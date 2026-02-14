"""Centralized database access for Optimization records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ALLOWED_SORT_FIELDS, OptimizationStatus
from app.converters import deserialize_json_field
from app.models.optimization import Optimization
from app.utils.scores import round_score, score_threshold_to_db


@dataclass
class ListFilters:
    """Filter parameters for listing optimizations."""

    project: str | None = None
    task_type: str | None = None
    status: str | None = None
    min_score: float | None = None
    search: str | None = None
    completed_only: bool = False


@dataclass
class Pagination:
    """Pagination and sorting parameters."""

    sort: str = "created_at"
    order: str = "desc"
    offset: int = 0
    limit: int = 20


class OptimizationRepository:
    """Encapsulates all DB queries for Optimization records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Single-record operations ---

    async def get_by_id(self, optimization_id: str) -> Optimization | None:
        stmt = select(Optimization).where(Optimization.id == optimization_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Optimization:
        opt = Optimization(**kwargs)
        self._session.add(opt)
        await self._session.flush()
        return opt

    async def delete_by_id(self, optimization_id: str) -> bool:
        opt = await self.get_by_id(optimization_id)
        if not opt:
            return False
        await self._session.execute(
            delete(Optimization).where(Optimization.id == optimization_id)
        )
        return True

    # --- List with filters ---

    def _build_search_filter(self, search_text: str):
        """Build a search filter across text columns."""
        return (
            Optimization.raw_prompt.ilike(f"%{search_text}%")
            | Optimization.optimized_prompt.ilike(f"%{search_text}%")
            | Optimization.title.ilike(f"%{search_text}%")
            | Optimization.tags.ilike(f"%{search_text}%")
            | Optimization.project.ilike(f"%{search_text}%")
        )

    def _apply_filters(self, query, count_query, filters: ListFilters):
        """Apply filter conditions to both the data and count queries."""
        conditions = []

        if filters.completed_only:
            conditions.append(Optimization.status == OptimizationStatus.COMPLETED)
        if filters.project:
            conditions.append(Optimization.project == filters.project)
        if filters.task_type:
            conditions.append(Optimization.task_type == filters.task_type)
        if filters.status:
            conditions.append(Optimization.status == filters.status)
        if filters.min_score is not None:
            threshold = score_threshold_to_db(filters.min_score)
            conditions.append(Optimization.overall_score >= threshold)
        if filters.search:
            conditions.append(self._build_search_filter(filters.search))

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        return query, count_query

    def _apply_sort_and_paginate(self, query, pagination: Pagination):
        """Apply sorting and pagination to a query."""
        sort_field = pagination.sort
        if sort_field not in ALLOWED_SORT_FIELDS:
            sort_field = "created_at"
        sort_column = getattr(Optimization, sort_field, Optimization.created_at)

        if pagination.order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))

        return query.offset(pagination.offset).limit(pagination.limit)

    async def list(
        self,
        filters: ListFilters | None = None,
        pagination: Pagination | None = None,
    ) -> tuple[list[Optimization], int]:
        """List optimizations with optional filters and pagination.

        Returns (items, total_count).
        """
        filters = filters or ListFilters()
        pagination = pagination or Pagination()

        query = select(Optimization)
        count_query = select(func.count(Optimization.id))

        query, count_query = self._apply_filters(query, count_query, filters)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        query = self._apply_sort_and_paginate(query, pagination)

        result = await self._session.execute(query)
        items = list(result.scalars().all())

        return items, total

    # --- Bulk operations ---

    async def clear_all(self) -> int:
        count_result = await self._session.execute(
            select(func.count(Optimization.id))
        )
        count = count_result.scalar() or 0
        if count > 0:
            await self._session.execute(delete(Optimization))
        return count

    # --- Tags / metadata ---

    async def update_tags(
        self,
        optimization_id: str,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
        project: str | None = ...,
        title: str | None = ...,
    ) -> dict | None:
        """Update tags and metadata. Returns updated info dict, or None if not found.

        Pass `project=None` or `title=None` to clear; omit (sentinel ...) to skip.
        """
        opt = await self.get_by_id(optimization_id)
        if not opt:
            return None

        current_tags = deserialize_json_field(opt.tags) or []

        if add_tags:
            for tag in add_tags:
                if tag not in current_tags:
                    current_tags.append(tag)

        if remove_tags:
            current_tags = [t for t in current_tags if t not in remove_tags]

        opt.tags = json.dumps(current_tags) if current_tags else None

        if project is not ...:
            opt.project = project if project else None

        if title is not ...:
            opt.title = title if title else None

        return {
            "id": optimization_id,
            "tags": current_tags,
            "project": opt.project,
            "title": opt.title,
            "updated": True,
        }

    # --- Statistics ---

    async def get_stats(self, project: str | None = None) -> dict:
        """Get usage statistics in a single aggregation query.

        Returns a dict suitable for both the web API (StatsResponse)
        and MCP. Optionally scoped to a project.
        """
        Opt = Optimization

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        most_common_subq = (
            select(Opt.task_type)
            .where(Opt.task_type.isnot(None))
            .group_by(Opt.task_type)
            .order_by(desc(func.count(Opt.id)))
            .limit(1)
            .correlate(None)
            .scalar_subquery()
        )

        completed = Opt.status == OptimizationStatus.COMPLETED

        base_query = select(
            func.count(Opt.id).label("total"),
            func.avg(Opt.overall_score).label("avg_overall"),
            func.avg(Opt.clarity_score).label("avg_clarity"),
            func.avg(Opt.specificity_score).label("avg_specificity"),
            func.avg(Opt.structure_score).label("avg_structure"),
            func.avg(Opt.faithfulness_score).label("avg_faithfulness"),
            func.count(Opt.id).filter(
                Opt.is_improvement.is_(True),
            ).label("improved"),
            func.count(Opt.id).filter(
                Opt.is_improvement.isnot(None),
            ).label("validated"),
            func.count(func.distinct(Opt.project)).filter(
                Opt.project.isnot(None),
            ).label("projects"),
            func.count(Opt.id).filter(
                Opt.created_at >= today_start,
            ).label("today"),
            most_common_subq.label("most_common_task"),
        ).where(completed)

        if project:
            base_query = base_query.where(Opt.project == project)

        result = await self._session.execute(base_query)
        row = result.one()

        total = row.total or 0
        if total == 0:
            return {
                "total_optimizations": 0,
                "average_overall_score": None,
                "average_clarity_score": None,
                "average_specificity_score": None,
                "average_structure_score": None,
                "average_faithfulness_score": None,
                "improvement_rate": None,
                "total_projects": 0,
                "most_common_task_type": None,
                "optimizations_today": 0,
            }

        imp = row.improved / row.validated if row.validated else None

        return {
            "total_optimizations": total,
            "average_overall_score": round_score(row.avg_overall),
            "average_clarity_score": round_score(row.avg_clarity),
            "average_specificity_score": round_score(row.avg_specificity),
            "average_structure_score": round_score(row.avg_structure),
            "average_faithfulness_score": round_score(row.avg_faithfulness),
            "improvement_rate": round_score(imp),
            "total_projects": row.projects or 0,
            "most_common_task_type": row.most_common_task,
            "optimizations_today": row.today or 0,
        }
