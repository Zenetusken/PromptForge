"""History endpoints for browsing and managing past optimizations."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.converters import optimization_to_response
from app.database import get_db
from app.models.optimization import Optimization
from app.repositories.optimization import ListFilters, OptimizationRepository, Pagination
from app.schemas.optimization import HistoryResponse, StatsResponse
from app.utils.scores import round_score

router = APIRouter(tags=["history"])


@router.api_route("/api/history", methods=["GET", "HEAD"], response_model=HistoryResponse)
async def get_history(
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

    return HistoryResponse(
        items=[optimization_to_response(opt) for opt in items],
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
    db: AsyncSession = Depends(get_db),
):
    """Retrieve aggregated statistics across all optimizations.

    Returns averages for all scores, improvement rate, total counts,
    and the most common task type.
    """
    # Total optimizations
    total_result = await db.execute(select(func.count(Optimization.id)))
    total_optimizations = total_result.scalar() or 0

    if total_optimizations == 0:
        return StatsResponse()

    # Average scores
    avg_overall = await db.execute(
        select(func.avg(Optimization.overall_score)).where(
            Optimization.overall_score.isnot(None)
        )
    )
    avg_clarity = await db.execute(
        select(func.avg(Optimization.clarity_score)).where(
            Optimization.clarity_score.isnot(None)
        )
    )
    avg_specificity = await db.execute(
        select(func.avg(Optimization.specificity_score)).where(
            Optimization.specificity_score.isnot(None)
        )
    )
    avg_structure = await db.execute(
        select(func.avg(Optimization.structure_score)).where(
            Optimization.structure_score.isnot(None)
        )
    )
    avg_faithfulness = await db.execute(
        select(func.avg(Optimization.faithfulness_score)).where(
            Optimization.faithfulness_score.isnot(None)
        )
    )

    # Improvement rate
    improved_count_result = await db.execute(
        select(func.count(Optimization.id)).where(Optimization.is_improvement == True)
    )
    validated_count_result = await db.execute(
        select(func.count(Optimization.id)).where(
            Optimization.is_improvement.isnot(None)
        )
    )
    improved_count = improved_count_result.scalar() or 0
    validated_count = validated_count_result.scalar() or 0
    improvement_rate = (
        (improved_count / validated_count) if validated_count > 0 else None
    )

    # Total distinct projects
    projects_result = await db.execute(
        select(func.count(func.distinct(Optimization.project))).where(
            Optimization.project.isnot(None)
        )
    )
    total_projects = projects_result.scalar() or 0

    # Most common task type
    task_type_result = await db.execute(
        select(Optimization.task_type, func.count(Optimization.id).label("cnt"))
        .where(Optimization.task_type.isnot(None))
        .group_by(Optimization.task_type)
        .order_by(desc("cnt"))
        .limit(1)
    )
    most_common_row = task_type_result.first()
    most_common_task_type = most_common_row[0] if most_common_row else None

    # Optimizations today
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_result = await db.execute(
        select(func.count(Optimization.id)).where(
            Optimization.created_at >= today_start
        )
    )
    optimizations_today = today_result.scalar() or 0

    return StatsResponse(
        total_optimizations=total_optimizations,
        average_overall_score=round_score(avg_overall.scalar()),
        average_clarity_score=round_score(avg_clarity.scalar()),
        average_specificity_score=round_score(avg_specificity.scalar()),
        average_structure_score=round_score(avg_structure.scalar()),
        average_faithfulness_score=round_score(avg_faithfulness.scalar()),
        improvement_rate=round(improvement_rate, 4) if improvement_rate is not None else None,
        total_projects=total_projects,
        most_common_task_type=most_common_task_type,
        optimizations_today=optimizations_today,
    )
