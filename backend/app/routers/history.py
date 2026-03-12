import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.dependencies.auth import get_current_user
from app.dependencies.rate_limit import RateLimit
from app.errors import bad_request, forbidden, internal_server_error, not_found
from app.models.optimization import Optimization
from app.schemas.auth import ERR_INSUFFICIENT_PERMISSIONS, AuthenticatedUser
from app.services.optimization_service import (
    OptimizationQuery,
    compute_stats,
    query_optimizations,
)

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
    # Validate status before passing to query
    if status:
        if status not in VALID_STATUSES:
            raise bad_request(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")

    try:
        return await query_optimizations(session, OptimizationQuery(
            limit=limit, offset=offset, project=project, task_type=task_type,
            framework=framework, has_repo=has_repo, min_score=min_score,
            max_score=max_score, status=status, search=search,
            search_columns=4, sort=sort, order=order,
            user_id=current_user.id,
        ))
    except ValueError as e:
        raise bad_request(str(e))


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
        raise not_found("Optimization not found")
    if opt.user_id != current_user.id:
        raise forbidden("Not authorized to delete this optimization", code=ERR_INSUFFICIENT_PERMISSIONS)
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
    return await query_optimizations(session, OptimizationQuery(
        limit=limit, offset=offset, user_id=current_user.id, deleted_only=True,
    ))


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
        raise not_found("Not found in trash")
    if opt.user_id != current_user.id:
        raise forbidden("Not authorized to restore this optimization", code=ERR_INSUFFICIENT_PERMISSIONS)
    restored = await svc_restore(session, optimization_id, current_user.id)
    if not restored:
        raise internal_server_error("Restore operation failed unexpectedly")
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
