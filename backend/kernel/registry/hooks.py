"""AppBase ABC — lifecycle hooks that all apps implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from kernel.bus.contracts import EventContract
    from kernel.core import Kernel


class AppBase(ABC):
    """Base class for all PromptForge apps.

    Apps implement lifecycle hooks that the kernel calls during
    discovery, installation, and runtime.

    The ``kernel`` parameter provides access to shared infrastructure:
    app registry, database sessions, service registry, and LLM providers.
    """

    @property
    @abstractmethod
    def app_id(self) -> str:
        """Unique identifier matching manifest.json ``id`` field."""
        ...

    async def on_install(self, kernel: Kernel | None) -> None:
        """Called once when the app is first installed.

        Use for one-time setup like seeding initial data.
        """

    async def on_enable(self, kernel: Kernel | None) -> None:
        """Called each time the app is enabled."""

    async def on_startup(self, kernel: Kernel | None) -> None:
        """Called on each server start for enabled apps.

        Use for registering event handlers, starting background tasks, etc.
        """

    async def on_shutdown(self, kernel: Kernel | None) -> None:
        """Called on server shutdown for enabled apps."""

    async def run_migrations(self, conn: AsyncConnection) -> None:
        """Run app-specific database migrations.

        Called during init_db() after kernel tables are created.
        Implementations should be idempotent (safe to run on every startup).
        """

    def get_mcp_tools(self) -> list:
        """Return MCP tool definitions for this app.

        Override to expose tools via the kernel's MCP aggregator.
        """
        return []

    def get_event_contracts(self) -> list[EventContract]:
        """Return event contracts published by this app.

        Override to declare typed event schemas for inter-app communication.
        Contracts are registered during kernel startup.
        """
        return []

    def get_event_handlers(self) -> dict[str, Callable]:
        """Return event handlers this app subscribes to.

        Override to register handlers for events from other apps.
        Keys are event type strings, values are async callables
        with signature ``(data: dict, source_app: str) -> Any``.
        """
        return {}
