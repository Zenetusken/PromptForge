"""History endpoints for browsing and managing past optimizations."""

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.converters import optimization_to_summary_response
from app.database import get_db
from app.repositories.optimization import ListFilters, OptimizationRepository, Pagination
from app.schemas.optimization import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    HistoryResponse,
    StatsResponse,
)

router = APIRouter(tags=["history"])


async def _get_history(
    response: Response,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search in prompt text and title"),
    sort: str = Query("created_at", description="Field to sort by"),
    sort_by: str | None = Query(None, description="Alias for sort (field to sort by)"),
    order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
    project: str | None = Query(None, description="Filter by project name"),
    project_id: str | None = Query(None, description="Filter by project ID"),
    task_type: str | None = Query(None, description="Filter by task type"),
    status: str | None = Query(None, description="Filter by status"),
    include_archived: bool = Query(True, description="Include items from archived projects"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve paginated optimization history with filtering and sorting.

    Supports searching by prompt text/title, filtering by project/task_type/status,
    and sorting by any column. Accepts both 'sort' and 'sort_by' parameter names.
    """
    if sort_by is not None:
        sort = sort_by

    repo = OptimizationRepository(db)
    offset = (page - 1) * per_page
    filters = ListFilters(
        project=project,
        task_type=task_type,
        status=status,
        search=search,
        project_id=project_id,
        include_archived=include_archived,
    )
    pagination = Pagination(sort=sort, order=order, offset=offset, limit=per_page)

    items, total = await repo.list(filters=filters, pagination=pagination)
    response.headers["Cache-Control"] = "max-age=0, must-revalidate"

    return HistoryResponse(
        items=[optimization_to_summary_response(opt) for opt in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/api/history", response_model=HistoryResponse)
async def get_history(
    response: Response,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search in prompt text and title"),
    sort: str = Query("created_at", description="Field to sort by"),
    sort_by: str | None = Query(None, description="Alias for sort (field to sort by)"),
    order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
    project: str | None = Query(None, description="Filter by project name"),
    project_id: str | None = Query(None, description="Filter by project ID"),
    task_type: str | None = Query(None, description="Filter by task type"),
    status: str | None = Query(None, description="Filter by status"),
    include_archived: bool = Query(True, description="Include items from archived projects"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve paginated optimization history with filtering and sorting."""
    return await _get_history(
        response, page, per_page, search, sort, sort_by, order,
        project, project_id, task_type, status, include_archived, db,
    )


@router.head("/api/history", include_in_schema=False)
async def get_history_head(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    sort: str = Query("created_at"),
    sort_by: str | None = Query(None),
    order: Literal["asc", "desc"] = Query("desc"),
    project: str | None = Query(None),
    project_id: str | None = Query(None),
    task_type: str | None = Query(None),
    status: str | None = Query(None),
    include_archived: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """HEAD variant of history list."""
    return await _get_history(
        response, page, per_page, search, sort, sort_by, order,
        project, project_id, task_type, status, include_archived, db,
    )


@router.delete("/api/history/all")
async def clear_all_history(
    db: AsyncSession = Depends(get_db),
    x_confirm_delete: str | None = Header(None, alias="X-Confirm-Delete"),
):
    """Delete all optimization records from the database.

    Requires ``X-Confirm-Delete: yes`` header as a safety guard.
    """
    if x_confirm_delete != "yes":
        raise HTTPException(
            status_code=400,
            detail="Bulk delete requires X-Confirm-Delete: yes header",
        )
    repo = OptimizationRepository(db)
    count = await repo.clear_all()

    if count == 0:
        return {"message": "No records to delete", "deleted_count": 0}

    return {"message": f"Deleted {count} records", "deleted_count": count}


@router.post("/api/history/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_optimizations(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple optimization records by ID."""
    repo = OptimizationRepository(db)
    deleted_ids, not_found_ids = await repo.delete_by_ids(payload.ids)
    return BulkDeleteResponse(
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
        not_found_ids=not_found_ids,
    )


@router.delete("/api/history/{optimization_id}")
async def delete_optimization(
    optimization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a single optimization record by ID."""
    repo = OptimizationRepository(db)
    deleted = await repo.delete_by_id(optimization_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Optimization not found")

    return {"message": "Optimization deleted", "id": optimization_id}


@router.get("/api/history/stats", response_model=StatsResponse)
async def get_stats(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve aggregated statistics across all optimizations."""
    repo = OptimizationRepository(db)
    stats = await repo.get_stats()
    response.headers["Cache-Control"] = "max-age=30"
    return StatsResponse(**stats)


@router.head("/api/history/stats", include_in_schema=False)
async def get_stats_head(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """HEAD variant of stats."""
    repo = OptimizationRepository(db)
    stats = await repo.get_stats()
    response.headers["Cache-Control"] = "max-age=30"
    return StatsResponse(**stats)
