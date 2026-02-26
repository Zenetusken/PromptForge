"""Centralized database access for Optimization records."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import ColumnElement, and_, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.constants import ALLOWED_SORT_FIELDS, LEGACY_STRATEGY_ALIASES, OptimizationStatus
from app.converters import deserialize_json_field
from app.models.optimization import Optimization
from app.models.project import Project, Prompt
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
            # (both FK and legacy paths). Uses NOT EXISTS correlated subqueries
            # instead of NOT IN to avoid materializing the full result set.
            arch_prompt = Prompt.__table__.alias("arch_prompt")
            arch_proj_fk = Project.__table__.alias("arch_proj_fk")
            arch_proj_leg = Project.__table__.alias("arch_proj_leg")
            hidden_statuses = ["archived", "deleted"]

            # NOT EXISTS for FK path: prompt → project with hidden status
            fk_exists = (
                select(1)
                .select_from(arch_prompt)
                .join(arch_proj_fk, arch_prompt.c.project_id == arch_proj_fk.c.id)
                .where(arch_prompt.c.id == Optimization.prompt_id)
                .where(arch_proj_fk.c.status.in_(hidden_statuses))
                .correlate(Optimization)
            )

            # NOT EXISTS for legacy path: project name match with hidden status
            legacy_exists = (
                select(1)
                .select_from(arch_proj_leg)
                .where(arch_proj_leg.c.name == Optimization.project)
                .where(arch_proj_leg.c.status.in_(hidden_statuses))
                .where(Optimization.prompt_id.is_(None))
                .correlate(Optimization)
            )

            conditions.append(~fk_exists.exists())
            conditions.append(~legacy_exists.exists())

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

        completed = Opt.status == OptimizationStatus.COMPLETED

        # Build most-common-task subquery with project + completed filters
        most_common_q = (
            select(Opt.task_type)
            .where(Opt.task_type.isnot(None))
            .where(completed)
        )
        if project:
            most_common_q = most_common_q.where(Opt.project == project)
        most_common_subq = (
            most_common_q
            .group_by(Opt.task_type)
            .order_by(desc(func.count(Opt.id)))
            .limit(1)
            .correlate(None)
            .scalar_subquery()
        )

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
            func.count(Opt.id).filter(
                Opt.created_at >= today_start,
            ).label("today"),
            most_common_subq.label("most_common_task"),
        ).where(completed)

        if project:
            base_query = base_query.where(Opt.project == project)

        result = await self._session.execute(base_query)
        row = result.one()

        # Count active projects from the projects table (not from optimizations)
        # When scoped to a project, just use 1 (or 0 if no results).
        if project:
            total_active_projects = 1 if (row.total or 0) > 0 else 0
        else:
            proj_count_query = select(func.count(Project.id)).where(
                Project.status == "active"
            )
            proj_count_result = await self._session.execute(proj_count_query)
            total_active_projects = proj_count_result.scalar() or 0

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
                "secondary_strategy_distribution": None,
                "tags_by_strategy": None,
                "score_matrix": None,
                "score_variance": None,
                "confidence_by_strategy": None,
                "combo_effectiveness": None,
                "complexity_performance": None,
                "improvement_by_strategy": None,
                "error_rates": None,
                "trend_7d": {"count": 0, "avg_score": None},
                "trend_30d": {"count": 0, "avg_score": None},
                "token_economics": None,
                "win_rates": None,
            }

        imp = row.improved / row.validated if row.validated else None

        # Per-strategy distribution, score averages, and extended analytics.
        # Prefer the dedicated `strategy` column; fall back to `framework_applied`
        # for legacy rows that predate the column addition.
        strategy_col = func.coalesce(Opt.strategy, Opt.framework_applied)

        # --- Merged Strategy Query (A) ---
        # Single query returning count, avg_score, min_score, max_score,
        # avg(score^2) for variance, avg_confidence, improved/validated counts,
        # avg tokens, avg duration. Grouped by strategy.
        strategy_query = (
            select(
                strategy_col.label("strategy_name"),
                func.count(Opt.id).label("count"),
                func.avg(Opt.overall_score).label("avg_score"),
                func.min(Opt.overall_score).label("min_score"),
                func.max(Opt.overall_score).label("max_score"),
                func.avg(Opt.overall_score * Opt.overall_score).label("avg_score_sq"),
                func.avg(Opt.strategy_confidence).label("avg_confidence"),
                func.count(Opt.id).filter(
                    Opt.is_improvement.is_(True),
                ).label("improved_count"),
                func.count(Opt.id).filter(
                    Opt.is_improvement.isnot(None),
                ).label("validated_count"),
                func.avg(Opt.input_tokens).label("avg_input_tokens"),
                func.avg(Opt.output_tokens).label("avg_output_tokens"),
                func.avg(Opt.duration_ms).label("avg_duration_ms"),
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

        # Extended analytics accumulators
        # score_variance: {strategy: {min, max, avg, stddev, count}}
        _var_accum: dict[str, dict[str, float | int]] = {}
        # confidence_by_strategy: {strategy: avg_confidence}
        _conf_accum: dict[str, tuple[float, int]] = {}  # name -> (weighted_sum, count)
        # improvement_by_strategy: {strategy: {improved, validated, rate}}
        _imp_accum: dict[str, dict[str, int]] = {}
        # token_economics: {strategy: {avg_input_tokens, avg_output_tokens, avg_duration_ms}}
        _tok_accum: dict[str, dict[str, float | int]] = {}

        for srow in strategy_rows:
            name = LEGACY_STRATEGY_ALIASES.get(srow.strategy_name, srow.strategy_name)
            strategy_distribution[name] = strategy_distribution.get(name, 0) + srow.count
            if srow.avg_score is not None:
                prev_sum, prev_n = _score_weights.get(name, (0.0, 0))
                _score_weights[name] = (
                    prev_sum + srow.avg_score * srow.count,
                    prev_n + srow.count,
                )

            # Variance accumulator (merge aliases via weighted stats)
            if srow.avg_score is not None:
                prev = _var_accum.get(name)
                if prev is None:
                    # SQLite variance workaround: stddev = sqrt(max(0, E[X^2] - E[X]^2))
                    avg_sq = srow.avg_score_sq if srow.avg_score_sq is not None else 0
                    _variance = max(0, avg_sq - srow.avg_score ** 2)
                    _var_accum[name] = {
                        "min": srow.min_score,
                        "max": srow.max_score,
                        "avg": srow.avg_score,
                        "count": srow.count,
                        "_sum": srow.avg_score * srow.count,
                        "_sum_sq": avg_sq * srow.count,
                    }
                else:
                    prev["min"] = min(prev["min"], srow.min_score)
                    prev["max"] = max(prev["max"], srow.max_score)
                    prev["count"] += srow.count
                    prev["_sum"] += srow.avg_score * srow.count
                    avg_sq = srow.avg_score_sq if srow.avg_score_sq is not None else 0
                    prev["_sum_sq"] += avg_sq * srow.count

            # Confidence accumulator
            if srow.avg_confidence is not None:
                prev_csum, prev_cn = _conf_accum.get(name, (0.0, 0))
                _conf_accum[name] = (
                    prev_csum + srow.avg_confidence * srow.count,
                    prev_cn + srow.count,
                )

            # Improvement accumulator
            imp_entry = _imp_accum.get(name, {"improved": 0, "validated": 0})
            imp_entry["improved"] += srow.improved_count or 0
            imp_entry["validated"] += srow.validated_count or 0
            _imp_accum[name] = imp_entry

            # Token accumulator (merge weighted)
            tok = _tok_accum.get(name)
            if tok is None:
                _tok_accum[name] = {
                    "_count": srow.count,
                    "_input_sum": (srow.avg_input_tokens or 0) * srow.count,
                    "_output_sum": (srow.avg_output_tokens or 0) * srow.count,
                    "_dur_sum": (srow.avg_duration_ms or 0) * srow.count,
                }
            else:
                tok["_count"] += srow.count
                tok["_input_sum"] += (srow.avg_input_tokens or 0) * srow.count
                tok["_output_sum"] += (srow.avg_output_tokens or 0) * srow.count
                tok["_dur_sum"] += (srow.avg_duration_ms or 0) * srow.count

        for name, (total_score, total_n) in _score_weights.items():
            score_by_strategy[name] = round(total_score / total_n, 4)

        # Finalize score variance
        score_variance: dict[str, dict[str, float | int]] = {}
        for name, v in _var_accum.items():
            n = v["count"]
            avg = v["_sum"] / n
            avg_sq = v["_sum_sq"] / n
            stddev = math.sqrt(max(0, avg_sq - avg ** 2))
            score_variance[name] = {
                "min": round_score(v["min"]),
                "max": round_score(v["max"]),
                "avg": round_score(avg),
                "stddev": round(stddev, 4),
                "count": int(n),
            }

        # Finalize confidence by strategy
        confidence_by_strategy: dict[str, float] = {}
        for name, (csum, cn) in _conf_accum.items():
            confidence_by_strategy[name] = round(csum / cn, 4)

        # Finalize improvement by strategy
        improvement_by_strategy: dict[str, dict[str, float | int | None]] = {}
        for name, imp_data in _imp_accum.items():
            rate = (
                imp_data["improved"] / imp_data["validated"]
                if imp_data["validated"] > 0
                else None
            )
            improvement_by_strategy[name] = {
                "improved": imp_data["improved"],
                "validated": imp_data["validated"],
                "rate": round_score(rate),
            }

        # Finalize token economics
        token_economics: dict[str, dict[str, int | None]] = {}
        for name, tok in _tok_accum.items():
            n = tok["_count"]
            token_economics[name] = {
                "avg_input_tokens": round(tok["_input_sum"] / n) if n else None,
                "avg_output_tokens": round(tok["_output_sum"] / n) if n else None,
                "avg_duration_ms": round(tok["_dur_sum"] / n) if n else None,
            }

        # --- Merged Score Matrix Query (B) ---
        # Per-strategy task type breakdown with avg_score for the score matrix.
        task_by_strategy_query = (
            select(
                strategy_col.label("strategy_name"),
                Opt.task_type.label("task_type"),
                func.count(Opt.id).label("count"),
                func.avg(Opt.overall_score).label("avg_score"),
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
        # score_matrix: {strategy: {task_type: {count, avg_score}}}
        score_matrix: dict[str, dict[str, dict[str, float | int]]] = {}
        for trow in tbs_rows:
            name = LEGACY_STRATEGY_ALIASES.get(trow.strategy_name, trow.strategy_name)
            bucket = task_types_by_strategy.setdefault(name, {})
            bucket[trow.task_type] = bucket.get(trow.task_type, 0) + trow.count

            # Score matrix accumulator (handle alias merges via weighted average)
            strat_matrix = score_matrix.setdefault(name, {})
            if trow.task_type in strat_matrix:
                prev = strat_matrix[trow.task_type]
                prev_count = prev["count"]
                new_count = prev_count + trow.count
                if trow.avg_score is not None and prev.get("avg_score") is not None:
                    prev["avg_score"] = round_score(
                        (prev["avg_score"] * prev_count + trow.avg_score * trow.count)
                        / new_count,
                    )
                elif trow.avg_score is not None:
                    prev["avg_score"] = round_score(trow.avg_score)
                prev["count"] = new_count
            else:
                strat_matrix[trow.task_type] = {
                    "count": trow.count,
                    "avg_score": round_score(trow.avg_score),
                }

        # Derive win_rates from score_matrix: best strategy per task type
        win_rates: dict[str, dict[str, str | float | int]] = {}
        # Invert matrix: task_type → [(strategy, avg_score, count)]
        _task_candidates: dict[str, list[tuple[str, float, int]]] = {}
        for strat_name, type_map in score_matrix.items():
            for task_type, data in type_map.items():
                if data.get("avg_score") is not None:
                    _task_candidates.setdefault(task_type, []).append(
                        (strat_name, data["avg_score"], data["count"]),
                    )
        for task_type, candidates in _task_candidates.items():
            # Best = highest avg_score, tie-break by count, then name
            best = max(candidates, key=lambda c: (c[1], c[2], c[0]))
            win_rates[task_type] = {
                "strategy": best[0],
                "avg_score": best[1],
                "count": best[2],
            }

        # --- Extended Secondary Query (C) ---
        # Secondary strategy distribution, per-strategy tags, and combo effectiveness.
        # Also fetch overall_score to track (primary, secondary) pair performance.
        sec_query = select(
            strategy_col.label("strategy_name"),
            Opt.secondary_frameworks,
            Opt.tags,
            Opt.overall_score,
        ).where(completed)
        if project:
            sec_query = sec_query.where(Opt.project == project)

        sec_result = await self._session.execute(sec_query)
        sec_rows = sec_result.all()

        secondary_distribution: dict[str, int] = {}
        tags_by_strategy_raw: dict[str, dict[str, int]] = {}
        # combo_effectiveness: {primary: {secondary: {count, total_score}}}
        _combo_accum: dict[str, dict[str, dict[str, float | int]]] = {}
        for srow in sec_rows:
            primary_name = LEGACY_STRATEGY_ALIASES.get(
                srow.strategy_name, srow.strategy_name,
            ) if srow.strategy_name else None

            # Count secondary framework usage and track combo scores
            if srow.secondary_frameworks:
                try:
                    secondaries = json.loads(srow.secondary_frameworks)
                except (json.JSONDecodeError, TypeError):
                    secondaries = []
                for fw in secondaries:
                    if isinstance(fw, str) and fw:
                        sec_name = LEGACY_STRATEGY_ALIASES.get(fw, fw)
                        secondary_distribution[sec_name] = (
                            secondary_distribution.get(sec_name, 0) + 1
                        )
                        # Track combo effectiveness
                        if primary_name:
                            combo_primary = _combo_accum.setdefault(primary_name, {})
                            combo = combo_primary.get(sec_name, {"count": 0, "total_score": 0.0})
                            combo["count"] += 1
                            if srow.overall_score is not None:
                                combo["total_score"] += srow.overall_score
                            combo_primary[sec_name] = combo

            # Bucket tags by primary strategy
            if primary_name and srow.tags:
                try:
                    tag_list = json.loads(srow.tags)
                except (json.JSONDecodeError, TypeError):
                    tag_list = []
                bucket = tags_by_strategy_raw.setdefault(primary_name, {})
                for tag in tag_list:
                    if isinstance(tag, str) and tag:
                        bucket[tag] = bucket.get(tag, 0) + 1

        # Keep only top 4 tags per strategy (by count desc, then alphabetical)
        tags_by_strategy: dict[str, dict[str, int]] = {}
        for strat_name, tag_counts in tags_by_strategy_raw.items():
            sorted_tags = sorted(tag_counts.items(), key=lambda t: (-t[1], t[0]))[:4]
            tags_by_strategy[strat_name] = dict(sorted_tags)

        # Finalize combo effectiveness
        combo_effectiveness: dict[str, dict[str, dict[str, float | int]]] = {}
        for primary, secondaries in _combo_accum.items():
            combo_effectiveness[primary] = {}
            for sec_name, data in secondaries.items():
                avg = data["total_score"] / data["count"] if data["count"] > 0 else None
                combo_effectiveness[primary][sec_name] = {
                    "count": data["count"],
                    "avg_score": round_score(avg),
                }

        # --- New Complexity Query (D) ---
        complexity_query = (
            select(
                strategy_col.label("strategy_name"),
                Opt.complexity.label("complexity"),
                func.count(Opt.id).label("count"),
                func.avg(Opt.overall_score).label("avg_score"),
            )
            .where(completed)
            .where(strategy_col.isnot(None))
            .where(Opt.complexity.isnot(None))
            .group_by(strategy_col, Opt.complexity)
        )
        if project:
            complexity_query = complexity_query.where(Opt.project == project)

        complexity_result = await self._session.execute(complexity_query)
        complexity_rows = complexity_result.all()

        complexity_performance: dict[str, dict[str, dict[str, float | int]]] = {}
        for crow in complexity_rows:
            name = LEGACY_STRATEGY_ALIASES.get(crow.strategy_name, crow.strategy_name)
            strat_map = complexity_performance.setdefault(name, {})
            if crow.complexity in strat_map:
                prev = strat_map[crow.complexity]
                prev_count = prev["count"]
                new_count = prev_count + crow.count
                if crow.avg_score is not None and prev.get("avg_score") is not None:
                    prev["avg_score"] = round_score(
                        (prev["avg_score"] * prev_count + crow.avg_score * crow.count)
                        / new_count,
                    )
                elif crow.avg_score is not None:
                    prev["avg_score"] = round_score(crow.avg_score)
                prev["count"] = new_count
            else:
                strat_map[crow.complexity] = {
                    "count": crow.count,
                    "avg_score": round_score(crow.avg_score),
                }

        # --- New Error Rate Query (E) ---
        # Includes ALL statuses (not just completed) so we can compute error rates.
        error_query = (
            select(
                strategy_col.label("strategy_name"),
                func.count(Opt.id).label("total_count"),
                func.count(Opt.id).filter(
                    Opt.status == OptimizationStatus.ERROR,
                ).label("error_count"),
            )
            .where(strategy_col.isnot(None))
            .group_by(strategy_col)
        )
        if project:
            error_query = error_query.where(Opt.project == project)

        error_result = await self._session.execute(error_query)
        error_rows = error_result.all()

        error_rates: dict[str, dict[str, float | int]] = {}
        for erow in error_rows:
            name = LEGACY_STRATEGY_ALIASES.get(erow.strategy_name, erow.strategy_name)
            if name in error_rates:
                prev = error_rates[name]
                prev["total"] += erow.total_count
                prev["errors"] += erow.error_count
            else:
                error_rates[name] = {
                    "total": erow.total_count,
                    "errors": erow.error_count,
                }
        for name, data in error_rates.items():
            data["rate"] = round(data["errors"] / data["total"], 4) if data["total"] > 0 else 0

        # --- New Time-Trend Query (F) ---
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        trend_query = select(
            func.count(Opt.id).filter(
                Opt.created_at >= seven_days_ago,
            ).label("count_7d"),
            func.avg(Opt.overall_score).filter(
                Opt.created_at >= seven_days_ago,
            ).label("avg_score_7d"),
            func.count(Opt.id).filter(
                Opt.created_at >= thirty_days_ago,
            ).label("count_30d"),
            func.avg(Opt.overall_score).filter(
                Opt.created_at >= thirty_days_ago,
            ).label("avg_score_30d"),
        ).where(completed)
        if project:
            trend_query = trend_query.where(Opt.project == project)

        trend_result = await self._session.execute(trend_query)
        trend_row = trend_result.one()

        trend_7d = {
            "count": trend_row.count_7d or 0,
            "avg_score": round_score(trend_row.avg_score_7d),
        }
        trend_30d = {
            "count": trend_row.count_30d or 0,
            "avg_score": round_score(trend_row.avg_score_30d),
        }

        return {
            "total_optimizations": total,
            "average_overall_score": round_score(row.avg_overall),
            "average_clarity_score": round_score(row.avg_clarity),
            "average_specificity_score": round_score(row.avg_specificity),
            "average_structure_score": round_score(row.avg_structure),
            "average_faithfulness_score": round_score(row.avg_faithfulness),
            "improvement_rate": round_score(imp),
            "total_projects": total_active_projects,
            "most_common_task_type": row.most_common_task,
            "optimizations_today": row.today or 0,
            "strategy_distribution": strategy_distribution or None,
            "score_by_strategy": score_by_strategy or None,
            "task_types_by_strategy": task_types_by_strategy or None,
            "secondary_strategy_distribution": secondary_distribution or None,
            "tags_by_strategy": tags_by_strategy or None,
            # --- New analytics ---
            "score_matrix": score_matrix or None,
            "score_variance": score_variance or None,
            "confidence_by_strategy": confidence_by_strategy or None,
            "combo_effectiveness": combo_effectiveness or None,
            "complexity_performance": complexity_performance or None,
            "improvement_by_strategy": improvement_by_strategy or None,
            "error_rates": error_rates or None,
            "trend_7d": trend_7d,
            "trend_30d": trend_30d,
            "token_economics": token_economics or None,
            "win_rates": win_rates or None,
        }
