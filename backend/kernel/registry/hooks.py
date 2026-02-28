"""AppBase ABC — lifecycle hooks that all apps implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class AppBase(ABC):
    """Base class for all PromptForge apps.

    Apps implement lifecycle hooks that the kernel calls during
    discovery, installation, and runtime.

    The ``kernel`` parameter is reserved for future use (will provide
    access to shared services). Currently passed as ``None``.
    """

    @property
    @abstractmethod
    def app_id(self) -> str:
        """Unique identifier matching manifest.json ``id`` field."""
        ...

    async def on_install(self, kernel: Any) -> None:
        """Called once when the app is first installed.

        Use for one-time setup like seeding initial data.
        """

    async def on_enable(self, kernel: Any) -> None:
        """Called each time the app is enabled."""

    async def on_startup(self, kernel: Any) -> None:
        """Called on each server start for enabled apps.

        Use for registering event handlers, starting background tasks, etc.
        """

    async def on_shutdown(self, kernel: Any) -> None:
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
