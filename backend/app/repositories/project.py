"""Centralized database access for Project and Prompt records."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import ALLOWED_PROJECT_SORT_FIELDS, MAX_FOLDER_DEPTH, ProjectStatus
from app.models.optimization import Optimization
from app.models.project import Project, Prompt, PromptVersion
from app.schemas.context import CodebaseContext, context_from_json

logger = logging.getLogger(__name__)

_UNSET = object()
"""Sentinel indicating a keyword argument was not provided."""


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """Lightweight result from ensure_project_by_name — avoids a second query."""

    id: str
    status: str


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


async def ensure_project_by_name(session: AsyncSession, name: str) -> ProjectInfo | None:
    """Get or create a root-level Project by name, returning its ID and status.

    Returns None if name is empty/blank. Reuses active/archived projects.
    Reactivates soft-deleted projects.  Only matches root-level projects
    (parent_id IS NULL) for MCP backward compatibility — subfolders with
    the same name are ignored.
    """
    if not name or not name.strip():
        return None
    name = name.strip()
    stmt = select(Project).where(
        Project.name == name,
        Project.parent_id.is_(None),
    )
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project:
        if project.status == ProjectStatus.DELETED:
            project.status = ProjectStatus.ACTIVE
            project.updated_at = datetime.now(timezone.utc)
            await session.flush()
        return ProjectInfo(id=project.id, status=project.status)

    new_project = Project(name=name)
    session.add(new_project)
    await session.flush()
    return ProjectInfo(id=new_project.id, status=new_project.status)


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
    # SQL-side normalization handles common whitespace differences
    fuzzy_stmt = select(Prompt.id).where(
        Prompt.project_id == project_id,
        func.trim(func.replace(func.replace(func.replace(
            Prompt.content, '\n', ' '), '\t', ' '), '  ', ' ')) == normalized,
    ).limit(1)
    fuzzy_result = await session.execute(fuzzy_stmt)
    fuzzy_id = fuzzy_result.scalar_one_or_none()
    if fuzzy_id:
        return fuzzy_id
    # Final fallback: Python-side normalization with safety limit
    all_stmt = select(Prompt.id, Prompt.content).where(
        Prompt.project_id == project_id,
    ).limit(100)
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
        """Find a root-level project by name (parent_id IS NULL)."""
        stmt = select(Project).where(
            Project.name == name,
            Project.parent_id.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Project:
        parent_id = kwargs.get("parent_id")
        if parent_id:
            parent = await self.get_by_id(parent_id, load_prompts=False)
            if not parent:
                raise ValueError(f"Parent folder {parent_id!r} not found")
            if parent.depth + 1 > MAX_FOLDER_DEPTH:
                raise ValueError(
                    f"Maximum folder depth ({MAX_FOLDER_DEPTH}) exceeded"
                )
            kwargs["depth"] = parent.depth + 1
        else:
            kwargs.setdefault("depth", 0)

        # Validate name uniqueness within parent
        name = kwargs.get("name")
        if name:
            await self._validate_name_unique(name, parent_id)

        project = Project(**kwargs)
        self._session.add(project)
        await self._session.flush()
        return project

    async def update(
        self,
        project: Project,
        name: str | None = None,
        description: str | None = _UNSET,
        context_profile: str | None = _UNSET,
    ) -> Project:
        if name is not None:
            project.name = name
        if description is not _UNSET:
            project.description = description
        if context_profile is not _UNSET:
            project.context_profile = context_profile
        project.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return project

    async def get_context_by_name(self, name: str) -> CodebaseContext | None:
        """Fetch a project's context profile by name (lightweight, no joins).

        Injects ``Project.description`` as a fallback for
        ``CodebaseContext.description`` when the context profile doesn't
        already provide one, so the LLM knows what the project is about
        without requiring users to duplicate their description into the
        context profile.
        """
        stmt = select(Project.context_profile, Project.description).where(
            Project.name == name,
            Project.parent_id.is_(None),
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        ctx_json, project_description = row
        ctx = context_from_json(ctx_json)
        # Inject project description as fallback for CodebaseContext.description
        if project_description:
            if ctx is None:
                ctx = CodebaseContext(description=project_description)
            elif not ctx.description:
                ctx.description = project_description
        return ctx

    async def archive(self, project: Project) -> Project:
        """Archive a project and all its child folders recursively."""
        await self._cascade_status(project, ProjectStatus.ARCHIVED)
        return project

    async def unarchive(self, project: Project) -> Project:
        """Unarchive a project and all its child folders recursively."""
        await self._cascade_status(project, ProjectStatus.ACTIVE)
        return project

    async def soft_delete(self, project: Project) -> Project:
        project.status = ProjectStatus.DELETED
        project.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return project

    async def _cascade_status(
        self, project: Project, status: str,
    ) -> None:
        """Set status on a project and all descendant folders."""
        now = datetime.now(timezone.utc)
        project.status = status
        project.updated_at = now

        child_stmt = select(Project).where(
            Project.parent_id == project.id,
            Project.status != ProjectStatus.DELETED,
        )
        child_result = await self._session.execute(child_stmt)
        for child in child_result.scalars().all():
            await self._cascade_status(child, status)

        await self._session.flush()

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
        """Delete a prompt and cascade-delete all related optimizations.

        Deletes optimizations linked via prompt_id FK, plus any unlinked
        optimizations in the same project whose raw_prompt matches the
        prompt content (prevents startup backfill from resurrecting the
        deleted prompt).

        Returns the number of optimizations that were deleted.
        """
        # 1. Delete optimizations linked via FK
        del_linked = delete(Optimization).where(Optimization.prompt_id == prompt.id)
        result_linked = await self._session.execute(del_linked)
        deleted_count = result_linked.rowcount or 0

        # 2. Delete unlinked optimizations with matching content in same project
        project_name_stmt = select(Project.name).where(Project.id == prompt.project_id)
        project_name_result = await self._session.execute(project_name_stmt)
        project_name = project_name_result.scalar_one_or_none()
        if project_name:
            del_orphans = (
                delete(Optimization)
                .where(
                    Optimization.prompt_id.is_(None),
                    Optimization.project == project_name,
                    Optimization.raw_prompt == prompt.content,
                )
            )
            result_orphans = await self._session.execute(del_orphans)
            deleted_count += result_orphans.rowcount or 0

        if deleted_count > 0:
            logger.info(
                "Deleted %d optimization(s) for prompt %s",
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

    # --- Filesystem operations ---

    async def get_children(
        self, parent_id: str | None,
    ) -> tuple[list[Project], list[Prompt]]:
        """Return direct child folders and prompts under *parent_id*.

        ``None`` means root level (desktop).
        """
        if parent_id is None:
            folder_stmt = (
                select(Project)
                .where(Project.parent_id.is_(None), Project.status != ProjectStatus.DELETED)
                .order_by(Project.name)
            )
            prompt_stmt = (
                select(Prompt)
                .where(Prompt.project_id.is_(None))
                .order_by(Prompt.order_index)
            )
        else:
            folder_stmt = (
                select(Project)
                .where(Project.parent_id == parent_id, Project.status != ProjectStatus.DELETED)
                .order_by(Project.name)
            )
            prompt_stmt = (
                select(Prompt)
                .where(Prompt.project_id == parent_id)
                .order_by(Prompt.order_index)
            )

        folder_result = await self._session.execute(folder_stmt)
        folders = list(folder_result.scalars().all())
        prompt_result = await self._session.execute(prompt_stmt)
        prompts = list(prompt_result.scalars().all())
        return folders, prompts

    async def get_subtree(
        self, root_id: str, max_depth: int = MAX_FOLDER_DEPTH,
    ) -> list[dict]:
        """Return the recursive subtree rooted at *root_id* via CTE."""
        cte_sql = text("""
            WITH RECURSIVE tree AS (
                SELECT id, name, parent_id, depth, status, 0 AS level
                FROM projects
                WHERE id = :root_id AND status != 'deleted'
                UNION ALL
                SELECT p.id, p.name, p.parent_id, p.depth, p.status, t.level + 1
                FROM projects p
                JOIN tree t ON p.parent_id = t.id
                WHERE p.status != 'deleted' AND t.level < :max_depth
            )
            SELECT id, name, parent_id, depth, status, level FROM tree
            ORDER BY level, name
        """)
        result = await self._session.execute(
            cte_sql, {"root_id": root_id, "max_depth": max_depth},
        )
        return [
            {
                "id": row[0], "name": row[1], "parent_id": row[2],
                "depth": row[3], "status": row[4], "level": row[5],
            }
            for row in result.fetchall()
        ]

    async def get_path(self, project_id: str) -> list[dict]:
        """Return ancestor chain from root to *project_id* (inclusive)."""
        cte_sql = text("""
            WITH RECURSIVE path AS (
                SELECT id, name, parent_id, depth
                FROM projects WHERE id = :pid
                UNION ALL
                SELECT p.id, p.name, p.parent_id, p.depth
                FROM projects p
                JOIN path pa ON pa.parent_id = p.id
            )
            SELECT id, name FROM path ORDER BY depth ASC
        """)
        result = await self._session.execute(cte_sql, {"pid": project_id})
        return [{"id": row[0], "name": row[1]} for row in result.fetchall()]

    async def move_project(
        self, project_id: str, new_parent_id: str | None,
    ) -> Project:
        """Move a folder to a new parent (or root if *new_parent_id* is None).

        Validates: target exists, no circular refs, depth limit, name uniqueness.
        """
        project = await self.get_by_id(project_id, load_prompts=False)
        if not project:
            raise ValueError("Project not found")

        # Validate target parent
        new_depth = 0
        if new_parent_id is not None:
            if new_parent_id == project_id:
                raise ValueError("Cannot move folder into itself")
            parent = await self.get_by_id(new_parent_id, load_prompts=False)
            if not parent:
                raise ValueError("Target parent not found")
            new_depth = parent.depth + 1
            # Check for circular reference
            await self._validate_no_circular_ref(project_id, new_parent_id)

        # Check depth limit for subtree
        subtree = await self.get_subtree(project_id)
        subtree_max_relative = max((n["depth"] - project.depth for n in subtree), default=0)
        if new_depth + subtree_max_relative > MAX_FOLDER_DEPTH:
            raise ValueError(
                f"Move would exceed maximum folder depth ({MAX_FOLDER_DEPTH})"
            )

        # Check name uniqueness in new parent
        await self._validate_name_unique(project.name, new_parent_id, exclude_id=project_id)

        # Apply the move
        depth_delta = new_depth - project.depth
        project.parent_id = new_parent_id
        project.depth = new_depth
        project.updated_at = datetime.now(timezone.utc)

        # Flush the project's own changes to DB before raw SQL subtree updates
        await self._session.flush()

        # Recompute depth for entire subtree via raw SQL
        if depth_delta != 0:
            for node in subtree:
                if node["id"] != project_id:
                    await self._session.execute(
                        text(
                            "UPDATE projects SET depth = depth + :delta"
                            " WHERE id = :nid"
                        ),
                        {"delta": depth_delta, "nid": node["id"]},
                    )
            # Expire ORM cache so subsequent reads reflect raw SQL depth changes.
            self._session.expire_all()
            await self._session.refresh(project)

        return project

    async def move_prompt(
        self, prompt_id: str, new_project_id: str | None,
    ) -> Prompt:
        """Move a prompt to a different folder (or desktop if None)."""
        prompt = await self.get_prompt_by_id(prompt_id)
        if not prompt:
            raise ValueError("Prompt not found")
        if new_project_id is not None:
            parent = await self.get_by_id(new_project_id, load_prompts=False)
            if not parent:
                raise ValueError("Target folder not found")
        prompt.project_id = new_project_id
        prompt.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return prompt

    async def _validate_no_circular_ref(
        self, project_id: str, target_parent_id: str,
    ) -> None:
        """Ensure moving *project_id* under *target_parent_id* won't loop."""
        cte_sql = text("""
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_id FROM projects WHERE id = :target
                UNION ALL
                SELECT p.id, p.parent_id
                FROM projects p
                JOIN ancestors a ON a.parent_id = p.id
            )
            SELECT 1 FROM ancestors WHERE id = :source LIMIT 1
        """)
        result = await self._session.execute(
            cte_sql, {"target": target_parent_id, "source": project_id},
        )
        if result.scalar() is not None:
            raise ValueError("Circular reference: target is a descendant of source")

    async def _validate_name_unique(
        self, name: str, parent_id: str | None, *, exclude_id: str | None = None,
    ) -> None:
        """Ensure *name* is unique within *parent_id*."""
        if parent_id is None:
            stmt = select(Project.id).where(
                Project.name == name,
                Project.parent_id.is_(None),
                Project.status != ProjectStatus.DELETED,
            )
        else:
            stmt = select(Project.id).where(
                Project.name == name,
                Project.parent_id == parent_id,
                Project.status != ProjectStatus.DELETED,
            )
        if exclude_id:
            stmt = stmt.where(Project.id != exclude_id)
        result = await self._session.execute(stmt)
        if result.scalar() is not None:
            raise ValueError(
                f"A folder named {name!r} already exists in this location"
            )

    # --- Cascade deletion ---

    async def delete_project_data(self, project: Project) -> int:
        """Delete all prompts, child folders, and associated optimizations for a project.

        Recursively deletes child folders first (depth-first), then handles the
        project's own prompts and legacy optimizations.

        Returns the total number of optimizations deleted.
        """
        deleted_total = 0

        # 1. Recursively delete child folders (depth-first)
        child_stmt = select(Project).where(
            Project.parent_id == project.id,
            Project.status != ProjectStatus.DELETED,
        )
        child_result = await self._session.execute(child_stmt)
        children = list(child_result.scalars().all())
        for child in children:
            # Load prompts for each child
            child_with_prompts = await self.get_by_id(child.id, load_prompts=True)
            if child_with_prompts:
                deleted_total += await self.delete_project_data(child_with_prompts)
                child_with_prompts.status = ProjectStatus.DELETED
                child_with_prompts.updated_at = datetime.now(timezone.utc)

        # 2. Delete each prompt (cascades its optimizations + versions)
        if project.prompts:
            for prompt in list(project.prompts):
                deleted_total += await self.delete_prompt(prompt)

        # 3. Catch-all: legacy optimizations referencing this project by name
        #    that weren't linked to any prompt (prompt_id IS NULL)
        del_legacy = (
            delete(Optimization)
            .where(
                Optimization.prompt_id.is_(None),
                Optimization.project == project.name,
            )
        )
        result = await self._session.execute(del_legacy)
        deleted_total += result.rowcount or 0

        if deleted_total > 0:
            logger.info(
                "Cascade-deleted %d optimization(s) for project %s (%s)",
                deleted_total,
                project.id,
                project.name,
            )

        return deleted_total

    # --- Helpers ---

    async def _get_max_order(self, project_id: str) -> int | None:
        stmt = select(func.max(Prompt.order_index)).where(
            Prompt.project_id == project_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar()
