"""ServiceRegistry — dependency injection container for kernel services.

Apps declare ``requires_services`` in their manifest. The kernel registers
core services (llm, db, storage) and validates app requirements at startup.
Apps access services via ``kernel.services.get("llm")`` in lifecycle hooks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """Simple service locator for kernel-provided services.

    Services are registered by name during kernel boot and consumed by apps
    via their lifecycle hooks (``kernel.services.get(name)``).
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """Register a service by name.

        Args:
            name: Service identifier (e.g. 'llm', 'db', 'storage').
            service: The service object or factory function.
        """
        if name in self._services:
            logger.warning("Service %r already registered, overwriting", name)
        self._services[name] = service
        logger.debug("Service registered: %s", name)

    def get(self, name: str) -> Any:
        """Retrieve a registered service by name.

        Args:
            name: Service identifier.

        Returns:
            The registered service object.

        Raises:
            KeyError: If the service is not registered.
        """
        if name not in self._services:
            raise KeyError(f"Service {name!r} is not registered")
        return self._services[name]

    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services

    def validate_requirements(self, required: list[str]) -> list[str]:
        """Check which required services are missing.

        Args:
            required: List of service names the app requires.

        Returns:
            List of missing service names (empty if all satisfied).
        """
        return [name for name in required if name not in self._services]

    @property
    def registered_names(self) -> list[str]:
        """List all registered service names."""
        return list(self._services.keys())
