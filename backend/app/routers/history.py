"""History endpoint — sorted/filtered optimization list."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import OptimizationPattern
from app.services.optimization_service import OptimizationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
async def get_history(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    task_type: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    svc = OptimizationService(db)
    result = await svc.list_optimizations(
        offset=offset, limit=limit, sort_by=sort_by, sort_order=sort_order,
        task_type=task_type, status=status,
    )

    # Batch-fetch family IDs for all returned items in a single query (not N+1).
    items = result["items"]
    family_map: dict[str, str] = {}
    if items:
        opt_ids = [opt.id for opt in items]
        family_rows = (
            await db.execute(
                select(
                    OptimizationPattern.optimization_id,
                    OptimizationPattern.family_id,
                )
                .where(
                    OptimizationPattern.optimization_id.in_(opt_ids),
                    OptimizationPattern.relationship == "source",
                )
            )
        ).all()
        family_map = {row.optimization_id: row.family_id for row in family_rows}

    return {
        "total": result["total"],
        "count": result["count"],
        "offset": result["offset"],
        "has_more": result["has_more"],
        "next_offset": result["next_offset"],
        "items": [
            {
                "id": opt.id,
                "trace_id": opt.trace_id,
                "created_at": opt.created_at.isoformat() if opt.created_at else None,
                "task_type": opt.task_type,
                "strategy_used": opt.strategy_used,
                "overall_score": opt.overall_score,
                "status": opt.status,
                "duration_ms": opt.duration_ms,
                "provider": opt.provider,
                "raw_prompt": opt.raw_prompt[:100] if opt.raw_prompt else None,
                "optimized_prompt": opt.optimized_prompt[:100] if opt.optimized_prompt else None,
                "intent_label": opt.intent_label,
                "domain": opt.domain,
                "family_id": family_map.get(opt.id),
            }
            for opt in items
        ],
    }
