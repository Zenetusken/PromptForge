"""History endpoints for browsing and managing past optimizations."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.converters import optimization_to_summary_response
from app.database import get_db
from app.repositories.optimization import ListFilters, OptimizationRepository, Pagination
from app.schemas.optimization import HistoryResponse, StatsResponse

router = APIRouter(tags=["history"])


@router.api_route("/api/history", methods=["GET", "HEAD"], response_model=HistoryResponse)
async def get_history(
    response: Response,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search in prompt text and title"),
    sort: str = Query("created_at", description="Field to sort by"),
    sort_by: str | None = Query(None, description="Alias for sort (field to sort by)"),
    order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
    project: str | None = Query(None, description="Filter by project"),
    task_type: str | None = Query(None, description="Filter by task type"),
    status: str | None = Query(None, description="Filter by status"),
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


@router.delete("/api/history/all")
async def clear_all_history(
    db: AsyncSession = Depends(get_db),
):
    """Delete all optimization records from the database."""
    repo = OptimizationRepository(db)
    count = await repo.clear_all()

    if count == 0:
        return {"message": "No records to delete", "deleted_count": 0}

    await db.commit()
    return {"message": f"Deleted {count} records", "deleted_count": count}


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

    await db.commit()
    return {"message": "Optimization deleted", "id": optimization_id}


@router.api_route("/api/history/stats", methods=["GET", "HEAD"], response_model=StatsResponse)
async def get_stats(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve aggregated statistics across all optimizations."""
    repo = OptimizationRepository(db)
    stats = await repo.get_stats()
    response.headers["Cache-Control"] = "max-age=30"
    return StatsResponse(**stats)
