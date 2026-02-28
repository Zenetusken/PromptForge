"""Filesystem API — hierarchical folder browsing and node operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_db_readonly
from apps.promptforge.models.optimization import Optimization
from apps.promptforge.repositories.project import ProjectRepository
from apps.promptforge.schemas.filesystem import (
    FsChildrenResponse,
    FsNode,
    FsPathResponse,
    FsTreeResponse,
    MoveRequest,
    MoveResponse,
    PathSegment,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["filesystem"])


def _repo(db: AsyncSession) -> ProjectRepository:
    return ProjectRepository(db)


def _folder_to_node(project) -> FsNode:
    """Convert a Project ORM object to an FsNode."""
    return FsNode(
        id=project.id,
        name=project.name,
        type="folder",
        parent_id=project.parent_id,
        depth=project.depth,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _prompt_to_node(prompt, forge_count: int = 0) -> FsNode:
    """Convert a Prompt ORM object to an FsNode."""
    return FsNode(
        id=prompt.id,
        name=prompt.content[:60].replace("\n", " ") if prompt.content else "Untitled",
        type="prompt",
        parent_id=prompt.project_id,
        depth=0,
        content=prompt.content,
        version=prompt.version,
        forge_count=forge_count if forge_count > 0 else None,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


@router.get("/fs/children", response_model=FsChildrenResponse)
async def get_children(
    parent_id: str | None = Query(None, description="Parent folder ID (null = root)"),
    db: AsyncSession = Depends(get_db_readonly),
):
    """List direct children (folders + prompts) of a folder or root."""
    repo = _repo(db)

    # Validate parent exists if specified
    if parent_id is not None:
        parent = await repo.get_by_id(parent_id, load_prompts=False)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")

    folders, prompts = await repo.get_children(parent_id)

    # Batch-fetch forge counts for prompts
    prompt_ids = [p.id for p in prompts]
    forge_counts: dict[str, int] = {}
    if prompt_ids:
        count_stmt = (
            select(Optimization.prompt_id, sa_func.count(Optimization.id))
            .where(Optimization.prompt_id.in_(prompt_ids))
            .group_by(Optimization.prompt_id)
        )
        count_result = await db.execute(count_stmt)
        forge_counts = {row[0]: row[1] for row in count_result.all()}

    nodes = [_folder_to_node(f) for f in folders] + [
        _prompt_to_node(p, forge_counts.get(p.id, 0)) for p in prompts
    ]

    # Build path breadcrumbs
    path: list[PathSegment] = []
    if parent_id is not None:
        raw_path = await repo.get_path(parent_id)
        path = [PathSegment(id=seg["id"], name=seg["name"]) for seg in raw_path]

    return FsChildrenResponse(nodes=nodes, path=path)


@router.get("/fs/tree", response_model=FsTreeResponse)
async def get_tree(
    root_id: str | None = Query(None, description="Root folder ID (null = full tree)"),
    db: AsyncSession = Depends(get_db_readonly),
):
    """Get a recursive folder tree (folders only, no prompts)."""
    repo = _repo(db)

    if root_id:
        parent = await repo.get_by_id(root_id, load_prompts=False)
        if not parent:
            raise HTTPException(status_code=404, detail="Root folder not found")
        raw = await repo.get_subtree(root_id)
        nodes = [
            FsNode(
                id=n["id"], name=n["name"], type="folder",
                parent_id=n["parent_id"], depth=n["depth"],
            )
            for n in raw
        ]
    else:
        # Return all root-level folders
        folders, _ = await repo.get_children(None)
        nodes = [_folder_to_node(f) for f in folders]

    return FsTreeResponse(nodes=nodes)


@router.get("/fs/path/{project_id}", response_model=FsPathResponse)
async def get_path(
    project_id: str,
    db: AsyncSession = Depends(get_db_readonly),
):
    """Get the ancestor breadcrumb path for a folder."""
    repo = _repo(db)
    project = await repo.get_by_id(project_id, load_prompts=False)
    if not project:
        raise HTTPException(status_code=404, detail="Folder not found")

    raw_path = await repo.get_path(project_id)
    return FsPathResponse(
        segments=[PathSegment(id=seg["id"], name=seg["name"]) for seg in raw_path],
    )


@router.get("/fs/prompt/{prompt_id}", response_model=FsNode)
async def get_prompt_direct(
    prompt_id: str,
    db: AsyncSession = Depends(get_db_readonly),
):
    """Get a single prompt by ID (works for any prompt including desktop/orphan)."""
    repo = _repo(db)
    prompt = await repo.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Fetch forge count
    count_stmt = (
        select(sa_func.count(Optimization.id))
        .where(Optimization.prompt_id == prompt_id)
    )
    count_result = await db.execute(count_stmt)
    forge_count = count_result.scalar() or 0

    return _prompt_to_node(prompt, forge_count)


@router.delete("/fs/prompt/{prompt_id}")
async def delete_prompt_direct(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a prompt by ID (works for any prompt including desktop/orphan)."""
    repo = _repo(db)
    prompt = await repo.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    deleted_count = await repo.delete_prompt(prompt)
    await db.commit()
    return {"success": True, "deleted_optimizations": deleted_count}


@router.post("/fs/move", response_model=MoveResponse)
async def move_node(
    body: MoveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Move a folder or prompt to a new parent (or root)."""
    repo = _repo(db)

    try:
        if body.type == "project":
            project = await repo.move_project(body.id, body.new_parent_id)
            node = _folder_to_node(project)
        else:
            prompt = await repo.move_prompt(body.id, body.new_parent_id)
            node = _prompt_to_node(prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MoveResponse(success=True, node=node)
