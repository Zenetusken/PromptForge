"""AppRegistry — discovers, loads, and manages app lifecycle.

Modeled on ProviderRegistry: lazy loading, singleton pattern, clear lifecycle.
"""

from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.registry.hooks import AppBase
from kernel.registry.manifest import AppManifest

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class AppStatus:
    DISCOVERED = "discovered"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class AppRecord:
    """Runtime record for a registered app."""

    manifest: AppManifest
    instance: AppBase
    status: str = AppStatus.DISCOVERED
    error: str | None = None
    manifest_path: Path | None = None


class AppRegistry:
    """Discovers and manages installed apps.

    Discovery sources:
    1. ``backend/apps/`` directory (filesystem scan)
    2. pip entry points (``promptforge.apps`` group) — future
    """

    def __init__(self) -> None:
        self._apps: dict[str, AppRecord] = {}
        self._discovered = False
        self.kernel: object | None = None  # Set by main.py lifespan after construction

    def discover(self, apps_dir: Path | None = None) -> None:
        """Scan apps/ directory for manifest.json files.

        Each app directory must contain:
        - manifest.json — parsed into AppManifest
        - A Python module with an AppBase subclass (entry_point)
        """
        if apps_dir is None:
            apps_dir = Path(__file__).resolve().parent.parent.parent / "apps"

        if not apps_dir.is_dir():
            logger.info("No apps/ directory found at %s", apps_dir)
            self._discovered = True
            return

        for manifest_path in sorted(apps_dir.glob("*/manifest.json")):
            app_dir = manifest_path.parent
            try:
                manifest_data = json.loads(manifest_path.read_text())
                manifest = AppManifest.model_validate(manifest_data)
            except Exception as exc:
                logger.error("Failed to parse %s: %s", manifest_path, exc)
                continue

            if manifest.id in self._apps:
                logger.warning(
                    "Duplicate app ID %r from %s (already registered)",
                    manifest.id,
                    manifest_path,
                )
                continue

            try:
                instance = self._load_app_instance(manifest)
            except Exception as exc:
                logger.error(
                    "Failed to load app %r from %s: %s",
                    manifest.id,
                    manifest_path,
                    exc,
                )
                self._apps[manifest.id] = AppRecord(
                    manifest=manifest,
                    instance=_StubApp(manifest.id),
                    status=AppStatus.ERROR,
                    error=str(exc),
                    manifest_path=manifest_path,
                )
                continue

            self._apps[manifest.id] = AppRecord(
                manifest=manifest,
                instance=instance,
                status=AppStatus.ENABLED,  # Auto-enable on discovery for now
                manifest_path=manifest_path,
            )
            logger.info(
                "Discovered app %r v%s from %s",
                manifest.id,
                manifest.version,
                app_dir.name,
            )

        self._discovered = True

    def _load_app_instance(self, manifest: AppManifest) -> AppBase:
        """Import and instantiate the app's entry point class."""
        module = importlib.import_module(manifest.python_module)
        cls = getattr(module, manifest.entry_point)
        instance = cls()
        if not isinstance(instance, AppBase):
            raise TypeError(
                f"{manifest.entry_point} must be a subclass of AppBase"
            )
        return instance

    def get(self, app_id: str) -> AppRecord | None:
        """Get an app record by ID."""
        return self._apps.get(app_id)

    def list_all(self) -> list[AppRecord]:
        """Return all registered app records."""
        return list(self._apps.values())

    def list_enabled(self) -> list[AppRecord]:
        """Return only enabled app records."""
        return [r for r in self._apps.values() if r.status == AppStatus.ENABLED]

    def collect_mcp_tools(self) -> list:
        """Collect MCP tool definitions from all enabled apps.

        Calls ``get_mcp_tools()`` on each enabled app instance and returns
        the combined list. Apps return tool callables that can be registered
        with a FastMCP server via ``server.tool()(fn)``.
        """
        tools: list = []
        for record in self.list_enabled():
            try:
                app_tools = record.instance.get_mcp_tools()
                if app_tools:
                    tools.extend(app_tools)
                    logger.info(
                        "Collected %d MCP tool(s) from app %r",
                        len(app_tools),
                        record.manifest.id,
                    )
            except Exception as exc:
                logger.error(
                    "Failed to collect MCP tools from app %r: %s",
                    record.manifest.id,
                    exc,
                )
        return tools

    def enable_app(self, app_id: str) -> AppRecord | None:
        """Enable a previously disabled app."""
        record = self._apps.get(app_id)
        if not record:
            return None
        record.status = AppStatus.ENABLED
        record.error = None
        logger.info("Enabled app %r", app_id)
        return record

    def disable_app(self, app_id: str) -> AppRecord | None:
        """Disable an enabled app."""
        record = self._apps.get(app_id)
        if not record:
            return None
        record.status = AppStatus.DISABLED
        logger.info("Disabled app %r", app_id)
        return record

    async def persist_app_states(self, session_factory) -> None:
        """Persist current app states to the database via kernel settings."""
        states = {
            app_id: record.status
            for app_id, record in self._apps.items()
        }
        async with session_factory() as session:
            from kernel.repositories.app_settings import AppSettingsRepository
            repo = AppSettingsRepository(session)
            await repo.set_all("__kernel__", {"app_states": json.dumps(states)})
            await session.commit()
        logger.debug("Persisted app states: %s", states)

    async def restore_app_states(self, session_factory) -> None:
        """Restore persisted app states from the database."""
        try:
            async with session_factory() as session:
                from kernel.repositories.app_settings import AppSettingsRepository
                repo = AppSettingsRepository(session)
                settings = await repo.get_all("__kernel__")
                raw = settings.get("app_states")
                if not raw:
                    return
                states = json.loads(raw)
                for app_id, status in states.items():
                    record = self._apps.get(app_id)
                    if record and status == AppStatus.DISABLED:
                        record.status = AppStatus.DISABLED
                        logger.info("Restored app %r as DISABLED", app_id)
        except Exception:
            logger.debug("Could not restore app states (first boot?)", exc_info=True)

    def mount_routers(
        self, fastapi_app: FastAPI, exclude: set[str] | None = None
    ) -> None:
        """Mount all routers from enabled apps onto the FastAPI app.

        Args:
            fastapi_app: The FastAPI application to mount routers on.
            exclude: Set of app IDs whose routers are already mounted
                     (e.g. the host app whose routers are hardcoded).
        """
        for record in self.list_enabled():
            if exclude and record.manifest.id in exclude:
                continue
            for router_def in record.manifest.backend.routers:
                try:
                    module = importlib.import_module(router_def.module)
                    router = getattr(module, "router")
                    fastapi_app.include_router(
                        router,
                        prefix=router_def.prefix,
                        tags=router_def.tags,
                    )
                    logger.info(
                        "Mounted router %s at %s",
                        router_def.module,
                        router_def.prefix,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to mount router %s for app %r: %s",
                        router_def.module,
                        record.manifest.id,
                        exc,
                    )


class _StubApp(AppBase):
    """Placeholder for apps that failed to load."""

    def __init__(self, app_id: str):
        self._app_id = app_id

    @property
    def app_id(self) -> str:
        return self._app_id


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_registry: AppRegistry | None = None


def get_app_registry() -> AppRegistry:
    """Return the global AppRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = AppRegistry()
    return _registry


def reset_app_registry() -> None:
    """Reset the singleton (for testing)."""
    global _registry
    _registry = None
