"""TextForge app — lifecycle hooks and kernel integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from kernel.registry.hooks import AppBase

if TYPE_CHECKING:
    from kernel.bus.contracts import EventContract
    from kernel.core import Kernel

logger = logging.getLogger(__name__)


class TextForgeApp(AppBase):
    """Text transformation app that exercises kernel services."""

    @property
    def app_id(self) -> str:
        return "textforge"

    async def on_startup(self, kernel: Kernel | None) -> None:
        if kernel and hasattr(kernel, "services"):
            missing = kernel.services.validate_requirements(["llm", "storage"])
            if missing:
                logger.warning("TextForge: missing services %s", missing)
            else:
                logger.info("TextForge: all required services available")
        logger.info("TextForge app started")

    async def on_shutdown(self, kernel: Kernel | None) -> None:
        logger.info("TextForge app stopped")

    def get_event_contracts(self) -> list[EventContract]:
        from apps.textforge.events import TEXTFORGE_CONTRACTS
        return list(TEXTFORGE_CONTRACTS)

    def get_event_handlers(self) -> dict[str, Callable]:
        async def on_optimization_completed(data: dict, source_app: str) -> None:
            logger.info(
                "TextForge received optimization.completed from %s: optimization_id=%s score=%s",
                source_app,
                data.get("optimization_id"),
                data.get("overall_score"),
            )

        return {
            "promptforge:optimization.completed": on_optimization_completed,
        }
