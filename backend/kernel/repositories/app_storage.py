"""Repository for per-app document storage CRUD."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel.models.app_document import AppCollection, AppDocument


class AppStorageRepository:
    """Data access for the app_collections and app_documents tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Collections ---

    async def list_collections(
        self, app_id: str, parent_id: str | None = None
    ) -> list[dict]:
        """List collections for an app, optionally filtered by parent."""
        query = select(AppCollection).where(AppCollection.app_id == app_id)
        if parent_id:
            query = query.where(AppCollection.parent_id == parent_id)
        else:
            query = query.where(AppCollection.parent_id.is_(None))
        result = await self.session.execute(query.order_by(AppCollection.name))
        return [
            {
                "id": c.id,
                "app_id": c.app_id,
                "name": c.name,
                "parent_id": c.parent_id,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in result.scalars().all()
        ]

    async def create_collection(
        self, app_id: str, name: str, parent_id: str | None = None
    ) -> dict:
        """Create a new collection."""
        now = datetime.now(timezone.utc)
        collection = AppCollection(
            app_id=app_id, name=name, parent_id=parent_id, created_at=now, updated_at=now
        )
        self.session.add(collection)
        await self.session.flush()
        return {
            "id": collection.id,
            "app_id": collection.app_id,
            "name": collection.name,
            "parent_id": collection.parent_id,
            "created_at": collection.created_at.isoformat(),
            "updated_at": collection.updated_at.isoformat(),
        }

    async def delete_collection(self, app_id: str, collection_id: str) -> bool:
        """Delete a collection and its documents (cascade)."""
        result = await self.session.execute(
            delete(AppCollection).where(
                AppCollection.id == collection_id, AppCollection.app_id == app_id
            )
        )
        return result.rowcount > 0

    # --- Documents ---

    async def list_documents(
        self, app_id: str, collection_id: str | None = None
    ) -> list[dict]:
        """List documents for an app, optionally filtered by collection."""
        query = select(AppDocument).where(AppDocument.app_id == app_id)
        if collection_id:
            query = query.where(AppDocument.collection_id == collection_id)
        result = await self.session.execute(query.order_by(AppDocument.created_at.desc()))
        return [self._doc_to_dict(d) for d in result.scalars().all()]

    async def get_document(self, app_id: str, document_id: str) -> dict | None:
        """Get a single document by ID."""
        result = await self.session.execute(
            select(AppDocument).where(
                AppDocument.id == document_id, AppDocument.app_id == app_id
            )
        )
        doc = result.scalar_one_or_none()
        return self._doc_to_dict(doc) if doc else None

    async def create_document(
        self,
        app_id: str,
        name: str,
        content: str,
        *,
        collection_id: str | None = None,
        content_type: str = "application/json",
        metadata: dict | None = None,
    ) -> dict:
        """Create a new document."""
        now = datetime.now(timezone.utc)
        doc = AppDocument(
            app_id=app_id,
            collection_id=collection_id,
            name=name,
            content_type=content_type,
            content=content,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(doc)
        await self.session.flush()
        return self._doc_to_dict(doc)

    async def update_document(
        self,
        app_id: str,
        document_id: str,
        *,
        name: str | None = None,
        content: str | None = None,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        """Update an existing document. Returns None if not found."""
        result = await self.session.execute(
            select(AppDocument).where(
                AppDocument.id == document_id, AppDocument.app_id == app_id
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return None

        if name is not None:
            doc.name = name
        if content is not None:
            doc.content = content
        if content_type is not None:
            doc.content_type = content_type
        if metadata is not None:
            doc.metadata_json = json.dumps(metadata)
        doc.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        return self._doc_to_dict(doc)

    async def delete_document(self, app_id: str, document_id: str) -> bool:
        """Delete a document. Returns True if deleted."""
        result = await self.session.execute(
            delete(AppDocument).where(
                AppDocument.id == document_id, AppDocument.app_id == app_id
            )
        )
        return result.rowcount > 0

    def _doc_to_dict(self, doc: AppDocument) -> dict:
        """Convert a document ORM object to a dict."""
        return {
            "id": doc.id,
            "app_id": doc.app_id,
            "collection_id": doc.collection_id,
            "name": doc.name,
            "content_type": doc.content_type,
            "content": doc.content,
            "metadata": json.loads(doc.metadata_json) if doc.metadata_json else None,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        }
