"""Tests for per-app document storage endpoints and repository."""

import pytest

from kernel.repositories.app_storage import AppStorageRepository


@pytest.mark.asyncio
class TestAppStorageRepository:
    """CRUD tests for AppStorageRepository."""

    async def test_list_collections_empty(self, db_session):
        repo = AppStorageRepository(db_session)
        result = await repo.list_collections("promptforge")
        assert result == []

    async def test_create_and_list_collection(self, db_session):
        repo = AppStorageRepository(db_session)
        created = await repo.create_collection("promptforge", "notes")
        await db_session.commit()

        assert created["name"] == "notes"
        assert created["app_id"] == "promptforge"

        collections = await repo.list_collections("promptforge")
        assert len(collections) == 1
        assert collections[0]["name"] == "notes"

    async def test_delete_collection(self, db_session):
        repo = AppStorageRepository(db_session)
        created = await repo.create_collection("promptforge", "temp")
        await db_session.commit()

        deleted = await repo.delete_collection("promptforge", created["id"])
        await db_session.commit()
        assert deleted is True

        collections = await repo.list_collections("promptforge")
        assert len(collections) == 0

    async def test_create_and_get_document(self, db_session):
        repo = AppStorageRepository(db_session)
        doc = await repo.create_document(
            "promptforge", "test-doc", '{"key": "value"}',
            content_type="application/json",
        )
        await db_session.commit()

        assert doc["name"] == "test-doc"
        assert doc["content"] == '{"key": "value"}'

        fetched = await repo.get_document("promptforge", doc["id"])
        assert fetched is not None
        assert fetched["name"] == "test-doc"

    async def test_update_document(self, db_session):
        repo = AppStorageRepository(db_session)
        doc = await repo.create_document("promptforge", "doc1", "original")
        await db_session.commit()

        updated = await repo.update_document(
            "promptforge", doc["id"], content="updated"
        )
        await db_session.commit()
        assert updated is not None
        assert updated["content"] == "updated"

    async def test_delete_document(self, db_session):
        repo = AppStorageRepository(db_session)
        doc = await repo.create_document("promptforge", "doc1", "data")
        await db_session.commit()

        deleted = await repo.delete_document("promptforge", doc["id"])
        await db_session.commit()
        assert deleted is True

        fetched = await repo.get_document("promptforge", doc["id"])
        assert fetched is None

    async def test_list_documents_with_collection(self, db_session):
        repo = AppStorageRepository(db_session)
        coll = await repo.create_collection("promptforge", "bucket")
        await repo.create_document(
            "promptforge", "doc-in-bucket", "data",
            collection_id=coll["id"],
        )
        await repo.create_document("promptforge", "doc-outside", "data")
        await db_session.commit()

        # List all
        all_docs = await repo.list_documents("promptforge")
        assert len(all_docs) == 2

        # List filtered by collection
        bucket_docs = await repo.list_documents("promptforge", collection_id=coll["id"])
        assert len(bucket_docs) == 1
        assert bucket_docs[0]["name"] == "doc-in-bucket"

    async def test_isolation_between_apps(self, db_session):
        repo = AppStorageRepository(db_session)
        await repo.create_document("app-a", "doc1", "a-data")
        await repo.create_document("app-b", "doc1", "b-data")
        await db_session.commit()

        a_docs = await repo.list_documents("app-a")
        b_docs = await repo.list_documents("app-b")
        assert len(a_docs) == 1
        assert len(b_docs) == 1
        assert a_docs[0]["content"] == "a-data"
        assert b_docs[0]["content"] == "b-data"


@pytest.mark.asyncio
class TestAppStorageEndpoints:
    """HTTP endpoint tests for /api/kernel/storage."""

    async def test_list_collections_empty(self, client):
        resp = await client.get("/api/kernel/storage/promptforge/collections")
        assert resp.status_code == 200
        assert resp.json()["collections"] == []

    async def test_create_collection(self, client):
        resp = await client.post(
            "/api/kernel/storage/promptforge/collections",
            json={"name": "transforms"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "transforms"

    async def test_create_and_get_document(self, client):
        resp = await client.post(
            "/api/kernel/storage/promptforge/documents",
            json={"name": "doc1", "content": '{"hello": "world"}'},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        resp = await client.get(f"/api/kernel/storage/promptforge/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "doc1"

    async def test_update_document(self, client):
        resp = await client.post(
            "/api/kernel/storage/promptforge/documents",
            json={"name": "doc1", "content": "original"},
        )
        doc_id = resp.json()["id"]

        resp = await client.put(
            f"/api/kernel/storage/promptforge/documents/{doc_id}",
            json={"content": "updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "updated"

    async def test_delete_document(self, client):
        resp = await client.post(
            "/api/kernel/storage/promptforge/documents",
            json={"name": "doc1", "content": "data"},
        )
        doc_id = resp.json()["id"]

        resp = await client.delete(f"/api/kernel/storage/promptforge/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_nonexistent_document(self, client):
        resp = await client.delete("/api/kernel/storage/promptforge/documents/nonexistent")
        assert resp.status_code == 404
