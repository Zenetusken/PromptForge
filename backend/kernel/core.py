"""Kernel core — the central object providing shared infrastructure to apps."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from kernel.registry.app_registry import AppRegistry
    from kernel.services.registry import ServiceRegistry

logger = logging.getLogger(__name__)


@dataclass
class Kernel:
    """Central kernel object passed to app lifecycle hooks.

    Provides access to shared infrastructure: app registry, database sessions,
    service registry, and convenience methods for common operations.
    """

    app_registry: AppRegistry
    db_session_factory: async_sessionmaker
    services: ServiceRegistry = field(default_factory=lambda: _lazy_service_registry())

    def get_provider(
        self,
        name: str | None = None,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> Any:
        """Get an LLM provider instance.

        Args:
            name: Provider name (e.g. 'claude-cli', 'anthropic'). Auto-detects if None.
            api_key: Optional API key override.
            model: Optional model override.

        Returns:
            An LLMProvider instance.
        """
        from app.providers import get_provider

        return get_provider(name, api_key=api_key, model=model)


def _lazy_service_registry() -> ServiceRegistry:
    """Create a ServiceRegistry lazily to avoid circular imports."""
    from kernel.services.registry import ServiceRegistry

    return ServiceRegistry()
