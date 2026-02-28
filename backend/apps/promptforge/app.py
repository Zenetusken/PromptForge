"""PromptForge app — AppBase implementation with lifecycle hooks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kernel.registry.hooks import AppBase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


class PromptForgeApp(AppBase):
    """PromptForge application — AI prompt optimization pipeline."""

    @property
    def app_id(self) -> str:
        return "promptforge"

    async def on_startup(self, kernel) -> None:
        logger.info("PromptForge app starting up")

    async def on_shutdown(self, kernel: object) -> None:
        # Close persistent HTTP clients
        try:
            from app.routers.health import _mcp_client

            await _mcp_client.aclose()
        except Exception as exc:
            logger.debug("Failed to close MCP client: %s", exc)
        logger.info("PromptForge app shut down")

    async def run_migrations(self, conn: AsyncConnection) -> None:
        """Run PromptForge-specific database migrations.

        Delegates to the existing migration functions in app.database.
        """
        from app.database import (
            _backfill_missing_prompts,
            _backfill_prompt_ids,
            _cleanup_stale_running,
            _migrate_legacy_projects,
            _migrate_legacy_strategies,
            _rebuild_projects_table,
            _rebuild_prompts_table,
            _run_migrations,
        )

        await _run_migrations(conn)
        await _rebuild_projects_table(conn)
        await _rebuild_prompts_table(conn)
        await _migrate_legacy_strategies(conn)
        await _migrate_legacy_projects(conn)
        await _backfill_missing_prompts(conn)
        await _backfill_prompt_ids(conn)
        await _cleanup_stale_running(conn)
