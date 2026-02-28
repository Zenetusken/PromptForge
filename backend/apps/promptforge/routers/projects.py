"""Project and prompt management endpoints."""

import json
import logging
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.constants import ProjectStatus
from apps.promptforge.converters import deserialize_json_field
from app.database import get_db, get_db_readonly
from apps.promptforge.repositories.optimization import OptimizationRepository
from apps.promptforge.repositories.project import ProjectFilters, ProjectPagination, ProjectRepository
from apps.promptforge.schemas.context import codebase_context_from_dict, context_to_dict
from apps.promptforge.schemas.project import (
    ForgeResultListResponse,
    ForgeResultSummary,
    LatestForgeInfo,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectSummaryResponse,
    ProjectUpdate,
    PromptCreate,
    PromptResponse,
    PromptUpdate,
    PromptVersionListResponse,
    PromptVersionResponse,
    ReorderRequest,
)
from apps.promptforge.services.stats_cache import invalidate_stats_cache

if TYPE_CHECKING:
    from apps.promptforge.models.project import Project

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def _repo(db: AsyncSession) -> ProjectRepository:
    return ProjectRepository(db)


async def _get_mutable_project(
    repo: ProjectRepository,
    project_id: str,
    *,
    load_prompts: bool = False,
) -> "Project":
    """Fetch a project and verify it can be mutated.

    Raises 404 for missing/deleted projects and 403 for archived ones.
    """
    project = await repo.get_by_id(project_id, load_prompts=load_prompts)
    if not project or project.status == ProjectStatus.DELETED:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status == ProjectStatus.ARCHIVED:
        raise HTTPException(status_code=403, detail="Cannot modify an archived project")
    return project


async def _build_prompt_responses(
    db: AsyncSession, prompts: list, *, project_name: str = "",
) -> list[PromptResponse]:
    """Build PromptResponse objects with forge_count and latest_forge injected."""
    prompt_ids = [p.id for p in prompts]
    content_map = (
        {p.id: (p.content, project_name) for p in prompts}
        if project_name
        else None
    )
    opt_repo = OptimizationRepository(db)
    forge_counts = await opt_repo.get_forge_counts(
        prompt_ids, content_map=content_map,
    )
    latest_forges = await opt_repo.get_latest_forge_metadata(
        prompt_ids, content_map=content_map,
    )

    responses: list[PromptResponse] = []
    for p in prompts:
        forge_info: LatestForgeInfo | None = None
        opt = latest_forges.get(p.id)
        if opt:
            forge_info = LatestForgeInfo(
                id=opt.id,
                title=opt.title,
                task_type=opt.task_type,
                complexity=opt.complexity,
                framework_applied=opt.framework_applied,
                overall_score=opt.overall_score,
                is_improvement=opt.is_improvement,
                tags=deserialize_json_field(opt.tags) or [],
                version=opt.version,
            )
        responses.append(
            PromptResponse(
                id=p.id,
                content=p.content,
                version=p.version,
                project_id=p.project_id,
                order_index=p.order_index,
                created_at=p.created_at,
                updated_at=p.updated_at,
                forge_count=forge_counts.get(p.id, 0),
                latest_forge=forge_info,
            )
        )
    return responses


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort: str = Query("created_at"),
    order: Literal["asc", "desc"] = Query("desc"),
    db: AsyncSession = Depends(get_db_readonly),
):
    """List projects with optional filtering, search, and pagination."""
    repo = _repo(db)
    offset = (page - 1) * per_page
    filters = ProjectFilters(status=status, search=search)
    pagination = ProjectPagination(sort=sort, order=order, offset=offset, limit=per_page)

    items, total = await repo.list(filters=filters, pagination=pagination)

    # Single query for all prompt counts instead of N+1
    prompt_counts = await repo.get_prompt_counts([p.id for p in items])

    summaries = [
        ProjectSummaryResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            status=p.status,
            parent_id=p.parent_id,
            depth=p.depth,
            prompt_count=prompt_counts.get(p.id, 0),
            has_context=bool(p.context_profile),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in items
    ]

    return ProjectListResponse(items=summaries, total=total, page=page, per_page=per_page)


