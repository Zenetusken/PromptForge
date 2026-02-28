"""Kernel router for per-app document storage — collections and documents CRUD."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.repositories.app_storage import AppStorageRepository

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
    repo: AppStorageRepository = Depends(_get_repo),
):
    """List collections for an app."""
    collections = await repo.list_collections(app_id, parent_id=parent_id)
    return {"app_id": app_id, "collections": collections}


@router.post("/{app_id}/collections", status_code=201)
async def create_collection(
    app_id: str,
    body: CreateCollectionRequest,
    repo: AppStorageRepository = Depends(_get_repo),
):
    """Create a new collection."""
    collection = await repo.create_collection(
        app_id, body.name, parent_id=body.parent_id
    )
    return collection


@router.delete("/{app_id}/collections/{collection_id}")
async def delete_collection(
    app_id: str,
    collection_id: str,
    repo: AppStorageRepository = Depends(_get_repo),
):
    """Delete a collection and all its documents."""
    deleted = await repo.delete_collection(app_id, collection_id)
    if not deleted:
        raise HTTPException(404, "Collection not found")
    return {"deleted": True}


# --- Documents ---

@router.get("/{app_id}/documents")
async def list_documents(
    app_id: str,
    collection_id: str | None = None,
    repo: AppStorageRepository = Depends(_get_repo),
):
    """List documents for an app, optionally filtered by collection."""
    documents = await repo.list_documents(app_id, collection_id=collection_id)
    return {"app_id": app_id, "documents": documents}


@router.get("/{app_id}/documents/{document_id}")
async def get_document(
    app_id: str,
    document_id: str,
    repo: AppStorageRepository = Depends(_get_repo),
):
    """Get a single document."""
    doc = await repo.get_document(app_id, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("/{app_id}/documents", status_code=201)
async def create_document(
    app_id: str,
    body: CreateDocumentRequest,
    repo: AppStorageRepository = Depends(_get_repo),
):
    """Create a new document."""
    doc = await repo.create_document(
        app_id,
        body.name,
        body.content,
        collection_id=body.collection_id,
        content_type=body.content_type,
        metadata=body.metadata,
    )
    return doc


@router.put("/{app_id}/documents/{document_id}")
async def update_document(
    app_id: str,
    document_id: str,
    body: UpdateDocumentRequest,
    repo: AppStorageRepository = Depends(_get_repo),
):
    """Update a document."""
    doc = await repo.update_document(
        app_id,
        document_id,
        name=body.name,
        content=body.content,
        content_type=body.content_type,
        metadata=body.metadata,
    )
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.delete("/{app_id}/documents/{document_id}")
async def delete_document(
    app_id: str,
    document_id: str,
    repo: AppStorageRepository = Depends(_get_repo),
):
    """Delete a document."""
    deleted = await repo.delete_document(app_id, document_id)
    if not deleted:
        raise HTTPException(404, "Document not found")
    return {"deleted": True}
