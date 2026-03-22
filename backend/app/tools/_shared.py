"""Shared state and helpers for MCP tool handlers.

Module-level state is initialised by ``mcp_server.py``'s lifespan via the
``init_*`` / ``set_*`` helpers below.  Tool handler modules import from here
rather than referencing ``mcp_server`` globals directly.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from app.config import DATA_DIR, PROMPTS_DIR
from app.database import async_session_factory
from app.services.workspace_intelligence import WorkspaceIntelligence

if TYPE_CHECKING:
    from app.services.routing import RoutingManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — set once by mcp_server.py lifespan
# ---------------------------------------------------------------------------

_routing: RoutingManager | None = None
_taxonomy_engine = None  # TaxonomyEngine | None (avoid import for startup speed)
_workspace_intel = WorkspaceIntelligence()


def set_routing(routing: RoutingManager | None) -> None:
    """Set the module-level routing manager (called by lifespan)."""
    global _routing
    _routing = routing


def set_taxonomy_engine(engine) -> None:
    """Set the module-level taxonomy engine (called by lifespan)."""
    global _taxonomy_engine
    _taxonomy_engine = engine


def get_routing() -> RoutingManager:
    """Return routing manager or raise if not initialized."""
    if _routing is None:
        raise ValueError("Routing service not initialized")
    return _routing


def get_taxonomy_engine():
    """Return the taxonomy engine (may be None if init failed)."""
    return _taxonomy_engine


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def resolve_workspace_guidance(
    ctx: Context | None, workspace_path: str | None
) -> str | None:
    """Resolve workspace guidance: try roots/list first, fall back to workspace_path."""
    roots: list[Path] = []

    # Try MCP roots/list (zero-config)
    if ctx:
        try:
            roots_result = await ctx.session.list_roots()
            for root in roots_result.roots:
                uri = str(root.uri)
                if uri.startswith("file://"):
                    roots.append(Path(uri.removeprefix("file://")))
            if roots:
                logger.debug("Resolved %d workspace roots via MCP roots/list", len(roots))
        except Exception:
            logger.debug("Client does not support roots/list — will try workspace_path fallback")

    # Fallback: explicit workspace_path
    if not roots and workspace_path:
        roots = [Path(workspace_path)]
        logger.debug("Using explicit workspace_path fallback: %s", workspace_path)

    if not roots:
        logger.debug("No workspace roots resolved — skipping guidance injection")
        return None

    profile = _workspace_intel.analyze(roots)
    if profile:
        logger.info("Workspace guidance resolved: %d chars from %d roots", len(profile), len(roots))
    return profile
