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
            from apps.promptforge.routers.health import _mcp_client

            await _mcp_client.aclose()
        except Exception as exc:
            logger.debug("Failed to close MCP client: %s", exc)
        logger.info("PromptForge app shut down")

    async def run_migrations(self, conn: AsyncConnection) -> None:
        """Run PromptForge-specific database migrations."""
        from apps.promptforge.database import (
            backfill_missing_prompts,
            backfill_prompt_ids,
            cleanup_stale_running,
            migrate_legacy_projects,
            migrate_legacy_strategies,
            rebuild_projects_table,
            rebuild_prompts_table,
            run_migrations,
        )

        await run_migrations(conn)
        await rebuild_projects_table(conn)
        await rebuild_prompts_table(conn)
        await migrate_legacy_strategies(conn)
        await migrate_legacy_projects(conn)
        await backfill_missing_prompts(conn)
        await backfill_prompt_ids(conn)
        await cleanup_stale_running(conn)
