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
