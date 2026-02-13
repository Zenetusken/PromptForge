"""History endpoints for browsing and managing past optimizations."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ALLOWED_SORT_FIELDS
from app.converters import optimization_to_response
from app.database import get_db
from app.models.optimization import Optimization
from app.schemas.optimization import HistoryResponse, StatsResponse

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
    # Support sort_by as alias for sort
    if sort_by is not None:
        sort = sort_by

    # Build base query
    query = select(Optimization)
    count_query = select(func.count(Optimization.id))

    # Apply filters
    if search:
        search_filter = (
            Optimization.raw_prompt.ilike(f"%{search}%")
            | Optimization.title.ilike(f"%{search}%")
            | Optimization.optimized_prompt.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if project:
        query = query.where(Optimization.project == project)
        count_query = count_query.where(Optimization.project == project)

    if task_type:
        query = query.where(Optimization.task_type == task_type)
        count_query = count_query.where(Optimization.task_type == task_type)

    if status:
        query = query.where(Optimization.status == status)
        count_query = count_query.where(Optimization.status == status)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting (validate against whitelist)
    if sort not in ALLOWED_SORT_FIELDS:
        sort = "created_at"
    sort_column = getattr(Optimization, sort, Optimization.created_at)
    if order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    # Execute
    result = await db.execute(query)
    optimizations = result.scalars().all()

    return HistoryResponse(
        items=[optimization_to_response(opt) for opt in optimizations],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.delete("/api/history/all")
async def clear_all_history(
    db: AsyncSession = Depends(get_db),
):
    """Delete all optimization records from the database."""
    result = await db.execute(select(func.count(Optimization.id)))
    count = result.scalar() or 0

    if count == 0:
        return {"message": "No records to delete", "deleted_count": 0}

    await db.execute(delete(Optimization))
    await db.commit()

    return {"message": f"Deleted {count} records", "deleted_count": count}


@router.delete("/api/history/{optimization_id}")
async def delete_optimization(
    optimization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a single optimization record by ID."""
    stmt = select(Optimization).where(Optimization.id == optimization_id)
    result = await db.execute(stmt)
    optimization = result.scalar_one_or_none()

    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    await db.execute(
        delete(Optimization).where(Optimization.id == optimization_id)
    )
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
        average_overall_score=_round_or_none(avg_overall.scalar()),
        average_clarity_score=_round_or_none(avg_clarity.scalar()),
        average_specificity_score=_round_or_none(avg_specificity.scalar()),
        average_structure_score=_round_or_none(avg_structure.scalar()),
        average_faithfulness_score=_round_or_none(avg_faithfulness.scalar()),
        improvement_rate=round(improvement_rate, 4) if improvement_rate is not None else None,
        total_projects=total_projects,
        most_common_task_type=most_common_task_type,
        optimizations_today=optimizations_today,
    )


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    """Round a float value or return None if the value is None."""
    if value is None:
        return None
    return round(value, digits)
