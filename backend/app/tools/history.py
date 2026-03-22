"""Handler for synthesis_history MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging

from app.database import async_session_factory
from app.schemas.mcp_models import HistoryItem, HistoryOutput

logger = logging.getLogger(__name__)

_VALID_SORT_COLUMNS = frozenset({
    "created_at", "overall_score", "task_type", "strategy_used",
    "duration_ms", "status", "intent_label", "domain",
})


async def handle_history(
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    task_type: str | None = None,
    status: str | None = None,
) -> HistoryOutput:
    """Query optimization history with filtering and sorting."""
    # Validate and clamp
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    if sort_by not in _VALID_SORT_COLUMNS:
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    from app.services.optimization_service import OptimizationService

    async with async_session_factory() as db:
        opt_svc = OptimizationService(db)
        result = await opt_svc.list_optimizations(
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            task_type=task_type,
            status=status,
        )

        total = result["total"]
        optimizations = result["items"]

        # Batch lookup feedback ratings
        from sqlalchemy import select
        from app.models import Feedback

        opt_ids = [o.id for o in optimizations]
        feedback_map: dict[str, str] = {}
        if opt_ids:
            fb_result = await db.execute(
                select(Feedback.optimization_id, Feedback.rating).where(
                    Feedback.optimization_id.in_(opt_ids)
                )
            )
            for row in fb_result.all():
                # Keep latest feedback per optimization
                feedback_map[row[0]] = row[1]

        items = []
        for opt in optimizations:
            raw_preview = (opt.raw_prompt[:200] if opt.raw_prompt else None)
            optimized_preview = (opt.optimized_prompt[:200] if opt.optimized_prompt else None)
            created_str = opt.created_at.isoformat() if opt.created_at else None

            items.append(HistoryItem(
                id=opt.id,
                created_at=created_str,
                task_type=opt.task_type,
                strategy_used=opt.strategy_used,
                overall_score=opt.overall_score,
                status=opt.status or "unknown",
                intent_label=getattr(opt, "intent_label", None),
                domain=getattr(opt, "domain", None),
                raw_prompt_preview=raw_preview,
                optimized_prompt_preview=optimized_preview,
                feedback_rating=feedback_map.get(opt.id),
            ))

    count = len(items)
    has_more = (offset + count) < total

    return HistoryOutput(
        total=total,
        count=count,
        has_more=has_more,
        items=items,
    )
