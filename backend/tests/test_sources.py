"""Tests for knowledge sources: repository operations and REST API endpoints."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.models.project import Project
from apps.promptforge.models.source import MAX_SOURCES_PER_PROJECT, ProjectSource
from apps.promptforge.repositories.source import SourceRepository


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSourceRepository:
    async def _create_project(self, session: AsyncSession, name: str = "test-proj") -> Project:
        project = Project(name=name)
        session.add(project)
        await session.flush()
        return project

    async def test_create_source(self, db_session: AsyncSession):
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        source = await repo.create(
            project_id=project.id,
            title="Architecture Doc",
            content="This is the architecture document.",
            source_type="document",
        )
        assert source.id is not None
        assert source.title == "Architecture Doc"
        assert source.char_count == len("This is the architecture document.")
        assert source.enabled is True
        assert source.order_index == 0

    async def test_list_by_project(self, db_session: AsyncSession):
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        await repo.create(project.id, "Doc A", "Content A")
        await repo.create(project.id, "Doc B", "Content B")
        items = await repo.list_by_project(project.id)
        assert len(items) == 2
        assert items[0].title == "Doc A"
        assert items[1].title == "Doc B"

    async def test_list_enabled_only(self, db_session: AsyncSession):
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        src_a = await repo.create(project.id, "Doc A", "Content A")
        await repo.create(project.id, "Doc B", "Content B")
        await repo.update(src_a, enabled=False)

        all_items = await repo.list_by_project(project.id)
        enabled_items = await repo.list_by_project(project.id, enabled_only=True)
        assert len(all_items) == 2
        assert len(enabled_items) == 1
        assert enabled_items[0].title == "Doc B"

    async def test_update_source(self, db_session: AsyncSession):
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        source = await repo.create(project.id, "Original", "Original content")
        updated = await repo.update(source, title="Updated", content="New content")
        assert updated.title == "Updated"
        assert updated.char_count == len("New content")

    async def test_delete_source(self, db_session: AsyncSession):
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        source = await repo.create(project.id, "ToDelete", "Content")
        source_id = source.id
        await repo.delete(source)

        result = await repo.get_by_id(source_id)
        assert result is None

    async def test_max_sources_enforced(self, db_session: AsyncSession):
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        for i in range(MAX_SOURCES_PER_PROJECT):
            await repo.create(project.id, f"Source {i}", f"Content {i}")

        with pytest.raises(ValueError, match="Maximum sources per project"):
            await repo.create(project.id, "One Too Many", "Content")

    async def test_cascade_delete_with_project(self, db_session: AsyncSession):
        """Sources should be deleted when their parent project is deleted."""
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        source = await repo.create(project.id, "Will Cascade", "Content")
        source_id = source.id

        await db_session.delete(project)
        await db_session.flush()

        result = await repo.get_by_id(source_id)
        assert result is None

    async def test_get_enabled_by_project_name(self, db_session: AsyncSession):
        project = await self._create_project(db_session, name="named-proj")
        repo = SourceRepository(db_session)
        await repo.create(project.id, "Enabled Doc", "Content A")
        disabled = await repo.create(project.id, "Disabled Doc", "Content B")
        await repo.update(disabled, enabled=False)

        results = await repo.get_enabled_by_project_name("named-proj")
        assert len(results) == 1
        assert results[0].title == "Enabled Doc"

    async def test_get_source_counts_batch(self, db_session: AsyncSession):
        p1 = await self._create_project(db_session, name="proj-1")
        p2 = await self._create_project(db_session, name="proj-2")
        repo = SourceRepository(db_session)
        await repo.create(p1.id, "Doc A", "Content")
        await repo.create(p1.id, "Doc B", "Content")
        await repo.create(p2.id, "Doc C", "Content")

        counts = await repo.get_source_counts([p1.id, p2.id])
        assert counts[p1.id] == 2
        assert counts[p2.id] == 1

    async def test_reorder_sources(self, db_session: AsyncSession):
        project = await self._create_project(db_session)
        repo = SourceRepository(db_session)
        s1 = await repo.create(project.id, "First", "A")
        s2 = await repo.create(project.id, "Second", "B")
        s3 = await repo.create(project.id, "Third", "C")

        # Reverse order
        await repo.reorder(project.id, [s3.id, s2.id, s1.id])
        items = await repo.list_by_project(project.id)
        assert [s.id for s in items] == [s3.id, s2.id, s1.id]


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSourceAPI:
    async def _create_project_via_api(self, client, name="api-test-proj"):
        resp = await client.post(
            "/api/apps/promptforge/projects",
            json={"name": name},
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_create_endpoint(self, client):
        project = await self._create_project_via_api(client)
        resp = await client.post(
            f"/api/apps/promptforge/projects/{project['id']}/sources",
            json={
                "title": "API Reference",
                "content": "GET /api/users - List all users",
                "source_type": "api_reference",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Reference"
        assert data["source_type"] == "api_reference"
        assert data["char_count"] == len("GET /api/users - List all users")
        assert data["enabled"] is True

    async def test_list_endpoint(self, client):
        project = await self._create_project_via_api(client)
        pid = project["id"]
        await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Doc A", "content": "Content A"},
        )
        await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Doc B", "content": "Content B"},
        )
        resp = await client.get(f"/api/apps/promptforge/projects/{pid}/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_update_endpoint(self, client):
        project = await self._create_project_via_api(client)
        pid = project["id"]
        create_resp = await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Original", "content": "Original content"},
        )
        sid = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/apps/promptforge/projects/{pid}/sources/{sid}",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    async def test_delete_endpoint(self, client):
        project = await self._create_project_via_api(client)
        pid = project["id"]
        create_resp = await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "ToDelete", "content": "Content"},
        )
        sid = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/apps/promptforge/projects/{pid}/sources/{sid}",
        )
        assert resp.status_code == 204

        get_resp = await client.get(
            f"/api/apps/promptforge/projects/{pid}/sources/{sid}",
        )
        assert get_resp.status_code == 404

    async def test_toggle_endpoint(self, client):
        project = await self._create_project_via_api(client)
        pid = project["id"]
        create_resp = await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Toggle Me", "content": "Content"},
        )
        sid = create_resp.json()["id"]
        assert create_resp.json()["enabled"] is True

        resp = await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources/{sid}/toggle",
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        resp2 = await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources/{sid}/toggle",
        )
        assert resp2.json()["enabled"] is True

    async def test_reorder_endpoint(self, client):
        project = await self._create_project_via_api(client)
        pid = project["id"]
        s1 = (await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "First", "content": "A"},
        )).json()
        s2 = (await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Second", "content": "B"},
        )).json()

        resp = await client.put(
            f"/api/apps/promptforge/projects/{pid}/sources/reorder",
            json={"source_ids": [s2["id"], s1["id"]]},
        )
        assert resp.status_code == 200
        assert resp.json()["reordered"] is True

    async def test_archived_project_blocked(self, client):
        project = await self._create_project_via_api(client)
        pid = project["id"]
        # Archive the project
        await client.post(f"/api/apps/promptforge/projects/{pid}/archive")

        resp = await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Blocked", "content": "Should fail"},
        )
        assert resp.status_code == 409

    async def test_project_list_includes_source_count(self, client):
        project = await self._create_project_via_api(client, name="source-count-proj")
        pid = project["id"]
        await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Doc 1", "content": "Content 1"},
        )
        await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Doc 2", "content": "Content 2"},
        )

        resp = await client.get("/api/apps/promptforge/projects")
        assert resp.status_code == 200
        items = resp.json()["items"]
        proj_item = next(i for i in items if i["id"] == pid)
        assert proj_item["source_count"] == 2

    async def test_project_detail_includes_source_count(self, client):
        project = await self._create_project_via_api(client, name="detail-count-proj")
        pid = project["id"]
        await client.post(
            f"/api/apps/promptforge/projects/{pid}/sources",
            json={"title": "Doc 1", "content": "Content 1"},
        )

        resp = await client.get(f"/api/apps/promptforge/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["source_count"] == 1