@router.post("/projects", response_model=ProjectDetailResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new project. Returns 409 if name already exists.

    If a soft-deleted project with the same name exists, it is reactivated
    with the new description instead of creating a duplicate (UNIQUE constraint).
    """
    repo = _repo(db)

    # Serialize context profile if provided
    ctx_json = None
    if body.context_profile:
        ctx = codebase_context_from_dict(body.context_profile)
        ctx_dict = context_to_dict(ctx)
        ctx_json = json.dumps(ctx_dict) if ctx_dict else None

    # Check name uniqueness within the same parent
    try:
        await repo._validate_name_unique(body.name, body.parent_id)
    except ValueError:
        # Allow reactivating soft-deleted projects at root level
        if body.parent_id is None:
            existing = await repo.get_by_name(body.name)
            if existing and existing.status == ProjectStatus.DELETED:
                project = await repo.update(
                    existing, name=body.name, description=body.description,
                    context_profile=ctx_json,
                )
                await repo.unarchive(project)

                ctx_dict_out = None
                if project.context_profile:
                    try:
                        ctx_dict_out = json.loads(project.context_profile)
                    except (json.JSONDecodeError, TypeError):
                        pass

                invalidate_stats_cache()
                return ProjectDetailResponse(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    context_profile=ctx_dict_out,
                    status=project.status,
                    parent_id=project.parent_id,
                    depth=project.depth,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    prompts=[],
                )
        raise HTTPException(
            status_code=409, detail="A project with this name already exists in this location",
        )

    try:
        project = await repo.create(
            name=body.name, description=body.description,
            context_profile=ctx_json, parent_id=body.parent_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ctx_dict = None
    if project.context_profile:
        try:
            ctx_dict = json.loads(project.context_profile)
        except (json.JSONDecodeError, TypeError):
            pass

    invalidate_stats_cache()
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        context_profile=ctx_dict,
        status=project.status,
        parent_id=project.parent_id,
        depth=project.depth,
        created_at=project.created_at,
        updated_at=project.updated_at,
        prompts=[],
    )


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db_readonly),
):
    """Get full project detail with prompts."""
    repo = _repo(db)
    project = await repo.get_by_id(project_id)
    if not project or project.status == ProjectStatus.DELETED:
        raise HTTPException(status_code=404, detail="Project not found")

    ctx_dict = None
    if project.context_profile:
        try:
            ctx_dict = json.loads(project.context_profile)
        except (json.JSONDecodeError, TypeError):
            pass

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        context_profile=ctx_dict,
        status=project.status,
        parent_id=project.parent_id,
        depth=project.depth,
        created_at=project.created_at,
        updated_at=project.updated_at,
        prompts=await _build_prompt_responses(db, project.prompts, project_name=project.name),
    )


@router.put("/projects/{project_id}", response_model=ProjectDetailResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    if_unmodified_since: str | None = Header(None),
):
    """Update a project. Supports optimistic concurrency via If-Unmodified-Since."""
    repo = _repo(db)
    project = await _get_mutable_project(repo, project_id)

    # Optimistic concurrency check
    if if_unmodified_since:
        try:
            client_ts = parsedate_to_datetime(if_unmodified_since)
            if client_ts.tzinfo is None:
                client_ts = client_ts.replace(tzinfo=timezone.utc)
            server_ts = project.updated_at
            if server_ts.tzinfo is None:
                server_ts = server_ts.replace(tzinfo=timezone.utc)
            # Compare at second precision — HTTP dates truncate microseconds
            if server_ts.replace(microsecond=0) > client_ts.replace(microsecond=0):
                raise HTTPException(
                    status_code=409,
                    detail="Project has been modified since your last read",
                )
        except (ValueError, TypeError):
            pass  # Ignore unparseable header

    # Check name uniqueness within the same parent if changing
    if body.name is not None and body.name != project.name:
        try:
            await repo._validate_name_unique(
                body.name, project.parent_id, exclude_id=project.id,
            )
        except ValueError:
            raise HTTPException(
                status_code=409,
                detail="A project with this name already exists in this location",
            )

    kwargs: dict = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.description is not None:
        kwargs["description"] = body.description
    if "context_profile" in body.model_fields_set:
        # Explicit null clears context; dict sets it; absent key leaves unchanged
        if body.context_profile:
            ctx = codebase_context_from_dict(body.context_profile)
            ctx_dict = context_to_dict(ctx)
            kwargs["context_profile"] = json.dumps(ctx_dict) if ctx_dict else None
        else:
            kwargs["context_profile"] = None

    project = await repo.update(project, **kwargs)
    # Reload to include prompts in response
    reloaded = await repo.get_by_id(project_id)
    if not reloaded:
        raise HTTPException(status_code=404, detail="Project not found")

    ctx_out = None
    if reloaded.context_profile:
        try:
            ctx_out = json.loads(reloaded.context_profile)
        except (json.JSONDecodeError, TypeError):
            pass

    return ProjectDetailResponse(
        id=reloaded.id,
        name=reloaded.name,
        description=reloaded.description,
        context_profile=ctx_out,
        status=reloaded.status,
        parent_id=reloaded.parent_id,
        depth=reloaded.depth,
        created_at=reloaded.created_at,
        updated_at=reloaded.updated_at,
        prompts=await _build_prompt_responses(db, reloaded.prompts, project_name=reloaded.name),
    )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a project and cascade-delete all associated prompts and optimizations."""
    repo = _repo(db)
    project = await repo.get_by_id(project_id, load_prompts=True)
    if not project or project.status == ProjectStatus.DELETED:
        raise HTTPException(status_code=404, detail="Project not found")

    deleted_optimizations = await repo.delete_project_data(project)
    await repo.soft_delete(project)
    invalidate_stats_cache()
    return {
        "message": "Project deleted",
        "id": project_id,
        "deleted_optimizations": deleted_optimizations,
    }


@router.post("/projects/{project_id}/archive")
async def archive_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Archive a project (sets status to 'archived')."""
    repo = _repo(db)
    project = await repo.get_by_id(project_id, load_prompts=False)
    if not project or project.status == ProjectStatus.DELETED:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status == ProjectStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="Project is already archived")

    await repo.archive(project)
    invalidate_stats_cache()
    return {
        "message": "Project archived",
        "id": project_id,
        "status": ProjectStatus.ARCHIVED,
        "updated_at": project.updated_at.isoformat(),
    }


@router.post("/projects/{project_id}/unarchive")
async def unarchive_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Restore an archived project to active status."""
    repo = _repo(db)
    project = await repo.get_by_id(project_id, load_prompts=False)
    if not project or project.status == ProjectStatus.DELETED:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status == ProjectStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Project is already active")

    await repo.unarchive(project)
    invalidate_stats_cache()
    return {
        "message": "Project unarchived",
        "id": project_id,
        "status": ProjectStatus.ACTIVE,
        "updated_at": project.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Prompt CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/prompts",
    response_model=PromptResponse,
    status_code=201,
)
async def add_prompt(
    project_id: str,
    body: PromptCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a prompt to a project."""
    repo = _repo(db)
    project = await _get_mutable_project(repo, project_id)

    prompt = await repo.add_prompt(project, body.content)
    return PromptResponse.model_validate(prompt)


# Register reorder BEFORE the parametric {prompt_id} route
@router.put("/projects/{project_id}/prompts/reorder")
async def reorder_prompts(
    project_id: str,
    body: ReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reorder prompts within a project."""
    repo = _repo(db)
    await _get_mutable_project(repo, project_id)

    try:
        ordered = await repo.reorder_prompts(project_id, body.prompt_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "message": "Prompts reordered",
        "prompts": [PromptResponse.model_validate(p) for p in ordered],
    }


@router.get(
    "/projects/{project_id}/prompts/{prompt_id}/versions",
    response_model=PromptVersionListResponse,
)
async def get_prompt_versions(
    project_id: str,
    prompt_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_readonly),
):
    """Get paginated version history for a prompt."""
    repo = _repo(db)
    prompt = await repo.get_prompt_by_id(prompt_id)
    if not prompt or prompt.project_id != project_id:
        raise HTTPException(status_code=404, detail="Prompt not found")

    items, total = await repo.get_prompt_versions(prompt_id, limit=limit, offset=offset)
    return PromptVersionListResponse(
        items=[PromptVersionResponse.model_validate(v) for v in items],
        total=total,
    )


@router.get(
    "/projects/{project_id}/prompts/{prompt_id}/forges",
    response_model=ForgeResultListResponse,
)
async def get_prompt_forges(
    project_id: str,
    prompt_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_readonly),
):
    """Get paginated forge results linked to a prompt."""
    repo = _repo(db)
    prompt = await repo.get_prompt_by_id(prompt_id)
    if not prompt or prompt.project_id != project_id:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Resolve project name for content-based fallback matching
    project = await repo.get_by_id(project_id, load_prompts=False)
    project_name = project.name if project else ""

    opt_repo = OptimizationRepository(db)
    items, total = await opt_repo.get_by_prompt_id(
        prompt_id, limit=limit, offset=offset,
        prompt_content=prompt.content, project_name=project_name,
    )
    return ForgeResultListResponse(
        items=[
            ForgeResultSummary(
                id=opt.id,
                created_at=opt.created_at,
                overall_score=opt.overall_score,
                framework_applied=opt.framework_applied,
                is_improvement=opt.is_improvement,
                status=opt.status,
                title=opt.title,
                task_type=opt.task_type,
                complexity=opt.complexity,
                tags=deserialize_json_field(opt.tags) or [],
                version=opt.version,
            )
            for opt in items
        ],
        total=total,
    )


@router.put(
    "/projects/{project_id}/prompts/{prompt_id}",
    response_model=PromptResponse,
)
async def update_prompt(
    project_id: str,
    prompt_id: str,
    body: PromptUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a prompt's content. Increments version."""
    repo = _repo(db)
    prompt = await repo.get_prompt_by_id(prompt_id)
    if not prompt or prompt.project_id != project_id:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await _get_mutable_project(repo, project_id)

    prompt = await repo.update_prompt(prompt, content=body.content)
    return PromptResponse.model_validate(prompt)


@router.delete("/projects/{project_id}/prompts/{prompt_id}")
async def delete_prompt(
    project_id: str,
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a prompt from a project (hard delete)."""
    repo = _repo(db)
    prompt = await repo.get_prompt_by_id(prompt_id)
    if not prompt or prompt.project_id != project_id:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await _get_mutable_project(repo, project_id)

    deleted_optimizations = await repo.delete_prompt(prompt)
    if deleted_optimizations:
        invalidate_stats_cache()
    return {
        "message": "Prompt deleted",
        "id": prompt_id,
        "deleted_optimizations": deleted_optimizations,
    }
