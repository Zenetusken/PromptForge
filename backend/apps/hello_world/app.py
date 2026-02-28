"""Hello World app — minimal example of an AppBase implementation."""

from __future__ import annotations

import logging

from kernel.registry.hooks import AppBase

logger = logging.getLogger(__name__)


class HelloWorldApp(AppBase):
    """Minimal example app demonstrating the kernel app platform.

    Shows how to implement lifecycle hooks and expose an API endpoint.
    """

    @property
    def app_id(self) -> str:
        return "hello-world"

    async def on_startup(self, kernel) -> None:
        logger.info("Hello World app started!")

    async def on_shutdown(self, kernel) -> None:
        logger.info("Hello World app stopped.")
