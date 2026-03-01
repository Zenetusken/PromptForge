"""Centralized database access for ProjectSource records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.constants import ProjectStatus
from apps.promptforge.models.project import Project
from apps.promptforge.models.source import MAX_SOURCES_PER_PROJECT, ProjectSource

logger = logging.getLogger(__name__)


class SourceRepository:
    """Encapsulates all DB queries for ProjectSource records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, source_id: str) -> ProjectSource | None:
        stmt = select(ProjectSource).where(ProjectSource.id == source_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(
        self, project_id: str, *, enabled_only: bool = False,
    ) -> list[ProjectSource]:
        stmt = select(ProjectSource).where(
            ProjectSource.project_id == project_id,
        )
        if enabled_only:
            stmt = stmt.where(ProjectSource.enabled.is_(True))
        stmt = stmt.order_by(ProjectSource.order_index)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_by_project_name(self, name: str) -> list[ProjectSource]:
        """Fetch enabled sources by project name (joins projects table).

        Used by ``_resolve_context()`` to attach sources during optimization.
        Excludes deleted projects. When duplicate names exist, uses the most
        recently updated project.
        """
        stmt = (
            select(ProjectSource)
            .join(Project, ProjectSource.project_id == Project.id)
            .where(
                Project.name == name,
                Project.status != ProjectStatus.DELETED,
                ProjectSource.enabled.is_(True),
            )
            .order_by(Project.updated_at.desc(), ProjectSource.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_source_count(self, project_id: str) -> int:
        stmt = select(func.count(ProjectSource.id)).where(
            ProjectSource.project_id == project_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_source_counts(self, project_ids: list[str]) -> dict[str, int]:
        """Batch-fetch source counts for multiple projects in a single query."""
        if not project_ids:
            return {}
        stmt = (
            select(ProjectSource.project_id, func.count(ProjectSource.id))
            .where(ProjectSource.project_id.in_(project_ids))
            .group_by(ProjectSource.project_id)
        )
        result = await self._session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        return {pid: counts.get(pid, 0) for pid in project_ids}

    async def get_total_char_count(self, project_id: str) -> int:
        stmt = select(func.coalesce(func.sum(ProjectSource.char_count), 0)).where(
            ProjectSource.project_id == project_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def create(
        self,
        project_id: str,
        title: str,
        content: str,
        source_type: str = "document",
    ) -> ProjectSource:
        current_count = await self.get_source_count(project_id)
        if current_count >= MAX_SOURCES_PER_PROJECT:
            raise ValueError(
                f"Maximum sources per project ({MAX_SOURCES_PER_PROJECT}) exceeded"
            )

        max_stmt = select(func.max(ProjectSource.order_index)).where(
            ProjectSource.project_id == project_id,
        )
        max_result = await self._session.execute(max_stmt)
        max_order = max_result.scalar()
        next_order = 0 if max_order is None else max_order + 1

        source = ProjectSource(
            project_id=project_id,
            title=title,
            content=content,
            source_type=source_type,
            char_count=len(content),
            order_index=next_order,
        )
        self._session.add(source)
        await self._session.flush()
        return source

    async def update(self, source: ProjectSource, **kwargs) -> ProjectSource:
        for key, value in kwargs.items():
            if hasattr(source, key):
                setattr(source, key, value)
        if "content" in kwargs:
            source.char_count = len(kwargs["content"])
        source.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return source

    async def delete(self, source: ProjectSource) -> None:
        await self._session.delete(source)
        await self._session.flush()

    async def reorder(self, project_id: str, source_ids: list[str]) -> None:
        """Reorder sources by the given ID list."""
        all_stmt = select(ProjectSource).where(
            ProjectSource.project_id == project_id,
        )
        all_result = await self._session.execute(all_stmt)
        all_sources = {s.id: s for s in all_result.scalars().all()}

        unknown = set(source_ids) - set(all_sources)
        if unknown:
            raise ValueError(f"Source IDs not found in project: {unknown}")

        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate source IDs in reorder request")

        missing = set(all_sources) - set(source_ids)
        if missing:
            raise ValueError(f"Reorder must include all sources; missing: {missing}")

        for idx, sid in enumerate(source_ids):
            all_sources[sid].order_index = idx

        await self._session.flush()
