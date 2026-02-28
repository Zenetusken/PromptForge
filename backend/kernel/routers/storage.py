"""Kernel router for per-app document storage — collections and documents CRUD."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.repositories.app_storage import AppStorageRepository
from kernel.repositories.audit import AuditRepository
from kernel.security.access import AppContext, check_capability
from kernel.security.dependencies import get_app_context, get_audit_repo

router = APIRouter(prefix="/api/kernel/storage", tags=["kernel-storage"])


def _get_repo(session: AsyncSession = Depends(get_db)) -> AppStorageRepository:
    return AppStorageRepository(session)


# --- Request schemas ---

class CreateCollectionRequest(BaseModel):
    name: str
    parent_id: str | None = None


class CreateDocumentRequest(BaseModel):
    name: str
    content: str
    collection_id: str | None = None
    content_type: str = "application/json"
    metadata: dict | None = None


class UpdateDocumentRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    content_type: str | None = None
    metadata: dict | None = None


# --- Collections ---

@router.get("/{app_id}/collections")
async def list_collections(
    app_id: str,
    parent_id: str | None = None,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
):
    """List collections for an app."""
    check_capability(ctx, "storage:read")
    collections = await repo.list_collections(app_id, parent_id=parent_id)
    return {"app_id": app_id, "collections": collections}


@router.post("/{app_id}/collections", status_code=201)
async def create_collection(
    app_id: str,
    body: CreateCollectionRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Create a new collection."""
    check_capability(ctx, "storage:write")
    collection = await repo.create_collection(
        app_id, body.name, parent_id=body.parent_id
    )
    await audit.log_action(app_id, "create", "collection", resource_id=collection["id"])
    return collection


@router.delete("/{app_id}/collections/{collection_id}")
async def delete_collection(
    app_id: str,
    collection_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Delete a collection and all its documents."""
    check_capability(ctx, "storage:write")
    deleted = await repo.delete_collection(app_id, collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    await audit.log_action(app_id, "delete", "collection", resource_id=collection_id)
    return {"deleted": True}


# --- Documents ---

@router.get("/{app_id}/documents")
async def list_documents(
    app_id: str,
    collection_id: str | None = None,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
):
    """List documents for an app, optionally filtered by collection."""
    check_capability(ctx, "storage:read")
    documents = await repo.list_documents(app_id, collection_id=collection_id)
    return {"app_id": app_id, "documents": documents}


@router.get("/{app_id}/documents/{document_id}")
async def get_document(
    app_id: str,
    document_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
):
    """Get a single document."""
    check_capability(ctx, "storage:read")
    doc = await repo.get_document(app_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/{app_id}/documents", status_code=201)
async def create_document(
    app_id: str,
    body: CreateDocumentRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Create a new document."""
    check_capability(ctx, "storage:write")
    doc = await repo.create_document(
        app_id,
        body.name,
        body.content,
        collection_id=body.collection_id,
        content_type=body.content_type,
        metadata=body.metadata,
    )
    await audit.log_action(app_id, "create", "document", resource_id=doc["id"])
    return doc


@router.put("/{app_id}/documents/{document_id}")
async def update_document(
    app_id: str,
    document_id: str,
    body: UpdateDocumentRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Update a document."""
    check_capability(ctx, "storage:write")
    doc = await repo.update_document(
        app_id,
        document_id,
        name=body.name,
        content=body.content,
        content_type=body.content_type,
        metadata=body.metadata,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await audit.log_action(app_id, "update", "document", resource_id=document_id)
    return doc


@router.delete("/{app_id}/documents/{document_id}")
async def delete_document(
    app_id: str,
    document_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: AppStorageRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Delete a document."""
    check_capability(ctx, "storage:write")
    deleted = await repo.delete_document(app_id, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await audit.log_action(app_id, "delete", "document", resource_id=document_id)
    return {"deleted": True}
