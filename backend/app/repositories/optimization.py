"""Centralized database access for Optimization records."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import ColumnElement, and_, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.constants import ALLOWED_SORT_FIELDS, LEGACY_STRATEGY_ALIASES, OptimizationStatus
from app.converters import deserialize_json_field
from app.models.optimization import Optimization
from app.models.project import Prompt, Project
from app.utils.scores import round_score, score_threshold_to_db

logger = logging.getLogger(__name__)


@dataclass
class ListFilters:
    """Filter parameters for listing optimizations."""

    project: str | None = None
    task_type: str | None = None
    status: str | None = None
    min_score: float | None = None
    search: str | None = None
    completed_only: bool = False
    project_id: str | None = None
    include_archived: bool = True


@dataclass
class Pagination:
    """Pagination and sorting parameters."""

    sort: str = "created_at"
    order: str = "desc"
    offset: int = 0
    limit: int = 20


_UNSET: Any = object()
"""Sentinel indicating a keyword argument was not provided."""


class OptimizationRepository:
    """Encapsulates all DB queries for Optimization records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Single-record operations ---

    async def get_by_id(self, optimization_id: str) -> Optimization | None:
        # Alias for the FK-based project join (via prompt.project_id → projects)
        fk_project = Project.__table__.alias("fk_project")
        stmt = (
            select(
                Optimization,
                Prompt.project_id.label("fk_project_id"),
                Project.id.label("legacy_project_id"),
                func.coalesce(
                    fk_project.c.status, Project.status,
                ).label("project_status"),
            )
            .outerjoin(Prompt, Optimization.prompt_id == Prompt.id)
            .outerjoin(fk_project, Prompt.project_id == fk_project.c.id)
            .outerjoin(
                Project,
                and_(Optimization.prompt_id.is_(None), Optimization.project == Project.name),
            )
            .where(Optimization.id == optimization_id)
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        opt = row[0]
        opt._resolved_project_id = row[1] or row[2]  # type: ignore[attr-defined]
        opt._resolved_project_status = row.project_status  # type: ignore[attr-defined]
        return opt

    async def create(self, **kwargs) -> Optimization:
        opt = Optimization(**kwargs)
        self._session.add(opt)
        await self._session.flush()
        return opt

    async def delete_by_id(self, optimization_id: str) -> bool:
        exists = await self._session.execute(
            select(Optimization.id).where(Optimization.id == optimization_id)
        )
        if not exists.scalar_one_or_none():
            return False
        await self._session.execute(
            delete(Optimization).where(Optimization.id == optimization_id)
        )
        return True

    async def get_by_prompt_id(
        self,
        prompt_id: str,
        limit: int = 20,
        offset: int = 0,
        *,
        prompt_content: str | None = None,
        project_name: str | None = None,
    ) -> tuple[list[Optimization], int]:
        """Return paginated optimizations linked to a prompt, newest-first.

        Matches by FK (prompt_id) first; also matches by raw_prompt content
        within the same project as a fallback for un-linked legacy records.
        """
        condition = Optimization.prompt_id == prompt_id
        if prompt_content and project_name:
            condition = or_(
                condition,
                and_(
                    Optimization.prompt_id.is_(None),
                    Optimization.raw_prompt == prompt_content,
                    Optimization.project == project_name,
                ),
            )

        count_stmt = select(func.count(Optimization.id)).where(condition)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        query = (
            select(Optimization)
            .where(condition)
            .order_by(desc(Optimization.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def get_forge_counts(
        self,
        prompt_ids: list[str],
        *,
        content_map: dict[str, tuple[str, str]] | None = None,
    ) -> dict[str, int]:
        """Return {prompt_id: count} for optimizations linked to the given prompt IDs.

        Args:
            prompt_ids: Prompt IDs to count forges for.
            content_map: Optional ``{prompt_id: (content, project_name)}`` for
                content-based matching of un-linked legacy optimizations.
        """
        if not prompt_ids:
            return {}
        # FK-based counts
        stmt = (
            select(Optimization.prompt_id, func.count(Optimization.id))
            .where(Optimization.prompt_id.in_(prompt_ids))
            .group_by(Optimization.prompt_id)
        )
        result = await self._session.execute(stmt)
        counts: dict[str, int] = dict(result.all())

        # Content-based fallback: single batched query for un-linked optimizations
        if content_map:
            # Build reverse lookup: (content, project) → prompt_id
            content_to_pid: dict[tuple[str, str], str] = {
                (content, pname): pid for pid, (content, pname) in content_map.items()
            }
            contents = [content for content, _ in content_to_pid]
            projects = list({pname for _, pname in content_to_pid})

            content_stmt = (
                select(Optimization.raw_prompt, Optimization.project, func.count(Optimization.id))
                .where(
                    and_(
                        Optimization.prompt_id.is_(None),
                        Optimization.raw_prompt.in_(contents),
                        Optimization.project.in_(projects),
                    )
                )
                .group_by(Optimization.raw_prompt, Optimization.project)
            )
            content_result = await self._session.execute(content_stmt)
            for raw_prompt, proj, cnt in content_result.all():
                pid = content_to_pid.get((raw_prompt, proj))
                if pid and cnt:
                    counts[pid] = counts.get(pid, 0) + cnt

        return counts

    async def get_latest_forge_metadata(
        self,
        prompt_ids: list[str],
        *,
        content_map: dict[str, tuple[str, str]] | None = None,
    ) -> dict[str, Optimization]:
        """Return {prompt_id: Optimization} for the newest completed forge per prompt.

        Args:
            prompt_ids: Prompt IDs to look up.
            content_map: Optional ``{prompt_id: (content, project_name)}`` for
                content-based matching of un-linked legacy optimizations.
        """
        if not prompt_ids:
            return {}

        completed = OptimizationStatus.COMPLETED

        # FK-based: newest completed optimization per prompt_id
        newest_sub = (
            select(
                Optimization.prompt_id,
                func.max(Optimization.created_at).label("max_ts"),
            )
            .where(
                Optimization.prompt_id.in_(prompt_ids),
                Optimization.status == completed,
            )
            .group_by(Optimization.prompt_id)
            .subquery()
        )
        stmt = (
            select(Optimization)
            .join(
                newest_sub,
                and_(
                    Optimization.prompt_id == newest_sub.c.prompt_id,
                    Optimization.created_at == newest_sub.c.max_ts,
                ),
            )
            .where(Optimization.status == completed)
        )
        result = await self._session.execute(stmt)
        # Deterministic tiebreaker: if two rows share the same max timestamp,
        # keep the one with the lexicographically greatest id.
        latest: dict[str, Optimization] = {}
        for opt in result.scalars().all():
            if not opt.prompt_id:
                continue
            existing = latest.get(opt.prompt_id)
            if existing is None or opt.id > existing.id:
                latest[opt.prompt_id] = opt

        # Content-based fallback for un-linked legacy records
        if content_map:
            missing_pids = [pid for pid in prompt_ids if pid not in latest]
            if missing_pids:
                content_to_pid: dict[tuple[str, str], str] = {
                    (content, pname): pid
                    for pid, (content, pname) in content_map.items()
                    if pid in missing_pids
                }
                if content_to_pid:
                    contents = [content for content, _ in content_to_pid]
                    projects = list({pname for _, pname in content_to_pid})

                    # Subquery: newest timestamp per (raw_prompt, project)
                    leg_sub = (
                        select(
                            Optimization.raw_prompt,
                            Optimization.project,
                            func.max(Optimization.created_at).label("max_ts"),
                        )
                        .where(
                            Optimization.prompt_id.is_(None),
                            Optimization.status == completed,
                            Optimization.raw_prompt.in_(contents),
                            Optimization.project.in_(projects),
                        )
                        .group_by(Optimization.raw_prompt, Optimization.project)
                        .subquery()
                    )
                    leg_stmt = (
                        select(Optimization)
                        .join(
                            leg_sub,
                            and_(
                                Optimization.raw_prompt == leg_sub.c.raw_prompt,
                                Optimization.project == leg_sub.c.project,
                                Optimization.created_at == leg_sub.c.max_ts,
                            ),
                        )
                        .where(
                            Optimization.prompt_id.is_(None),
                            Optimization.status == completed,
                        )
                    )
                    leg_result = await self._session.execute(leg_stmt)
                    for opt in leg_result.scalars().all():
                        pid = content_to_pid.get((opt.raw_prompt, opt.project))
                        if not pid:
                            continue
                        # Deterministic tiebreaker: keep greatest id on ties
                        existing = latest.get(pid)
                        if existing is None or opt.id > existing.id:
                            latest[pid] = opt

        return latest

    async def title_exists(
        self,
        title: str,
        project: str | None = None,
        exclude_id: str | None = None,
    ) -> bool:
        """Check if an optimization with the given title exists (case-insensitive).

        Optionally scoped to a project name.
        """
        conditions = [func.lower(Optimization.title) == title.lower()]
        if project:
            conditions.append(Optimization.project == project)
        if exclude_id:
            conditions.append(Optimization.id != exclude_id)
        stmt = select(func.count(Optimization.id)).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    # --- List with filters ---

    def _build_search_filter(self, search_text: str) -> ColumnElement[bool]:
        """Build a search filter across text columns."""
        escaped = search_text.replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped}%"
        return (
            Optimization.raw_prompt.ilike(pattern)
            | Optimization.optimized_prompt.ilike(pattern)
            | Optimization.title.ilike(pattern)
            | Optimization.tags.ilike(pattern)
            | Optimization.project.ilike(pattern)
        )

    def _apply_filters(
        self, query: Select, count_query: Select, filters: ListFilters,
    ) -> tuple[Select, Select]:
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
        if filters.project_id:
            # Match via FK chain (prompt.project_id) or legacy name match
            pid_alias = Prompt.__table__.alias("pid_filter")
            proj_alias = Project.__table__.alias("proj_filter")
            fk_match = Optimization.prompt_id.in_(
                select(pid_alias.c.id).where(pid_alias.c.project_id == filters.project_id)
            )
            legacy_match = and_(
                Optimization.prompt_id.is_(None),
                Optimization.project.in_(
                    select(proj_alias.c.name).where(proj_alias.c.id == filters.project_id)
                ),
            )
            conditions.append(or_(fk_match, legacy_match))

        if not filters.include_archived:
            # Exclude optimizations linked to archived or deleted projects
            # (both FK and legacy paths). Uses NOT IN on optimization IDs to
            # avoid SQL NULL logic issues.
            arch_prompt = Prompt.__table__.alias("arch_prompt")
            arch_proj_fk = Project.__table__.alias("arch_proj_fk")
            arch_proj_leg = Project.__table__.alias("arch_proj_leg")
            hidden_statuses = ["archived", "deleted"]
            # IDs linked via FK to archived/deleted projects
            exclude_fk = (
                select(Optimization.id)
                .join(arch_prompt, Optimization.prompt_id == arch_prompt.c.id)
                .join(arch_proj_fk, arch_prompt.c.project_id == arch_proj_fk.c.id)
                .where(arch_proj_fk.c.status.in_(hidden_statuses))
            )
            # IDs linked via legacy project name to archived/deleted projects
            exclude_legacy = (
                select(Optimization.id)
                .where(
                    and_(
                        Optimization.prompt_id.is_(None),
                        Optimization.project.in_(
                            select(arch_proj_leg.c.name)
                            .where(arch_proj_leg.c.status.in_(hidden_statuses))
                        ),
                    )
                )
            )
            conditions.append(
                Optimization.id.notin_(exclude_fk.union(exclude_legacy))
            )

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        return query, count_query

    def _apply_sort_and_paginate(self, query: Select, pagination: Pagination) -> Select:
        """Apply sorting and pagination to a query."""
        sort_field = pagination.sort
        if sort_field not in ALLOWED_SORT_FIELDS:
            logger.debug("Invalid sort field %r, defaulting to created_at", sort_field)
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

        # Alias for the FK-based project join (via prompt.project_id → projects)
        fk_project = Project.__table__.alias("fk_project")
        query = select(
            Optimization,
            Prompt.project_id.label("fk_project_id"),
            Project.id.label("legacy_project_id"),
            func.coalesce(
                fk_project.c.status, Project.status,
            ).label("project_status"),
        ).outerjoin(
            Prompt, Optimization.prompt_id == Prompt.id
        ).outerjoin(
            fk_project, Prompt.project_id == fk_project.c.id,
        ).outerjoin(
            Project,
            and_(Optimization.prompt_id.is_(None), Optimization.project == Project.name),
        )
        count_query = select(func.count(Optimization.id))

        query, count_query = self._apply_filters(query, count_query, filters)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        query = self._apply_sort_and_paginate(query, pagination)

        result = await self._session.execute(query)
        items: list[Optimization] = []
        for row in result.all():
            opt = row[0]
            opt._resolved_project_id = row[1] or row[2]  # type: ignore[attr-defined]
            opt._resolved_project_status = row.project_status  # type: ignore[attr-defined]
            items.append(opt)

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

    async def delete_by_ids(self, ids: list[str]) -> tuple[list[str], list[str]]:
        """Delete multiple optimization records by ID.

        Returns (deleted_ids, not_found_ids).
        """
        result = await self._session.execute(
            select(Optimization.id).where(Optimization.id.in_(ids))
        )
        existing_ids = {row[0] for row in result.all()}

        deleted_ids = [i for i in ids if i in existing_ids]
        not_found_ids = [i for i in ids if i not in existing_ids]

        if deleted_ids:
            await self._session.execute(
                delete(Optimization).where(Optimization.id.in_(deleted_ids))
            )

        return deleted_ids, not_found_ids

    # --- Tags / metadata ---

    async def update_tags(
        self,
        optimization_id: str,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
        project: str | None = _UNSET,
        title: str | None = _UNSET,
    ) -> dict[str, Any] | None:
        """Update tags and metadata. Returns updated info dict, or None if not found.

        Pass ``project=None`` or ``title=None`` to clear the field.
        Omit the argument entirely to leave it unchanged.
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

        if project is not _UNSET:
            opt.project = project if project else None

        if title is not _UNSET:
            opt.title = title if title else None

        return {
            "id": optimization_id,
            "tags": current_tags,
            "project": opt.project,
            "title": opt.title,
            "updated": True,
        }

    # --- Statistics ---

    async def get_stats(self, project: str | None = None) -> dict[str, Any]:
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
                "strategy_distribution": None,
                "score_by_strategy": None,
                "task_types_by_strategy": None,
            }

        imp = row.improved / row.validated if row.validated else None

        # Per-strategy distribution and score averages.
        # Prefer the dedicated `strategy` column; fall back to `framework_applied`
        # for legacy rows that predate the column addition.
        strategy_col = func.coalesce(Opt.strategy, Opt.framework_applied)
        strategy_query = (
            select(
                strategy_col.label("strategy_name"),
                func.count(Opt.id).label("count"),
                func.avg(Opt.overall_score).label("avg_score"),
            )
            .where(completed)
            .where(strategy_col.isnot(None))
            .group_by(strategy_col)
        )
        if project:
            strategy_query = strategy_query.where(Opt.project == project)

        strategy_result = await self._session.execute(strategy_query)
        strategy_rows = strategy_result.all()

        strategy_distribution: dict[str, int] = {}
        score_by_strategy: dict[str, float] = {}
        # Track raw counts for weighted score averaging when merging aliases.
        _score_weights: dict[str, tuple[float, int]] = {}  # name -> (sum, count)
        for srow in strategy_rows:
            name = LEGACY_STRATEGY_ALIASES.get(srow.strategy_name, srow.strategy_name)
            strategy_distribution[name] = strategy_distribution.get(name, 0) + srow.count
            if srow.avg_score is not None:
                prev_sum, prev_n = _score_weights.get(name, (0.0, 0))
                _score_weights[name] = (
                    prev_sum + srow.avg_score * srow.count,
                    prev_n + srow.count,
                )
        for name, (total_score, total_n) in _score_weights.items():
            score_by_strategy[name] = round(total_score / total_n, 4)

        # Per-strategy task type breakdown.
        task_by_strategy_query = (
            select(
                strategy_col.label("strategy_name"),
                Opt.task_type.label("task_type"),
                func.count(Opt.id).label("count"),
            )
            .where(completed)
            .where(strategy_col.isnot(None))
            .where(Opt.task_type.isnot(None))
            .group_by(strategy_col, Opt.task_type)
        )
        if project:
            task_by_strategy_query = task_by_strategy_query.where(Opt.project == project)

        tbs_result = await self._session.execute(task_by_strategy_query)
        tbs_rows = tbs_result.all()

        task_types_by_strategy: dict[str, dict[str, int]] = {}
        for trow in tbs_rows:
            name = LEGACY_STRATEGY_ALIASES.get(trow.strategy_name, trow.strategy_name)
            bucket = task_types_by_strategy.setdefault(name, {})
            bucket[trow.task_type] = bucket.get(trow.task_type, 0) + trow.count

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
            "strategy_distribution": strategy_distribution or None,
            "score_by_strategy": score_by_strategy or None,
            "task_types_by_strategy": task_types_by_strategy or None,
        }
