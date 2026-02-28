"""Server-side stats cache with TTL-based invalidation.

Extracted from the history router so both HTTP endpoints and the MCP server
can share a single cache without circular imports.
"""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.repositories.optimization import OptimizationRepository

_STATS_CACHE_TTL = 300  # seconds (invalidated on mutations anyway)
_stats_cache: dict[str | None, tuple[float, dict]] = {}  # project_key → (timestamp, data)


def invalidate_stats_cache(project: str | None = None) -> None:
    """Clear cached stats.  Called by mutation endpoints and MCP tools.

    If *project* is given, invalidates that project's cache and the global
    (project=None) cache.  If *project* is None, clears everything.
    """
    if project is None:
        _stats_cache.clear()
    else:
        _stats_cache.pop(project, None)
        _stats_cache.pop(None, None)  # global cache also stale


async def get_stats_cached(project: str | None, db: AsyncSession) -> dict:
    """Return stats, using a server-side TTL cache to avoid re-running the heavy query."""
    cached = _stats_cache.get(project)
    if cached and (time.monotonic() - cached[0]) < _STATS_CACHE_TTL:
        return cached[1]

    repo = OptimizationRepository(db)
    stats = await repo.get_stats(project=project)
    _stats_cache[project] = (time.monotonic(), stats)
    return stats
