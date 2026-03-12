import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.dependencies.auth import get_current_user
from app.dependencies.rate_limit import RateLimit
from app.models.optimization import Optimization
from app.schemas.auth import ERR_INSUFFICIENT_PERMISSIONS, AuthenticatedUser
from app.services.optimization_service import VALID_SORT_COLUMNS, compute_stats, escape_like

logger = logging.getLogger(__name__)
router = APIRouter(tags=["history"])

# Valid status values for the status filter query parameter.
VALID_STATUSES: frozenset[str] = frozenset({"running", "completed", "failed", "pending"})


class BatchDeleteRequest(BaseModel):
    ids: list[str]

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, v: list[str]) -> list[str]:
        if len(v) < 1:
            raise ValueError("At least one ID is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 IDs per batch delete request")
        return v


class BatchDeleteResponse(BaseModel):
    deleted_count: int
    ids: list[str]


@router.get("/api/history")
async def list_history(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    project: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    has_repo: Optional[bool] = Query(None),
    min_score: Optional[float] = Query(None, ge=1.0, le=10.0),
    max_score: Optional[float] = Query(None, ge=1.0, le=10.0),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY)),
):
    """List optimization history with pagination, search, sort, and filter."""
    query = select(Optimization).where(
        Optimization.deleted_at.is_(None),
        Optimization.user_id == current_user.id,
    )

    # Filters
    if search:
        escaped = escape_like(search)
        search_pattern = f"%{escaped}%"
        query = query.where(
            (Optimization.raw_prompt.ilike(search_pattern, escape="\\"))
            | (Optimization.optimized_prompt.ilike(search_pattern, escape="\\"))
            | (Optimization.title.ilike(search_pattern, escape="\\"))
            | (Optimization.project.ilike(search_pattern, escape="\\"))
        )
    if project:
        query = query.where(Optimization.project == project)
    if task_type:
        query = query.where(Optimization.task_type == task_type)
    if framework:
        query = query.where(Optimization.primary_framework == framework)
    if has_repo is True:
        query = query.where(Optimization.linked_repo_full_name.isnot(None))
    elif has_repo is False:
        query = query.where(Optimization.linked_repo_full_name.is_(None))
    if min_score is not None:
        query = query.where(Optimization.overall_score >= min_score)
    if max_score is not None:
        query = query.where(Optimization.overall_score <= max_score)
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
            )
        query = query.where(Optimization.status == status)

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Sorting — whitelist prevents getattr on arbitrary user input
    if sort not in VALID_SORT_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort column '{sort}'. Must be one of: {', '.join(sorted(VALID_SORT_COLUMNS))}",
        )
    if order not in ("asc", "desc"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order '{order}'. Must be 'asc' or 'desc'.",
        )
    sort_column = getattr(Optimization, sort)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    optimizations = result.scalars().all()

    fetched = len(optimizations)
    has_more = (offset + fetched) < total
    return {
        "total": total,
        "count": fetched,
        "offset": offset,
        "items": [opt.to_dict() for opt in optimizations],
        "has_more": has_more,
        "next_offset": offset + fetched if has_more else None,
    }


@router.post("/api/history/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_optimizations(
    request: Request,
    body: BatchDeleteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY_BATCH_DELETE)),
):
    """Batch soft-delete optimization records (user-scoped, all-or-nothing)."""
    from app.services.optimization_service import batch_delete_optimizations as svc_batch_delete

    deleted_ids = await svc_batch_delete(session, current_user.id, body.ids)
    logger.info(
        "Batch-deleted %d optimizations by user %s",
        len(deleted_ids), current_user.id,
    )
    return BatchDeleteResponse(deleted_count=len(deleted_ids), ids=deleted_ids)


@router.delete("/api/history/{optimization_id}")
async def delete_optimization(
    request: Request,
    optimization_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY_WRITE)),
):
    """Soft-delete an optimization record (user-scoped)."""
    from app.services.optimization_service import get_optimization_orm

    # Fetch without user filter to distinguish 404 from 403
    opt = await get_optimization_orm(session, optimization_id)
    if not opt:
        raise HTTPException(status_code=404, detail="Optimization not found")
    if opt.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={"code": ERR_INSUFFICIENT_PERMISSIONS, "message": "Not authorized to delete this optimization"},
        )
    opt.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    logger.info("Soft-deleted optimization %s by user %s", optimization_id, current_user.id)
    return {"deleted": True, "id": optimization_id}


@router.get("/api/history/trash")
async def list_trash(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY)),
):
    """List soft-deleted optimizations pending purge (deleted within the last 7 days)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    base_filter = [
        Optimization.deleted_at.isnot(None),
        Optimization.deleted_at >= cutoff,
        Optimization.user_id == current_user.id,
    ]

    # Count total matching items
    count_query = select(func.count()).select_from(
        select(Optimization).where(*base_filter).subquery()
    )
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Paginated items
    query = (
        select(Optimization)
        .where(*base_filter)
        .order_by(Optimization.deleted_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    items = [opt.to_dict() for opt in result.scalars().all()]
    fetched = len(items)
    has_more = (offset + fetched) < total
    return {
        "total": total,
        "count": fetched,
        "offset": offset,
        "items": items,
        "has_more": has_more,
        "next_offset": offset + fetched if has_more else None,
    }


@router.post("/api/history/{optimization_id}/restore")
async def restore_optimization(
    request: Request,
    optimization_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY_WRITE)),
) -> dict:
    """Restore a soft-deleted optimization (clears deleted_at)."""
    from app.services.optimization_service import restore_optimization as svc_restore
    result = await session.execute(
        select(Optimization).where(
            Optimization.id == optimization_id,
            Optimization.deleted_at.isnot(None),
        )
    )
    opt = result.scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="Not found in trash")
    if opt.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={"code": ERR_INSUFFICIENT_PERMISSIONS, "message": "Not authorized to restore this optimization"},
        )
    restored = await svc_restore(session, optimization_id, current_user.id)
    if not restored:
        raise HTTPException(status_code=500, detail="Restore operation failed unexpectedly")
    await session.commit()
    return {"restored": True, "id": optimization_id}


@router.get("/api/history/stats")
async def get_stats(
    request: Request,
    project: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY)),
):
    """Get aggregated statistics about optimization history (user-scoped)."""
    return await compute_stats(session, project=project, user_id=current_user.id)
