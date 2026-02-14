"""History endpoints for browsing and managing past optimizations."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.converters import optimization_to_summary_response
from app.database import get_db
from app.models.optimization import Optimization
from app.repositories.optimization import ListFilters, OptimizationRepository, Pagination
from app.schemas.optimization import HistoryResponse, StatsResponse
from app.utils.scores import round_score

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
    """Retrieve aggregated statistics across all optimizations.

    Returns averages for all scores, improvement rate, total counts,
    and the most common task type — all in a single query.
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    O = Optimization

    # Scalar subquery for most common task type, merged into the main aggregation
    most_common_subq = (
        select(O.task_type)
        .where(O.task_type.isnot(None))
        .group_by(O.task_type)
        .order_by(desc(func.count(O.id)))
        .limit(1)
        .correlate(None)
        .scalar_subquery()
    )

    agg_result = await db.execute(
        select(
            func.count(O.id).label("total"),
            func.avg(O.overall_score).label("avg_overall"),
            func.avg(O.clarity_score).label("avg_clarity"),
            func.avg(O.specificity_score).label("avg_specificity"),
            func.avg(O.structure_score).label("avg_structure"),
            func.avg(O.faithfulness_score).label("avg_faithfulness"),
            func.count(O.id).filter(O.is_improvement == True).label("improved"),
            func.count(O.id).filter(O.is_improvement.isnot(None)).label("validated"),
            func.count(func.distinct(O.project)).filter(O.project.isnot(None)).label("projects"),
            func.count(O.id).filter(O.created_at >= today_start).label("today"),
            most_common_subq.label("most_common_task"),
        )
    )
    row = agg_result.one()

    response.headers["Cache-Control"] = "max-age=30"

    if not row.total:
        return StatsResponse()

    improvement_rate = (row.improved / row.validated) if row.validated else None

    return StatsResponse(
        total_optimizations=row.total,
        average_overall_score=round_score(row.avg_overall),
        average_clarity_score=round_score(row.avg_clarity),
        average_specificity_score=round_score(row.avg_specificity),
        average_structure_score=round_score(row.avg_structure),
        average_faithfulness_score=round_score(row.avg_faithfulness),
        improvement_rate=round(improvement_rate, 4) if improvement_rate is not None else None,
        total_projects=row.projects or 0,
        most_common_task_type=row.most_common_task,
        optimizations_today=row.today or 0,
    )
