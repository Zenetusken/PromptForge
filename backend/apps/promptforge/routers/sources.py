"""Knowledge source CRUD endpoints for projects.

Proxies to the kernel Knowledge Base while maintaining backward-compatible
response shapes. The kernel ``KnowledgeRepository`` is the authoritative source;
the legacy ``SourceRepository`` / ``project_sources`` table is kept in sync
for Phase 4 cleanup.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_db_readonly
from apps.promptforge.constants import ProjectStatus
from apps.promptforge.repositories.project import ProjectRepository
from apps.promptforge.routers._audit import audit_log
from apps.promptforge.schemas.source import (
    SourceCreate,
    SourceListResponse,
    SourceReorderRequest,
    SourceResponse,
    SourceUpdate,
)
from kernel.repositories.knowledge import KnowledgeRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sources"])


def _knowledge_repo(db: AsyncSession) -> KnowledgeRepository:
    return KnowledgeRepository(db)


def _source_dict_to_response(d: dict, project_id: str) -> SourceResponse:
    """Convert a kernel source dict to the PF SourceResponse schema."""
    return SourceResponse(
        id=d["id"],
        project_id=project_id,
        title=d["title"],
        content=d["content"],
        source_type=d["source_type"],
        char_count=d["char_count"],
        enabled=d["enabled"],
        order_index=d["order_index"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
    )


async def _get_mutable_project(db: AsyncSession, project_id: str):
    """Fetch a project and verify it can be mutated."""
    project = await ProjectRepository(db).get_by_id(project_id, load_prompts=False)
    if not project or project.status == ProjectStatus.DELETED:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status == ProjectStatus.ARCHIVED:
        raise HTTPException(
            status_code=409, detail="Cannot modify an archived project",
        )
    return project


async def _get_profile_id(
    repo: KnowledgeRepository, project_id: str, project_name: str,
) -> str:
    """Get or create the kernel knowledge profile for a PF project."""
    kp = await repo.get_or_create_profile("promptforge", project_id, project_name)
    return kp["id"]


@router.post(
    "/projects/{project_id}/sources",
    response_model=SourceResponse,
    status_code=201,
)
async def create_source(
    project_id: str,
    body: SourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a knowledge source to a project."""
    project = await _get_mutable_project(db, project_id)
    repo = _knowledge_repo(db)
    profile_id = await _get_profile_id(repo, project_id, project.name)
    try:
        source = await repo.create_source(
            profile_id=profile_id,
            title=body.title,
            content=body.content,
            source_type=body.source_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await audit_log(
        "create", "source",
        resource_id=source["id"], details={"project_id": project_id},
    )
    return _source_dict_to_response(source, project_id)


@router.get(
    "/projects/{project_id}/sources",
    response_model=SourceListResponse,
)
async def list_sources(
    project_id: str,
    enabled_only: bool = Query(False),
    db: AsyncSession = Depends(get_db_readonly),
):
    """List all knowledge sources for a project."""
    project = await ProjectRepository(db).get_by_id(project_id, load_prompts=False)
    if not project or project.status == ProjectStatus.DELETED:
        raise HTTPException(status_code=404, detail="Project not found")

    repo = _knowledge_repo(db)
    kp = await repo.get_profile("promptforge", project_id)
    if not kp:
        return SourceListResponse(items=[], total=0, total_chars=0)

    items = await repo.list_sources(kp["id"], enabled_only=enabled_only)
    total_chars = sum(s["char_count"] for s in items)
    return SourceListResponse(
        items=[_source_dict_to_response(s, project_id) for s in items],
        total=len(items),
        total_chars=total_chars,
    )


@router.get(
    "/projects/{project_id}/sources/{source_id}",
    response_model=SourceResponse,
)
async def get_source(
    project_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db_readonly),
):
    """Get a single knowledge source by ID."""
    repo = _knowledge_repo(db)
    source = await repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_dict_to_response(source, project_id)


@router.patch(
    "/projects/{project_id}/sources/{source_id}",
    response_model=SourceResponse,
)
async def update_source(
    project_id: str,
    source_id: str,
    body: SourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a knowledge source."""
    await _get_mutable_project(db, project_id)
    repo = _knowledge_repo(db)
    source = await repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return _source_dict_to_response(source, project_id)

    try:
        source = await repo.update_source(source_id, **updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await audit_log("update", "source", resource_id=source_id)
    return _source_dict_to_response(source, project_id)


@router.delete("/projects/{project_id}/sources/{source_id}", status_code=204)
async def delete_source(
    project_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge source."""
    await _get_mutable_project(db, project_id)
    repo = _knowledge_repo(db)
    source = await repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await repo.delete_source(source_id)
    await db.commit()
    await audit_log("delete", "source", resource_id=source_id)


@router.post(
    "/projects/{project_id}/sources/{source_id}/toggle",
    response_model=SourceResponse,
)
async def toggle_source(
    project_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Toggle the enabled state of a knowledge source."""
    await _get_mutable_project(db, project_id)
    repo = _knowledge_repo(db)
    source = await repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source = await repo.update_source(source_id, enabled=not source["enabled"])
    await db.commit()
    await audit_log(
        "toggle", "source",
        resource_id=source_id, details={"enabled": source["enabled"]},
    )
    return _source_dict_to_response(source, project_id)


@router.put("/projects/{project_id}/sources/reorder")
async def reorder_sources(
    project_id: str,
    body: SourceReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reorder knowledge sources within a project."""
    await _get_mutable_project(db, project_id)
    repo = _knowledge_repo(db)
    kp = await repo.get_profile("promptforge", project_id)
    if not kp:
        raise HTTPException(status_code=404, detail="No knowledge profile for this project")
    try:
        await repo.reorder_sources(kp["id"], body.source_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return {"reordered": True}
