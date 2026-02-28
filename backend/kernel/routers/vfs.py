"""Kernel router for VFS — virtual filesystem with folders, files, and versioning."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.repositories.audit import AuditRepository
from kernel.repositories.vfs import VfsRepository
from kernel.security.access import AppContext, check_capability
from kernel.security.dependencies import get_app_context, get_audit_repo

router = APIRouter(prefix="/api/kernel/vfs", tags=["kernel-vfs"])


def _get_repo(session: AsyncSession = Depends(get_db)) -> VfsRepository:
    return VfsRepository(session)


# --- Request schemas ---

class CreateFolderRequest(BaseModel):
    name: str
    parent_id: str | None = None
    metadata: dict | None = None


class CreateFileRequest(BaseModel):
    name: str
    content: str = ""
    folder_id: str | None = None
    content_type: str = "text/plain"
    metadata: dict | None = None


class UpdateFileRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    content_type: str | None = None
    metadata: dict | None = None
    change_source: str | None = None


# --- Children (combined folder + file listing) ---

@router.get("/{app_id}/children")
async def list_children(
    app_id: str,
    parent_id: str | None = None,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
):
    """List child folders and files of a parent folder (or root)."""
    check_capability(ctx, "vfs:read")
    return await repo.list_children(app_id, parent_id=parent_id)


# --- Folders ---

@router.post("/{app_id}/folders", status_code=201)
async def create_folder(
    app_id: str,
    body: CreateFolderRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Create a new folder."""
    check_capability(ctx, "vfs:write")
    try:
        folder = await repo.create_folder(
            app_id, body.name, parent_id=body.parent_id, metadata=body.metadata
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await audit.log_action(app_id, "create", "vfs_folder", resource_id=folder["id"])
    return folder


@router.get("/{app_id}/folders/{folder_id}")
async def get_folder(
    app_id: str,
    folder_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
):
    """Get a folder by ID."""
    check_capability(ctx, "vfs:read")
    folder = await repo.get_folder(app_id, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.delete("/{app_id}/folders/{folder_id}")
async def delete_folder(
    app_id: str,
    folder_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Delete a folder and all contents (cascade)."""
    check_capability(ctx, "vfs:write")
    deleted = await repo.delete_folder(app_id, folder_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Folder not found")
    await audit.log_action(app_id, "delete", "vfs_folder", resource_id=folder_id)
    return {"deleted": True}


@router.get("/{app_id}/folders/{folder_id}/path")
async def get_folder_path(
    app_id: str,
    folder_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
):
    """Get the breadcrumb path from root to a folder."""
    check_capability(ctx, "vfs:read")
    path = await repo.get_path(app_id, folder_id)
    return {"path": path}


# --- Files ---

@router.post("/{app_id}/files", status_code=201)
async def create_file(
    app_id: str,
    body: CreateFileRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Create a new file."""
    check_capability(ctx, "vfs:write")
    file = await repo.create_file(
        app_id, body.name, body.content,
        folder_id=body.folder_id, content_type=body.content_type,
        metadata=body.metadata,
    )
    await audit.log_action(app_id, "create", "vfs_file", resource_id=file["id"])
    return file


@router.get("/{app_id}/files/{file_id}")
async def get_file(
    app_id: str,
    file_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
):
    """Get a file by ID."""
    check_capability(ctx, "vfs:read")
    file = await repo.get_file(app_id, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.put("/{app_id}/files/{file_id}")
async def update_file(
    app_id: str,
    file_id: str,
    body: UpdateFileRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Update a file. Auto-creates a version snapshot when content changes."""
    check_capability(ctx, "vfs:write")
    file = await repo.update_file(
        app_id, file_id,
        name=body.name, content=body.content,
        content_type=body.content_type, metadata=body.metadata,
        change_source=body.change_source,
    )
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    await audit.log_action(app_id, "update", "vfs_file", resource_id=file_id)
    return file


@router.delete("/{app_id}/files/{file_id}")
async def delete_file(
    app_id: str,
    file_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Delete a file and its version history."""
    check_capability(ctx, "vfs:write")
    deleted = await repo.delete_file(app_id, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    await audit.log_action(app_id, "delete", "vfs_file", resource_id=file_id)
    return {"deleted": True}


# --- Versions ---

@router.get("/{app_id}/files/{file_id}/versions")
async def list_file_versions(
    app_id: str,
    file_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
):
    """List all version snapshots for a file."""
    check_capability(ctx, "vfs:read")
    versions = await repo.list_versions(app_id, file_id)
    return {"file_id": file_id, "versions": versions}


# --- Search ---

@router.get("/{app_id}/search")
async def search_files(
    app_id: str,
    q: str = Query(..., min_length=1),
    ctx: AppContext = Depends(get_app_context),
    repo: VfsRepository = Depends(_get_repo),
):
    """Search files by name within an app."""
    check_capability(ctx, "vfs:read")
    results = await repo.search_files(app_id, q)
    return {"app_id": app_id, "query": q, "results": results}
