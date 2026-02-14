"""Centralized database access for Optimization records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ALLOWED_SORT_FIELDS, OptimizationStatus
from app.converters import deserialize_json_field
from app.models.optimization import Optimization
from app.utils.scores import score_threshold_to_db, score_to_display


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
        """Get usage statistics, optionally scoped to a project."""
        base_filter = Optimization.status == OptimizationStatus.COMPLETED
        if project:
            base_filter = base_filter & (Optimization.project == project)

        total_result = await self._session.execute(
            select(func.count(Optimization.id)).where(base_filter)
        )
        total_optimizations = total_result.scalar() or 0

        if total_optimizations == 0:
            return {
                "total_optimizations": 0,
                "avg_overall_score": 0,
                "projects": {},
                "task_types": {},
                "top_frameworks": {},
                "optimizations_today": 0,
                "optimizations_this_week": 0,
            }

        avg_result = await self._session.execute(
            select(func.avg(Optimization.overall_score)).where(
                base_filter & Optimization.overall_score.isnot(None)
            )
        )
        avg_raw = avg_result.scalar()
        avg_overall = score_to_display(avg_raw) if avg_raw is not None else 0

        projects_result = await self._session.execute(
            select(Optimization.project, func.count(Optimization.id))
            .where(base_filter & Optimization.project.isnot(None))
            .group_by(Optimization.project)
        )
        projects = {row[0]: row[1] for row in projects_result.all()}

        task_types_result = await self._session.execute(
            select(Optimization.task_type, func.count(Optimization.id))
            .where(base_filter & Optimization.task_type.isnot(None))
            .group_by(Optimization.task_type)
        )
        task_types = {row[0]: row[1] for row in task_types_result.all()}

        frameworks_result = await self._session.execute(
            select(Optimization.framework_applied, func.count(Optimization.id))
            .where(base_filter & Optimization.framework_applied.isnot(None))
            .group_by(Optimization.framework_applied)
        )
        top_frameworks = {row[0]: row[1] for row in frameworks_result.all()}

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_result = await self._session.execute(
            select(func.count(Optimization.id)).where(
                base_filter & (Optimization.created_at >= today_start)
            )
        )
        optimizations_today = today_result.scalar() or 0

        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        week_result = await self._session.execute(
            select(func.count(Optimization.id)).where(
                base_filter & (Optimization.created_at >= week_start)
            )
        )
        optimizations_this_week = week_result.scalar() or 0

        return {
            "total_optimizations": total_optimizations,
            "avg_overall_score": avg_overall,
            "projects": projects,
            "task_types": task_types,
            "top_frameworks": top_frameworks,
            "optimizations_today": optimizations_today,
            "optimizations_this_week": optimizations_this_week,
        }
