"""Centralized database access for Project and Prompt records."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import ALLOWED_PROJECT_SORT_FIELDS, ProjectStatus
from app.models.optimization import Optimization
from app.models.project import Project, Prompt, PromptVersion

logger = logging.getLogger(__name__)

_UNSET = object()
"""Sentinel indicating a keyword argument was not provided."""


@dataclass
class ProjectFilters:
    """Filter parameters for listing projects."""

    status: str | None = None
    search: str | None = None


@dataclass
class ProjectPagination:
    """Pagination and sorting parameters."""

    sort: str = "created_at"
    order: str = "desc"
    offset: int = 0
    limit: int = 20


async def ensure_project_by_name(session: AsyncSession, name: str) -> str | None:
    """Get or create a Project by name, returning its ID.

    Returns None if name is empty/blank. Reuses active/archived projects.
    Reactivates soft-deleted projects (name is UNIQUE so we can't create a
    duplicate).
    """
    if not name or not name.strip():
        return None
    name = name.strip()
    stmt = select(Project).where(Project.name == name)
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project:
        if project.status == ProjectStatus.DELETED:
            project.status = ProjectStatus.ACTIVE
            project.updated_at = datetime.now(timezone.utc)
            await session.flush()
        return project.id

    new_project = Project(name=name)
    session.add(new_project)
    await session.flush()
    return new_project.id


async def ensure_prompt_in_project(
    session: AsyncSession, project_id: str, content: str,
) -> str | None:
    """Find or create a Prompt for the given content in a project.

    Returns the Prompt ID. If a prompt with identical content already
    exists in the project, returns its ID (idempotent). Returns None
    if project_id or content is empty.
    """
    if not project_id or not content:
        return None
    # Fast path: exact match
    stmt = select(Prompt.id).where(
        Prompt.project_id == project_id,
        Prompt.content == content,
    ).limit(1)
    result = await session.execute(stmt)
    existing_id = result.scalar_one_or_none()
    if existing_id:
        return existing_id
    # Fuzzy path: strip edges + collapse internal whitespace
    normalized = " ".join(content.split())
    all_stmt = select(Prompt.id, Prompt.content).where(
        Prompt.project_id == project_id,
    )
    all_result = await session.execute(all_stmt)
    for pid, pcontent in all_result.all():
        if " ".join(pcontent.split()) == normalized:
            return pid
    # No match — create new prompt
    max_stmt = select(func.max(Prompt.order_index)).where(
        Prompt.project_id == project_id,
    )
    max_result = await session.execute(max_stmt)
    max_order = max_result.scalar()
    next_order = 0 if max_order is None else max_order + 1
    new_prompt = Prompt(content=content, project_id=project_id, order_index=next_order)
    session.add(new_prompt)
    await session.flush()
    return new_prompt.id


class ProjectRepository:
    """Encapsulates all DB queries for Project and Prompt records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Project CRUD ---

    async def get_by_id(self, project_id: str, *, load_prompts: bool = True) -> Project | None:
        stmt = select(Project).where(Project.id == project_id)
        if load_prompts:
            stmt = stmt.options(selectinload(Project.prompts))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Project | None:
        stmt = select(Project).where(Project.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Project:
        project = Project(**kwargs)
        self._session.add(project)
        await self._session.flush()
        return project

    async def update(
        self,
        project: Project,
        name: str | None = None,
        description: str | None = _UNSET,
    ) -> Project:
        if name is not None:
            project.name = name
        if description is not _UNSET:
            project.description = description
        project.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return project

    async def archive(self, project: Project) -> Project:
        project.status = ProjectStatus.ARCHIVED
        project.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return project

    async def unarchive(self, project: Project) -> Project:
        project.status = ProjectStatus.ACTIVE
        project.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return project

    async def soft_delete(self, project: Project) -> Project:
        project.status = ProjectStatus.DELETED
        project.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return project

    async def list(
        self,
        filters: ProjectFilters | None = None,
        pagination: ProjectPagination | None = None,
    ) -> tuple[list[Project], int]:
        filters = filters or ProjectFilters()
        pagination = pagination or ProjectPagination()

        query = select(Project)
        count_query = select(func.count(Project.id))

        # Exclude deleted by default
        if filters.status:
            query = query.where(Project.status == filters.status)
            count_query = count_query.where(Project.status == filters.status)
        else:
            query = query.where(Project.status != ProjectStatus.DELETED)
            count_query = count_query.where(Project.status != ProjectStatus.DELETED)

        if filters.search:
            escaped = filters.search.replace("%", r"\%").replace("_", r"\_")
            pattern = f"%{escaped}%"
            search_cond = Project.name.ilike(pattern) | Project.description.ilike(pattern)
            query = query.where(search_cond)
            count_query = count_query.where(search_cond)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        # Sorting
        sort_field = pagination.sort
        if sort_field not in ALLOWED_PROJECT_SORT_FIELDS:
            sort_field = "created_at"
        sort_column = getattr(Project, sort_field, Project.created_at)

        if pagination.order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))

        query = query.offset(pagination.offset).limit(pagination.limit)

        result = await self._session.execute(query)
        items = list(result.scalars().all())

        return items, total

    # --- Prompt operations ---

    async def get_prompt_by_id(self, prompt_id: str) -> Prompt | None:
        stmt = select(Prompt).where(Prompt.id == prompt_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_prompt_count(self, project_id: str) -> int:
        stmt = select(func.count(Prompt.id)).where(Prompt.project_id == project_id)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_prompt_counts(self, project_ids: list[str]) -> dict[str, int]:
        """Batch-fetch prompt counts for multiple projects in a single query."""
        if not project_ids:
            return {}
        stmt = (
            select(Prompt.project_id, func.count(Prompt.id))
            .where(Prompt.project_id.in_(project_ids))
            .group_by(Prompt.project_id)
        )
        result = await self._session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        # Ensure every requested ID has an entry (0 for projects with no prompts)
        return {pid: counts.get(pid, 0) for pid in project_ids}

    async def add_prompt(self, project: Project, content: str) -> Prompt:
        max_order = await self._get_max_order(project.id)
        next_order = 0 if max_order is None else max_order + 1
        prompt = Prompt(
            content=content,
            project_id=project.id,
            order_index=next_order,
        )
        self._session.add(prompt)
        project.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return prompt

    async def update_prompt(
        self,
        prompt: Prompt,
        content: str | None = None,
        optimization_id: str | None = None,
    ) -> Prompt:
        if content is not None and content != prompt.content:
            # Snapshot the current (soon-to-be-old) version before overwriting
            snapshot = PromptVersion(
                prompt_id=prompt.id,
                version=prompt.version,
                content=prompt.content,
                optimization_id=optimization_id,
            )
            self._session.add(snapshot)
            logger.info(
                "Snapshotting prompt %s at version %d (optimization_id=%s)",
                prompt.id, prompt.version, optimization_id,
            )
            prompt.content = content
            prompt.version += 1
        prompt.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return prompt

    async def delete_prompt(self, prompt: Prompt) -> int:
        """Delete a prompt and cascade-delete all linked optimizations.

        Returns the number of optimizations that were deleted.
        """
        del_stmt = delete(Optimization).where(Optimization.prompt_id == prompt.id)
        result = await self._session.execute(del_stmt)
        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.info(
                "Deleted %d optimization(s) linked to prompt %s",
                deleted_count,
                prompt.id,
            )
        await self._session.delete(prompt)
        await self._session.flush()
        return deleted_count

    async def reorder_prompts(
        self, project_id: str, prompt_ids: list[str],
    ) -> list[Prompt]:
        """Reorder prompts by the given ID list.

        Raises ValueError if any ID doesn't belong to this project or if
        the count doesn't match all existing prompts.
        """
        # Fetch all prompts belonging to this project
        all_stmt = select(Prompt).where(Prompt.project_id == project_id)
        all_result = await self._session.execute(all_stmt)
        all_prompts = {p.id: p for p in all_result.scalars().all()}

        # Validate: every provided ID must belong to this project
        unknown = set(prompt_ids) - set(all_prompts)
        if unknown:
            raise ValueError(f"Prompt IDs not found in project: {unknown}")

        # Validate: no duplicates
        if len(prompt_ids) != len(set(prompt_ids)):
            raise ValueError("Duplicate prompt IDs in reorder request")

        # Validate: all prompts in the project must be included
        missing = set(all_prompts) - set(prompt_ids)
        if missing:
            raise ValueError(f"Reorder must include all prompts; missing: {missing}")

        ordered: list[Prompt] = []
        for idx, pid in enumerate(prompt_ids):
            prompt = all_prompts[pid]
            prompt.order_index = idx
            ordered.append(prompt)

        await self._session.flush()
        return ordered

    # --- Version history ---

    async def get_prompt_versions(
        self,
        prompt_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[PromptVersion], int]:
        """Return paginated version history for a prompt, newest-first."""
        count_stmt = select(func.count(PromptVersion.id)).where(
            PromptVersion.prompt_id == prompt_id,
        )
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        query = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(desc(PromptVersion.version))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        items = list(result.scalars().all())
        return items, total

    # --- Helpers ---

    async def _get_max_order(self, project_id: str) -> int | None:
        stmt = select(func.max(Prompt.order_index)).where(
            Prompt.project_id == project_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar()
