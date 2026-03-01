"""Tests for kernel Knowledge Base — profiles, sources, resolution, and REST API."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kernel.repositories.knowledge import KnowledgeRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_profile(
    session: AsyncSession, app_id: str = "promptforge", entity_id: str = "proj-1",
    name: str = "Test Project", **kwargs,
) -> dict:
    repo = KnowledgeRepository(session)
    profile = await repo.get_or_create_profile(app_id, entity_id, name)
    if kwargs:
        profile = await repo.update_profile(profile["id"], **kwargs)
    return profile


async def _seed_source(
    session: AsyncSession, profile_id: str,
    title: str = "Docs", content: str = "Hello world",
    source_type: str = "document",
) -> dict:
    repo = KnowledgeRepository(session)
    return await repo.create_source(profile_id, title, content, source_type)


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

class TestProfileCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_profile(self, db_session):
        repo = KnowledgeRepository(db_session)
        profile = await repo.get_or_create_profile("promptforge", "proj-1", "My Project")

        assert profile["app_id"] == "promptforge"
        assert profile["entity_id"] == "proj-1"
        assert profile["name"] == "My Project"
        assert profile["id"]

        fetched = await repo.get_profile("promptforge", "proj-1")
        assert fetched["id"] == profile["id"]

    @pytest.mark.asyncio
    async def test_get_or_create_is_idempotent(self, db_session):
        repo = KnowledgeRepository(db_session)
        p1 = await repo.get_or_create_profile("app", "e1", "Name")
        p2 = await repo.get_or_create_profile("app", "e1", "Different Name")
        assert p1["id"] == p2["id"]
        assert p2["name"] == "Name"  # original name preserved

    @pytest.mark.asyncio
    async def test_update_profile_fields(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        updated = await repo.update_profile(
            profile["id"], language="Python", framework="FastAPI",
            description="A test project",
        )
        assert updated["language"] == "Python"
        assert updated["framework"] == "FastAPI"
        assert updated["description"] == "A test project"

    @pytest.mark.asyncio
    async def test_update_metadata_json(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        meta = {"conventions": ["snake_case"], "patterns": ["repository"]}
        updated = await repo.update_profile(profile["id"], metadata_json=meta)
        assert updated["metadata"]["conventions"] == ["snake_case"]
        assert updated["metadata"]["patterns"] == ["repository"]

    @pytest.mark.asyncio
    async def test_delete_profile(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        deleted = await repo.delete_profile(profile["id"])
        assert deleted is True

        fetched = await repo.get_profile("promptforge", "proj-1")
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile(self, db_session):
        repo = KnowledgeRepository(db_session)
        deleted = await repo.delete_profile("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_profiles(self, db_session):
        repo = KnowledgeRepository(db_session)
        await repo.get_or_create_profile("app", "e1", "Alpha")
        await repo.get_or_create_profile("app", "e2", "Beta")
        await repo.get_or_create_profile("other", "e3", "Gamma")

        profiles = await repo.list_profiles("app")
        assert len(profiles) == 2
        assert profiles[0]["name"] == "Alpha"
        assert profiles[1]["name"] == "Beta"


# ---------------------------------------------------------------------------
# Auto-detected merge
# ---------------------------------------------------------------------------

class TestResolveProfile:
    @pytest.mark.asyncio
    async def test_manual_wins_over_auto(self, db_session):
        profile = await _seed_profile(db_session, language="Python")
        repo = KnowledgeRepository(db_session)

        await repo.update_auto_detected(profile["id"], {
            "language": "JavaScript",
            "framework": "React",
            "description": "Auto desc",
        })

        resolved = await repo.resolve_profile("promptforge", "proj-1")
        assert resolved["language"] == "Python"  # manual wins
        assert resolved["framework"] == "React"  # auto fallback
        assert resolved["description"] == "Auto desc"  # auto fallback

    @pytest.mark.asyncio
    async def test_auto_fills_empty_fields(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        await repo.update_auto_detected(profile["id"], {
            "language": "TypeScript",
            "test_framework": "vitest",
        })

        resolved = await repo.resolve_profile("promptforge", "proj-1")
        assert resolved["language"] == "TypeScript"
        assert resolved["test_framework"] == "vitest"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent(self, db_session):
        repo = KnowledgeRepository(db_session)
        result = await repo.resolve_profile("app", "nope")
        assert result is None


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------

class TestSourceCRUD:
    @pytest.mark.asyncio
    async def test_create_and_list_sources(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        await repo.create_source(profile["id"], "Doc A", "Content A")
        await repo.create_source(profile["id"], "Doc B", "Content B", "paste")

        sources = await repo.list_sources(profile["id"])
        assert len(sources) == 2
        assert sources[0]["title"] == "Doc A"
        assert sources[0]["order_index"] == 0
        assert sources[1]["title"] == "Doc B"
        assert sources[1]["order_index"] == 1
        assert sources[1]["source_type"] == "paste"

    @pytest.mark.asyncio
    async def test_source_char_count(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        source = await repo.create_source(profile["id"], "Src", "Hello" * 100)
        assert source["char_count"] == 500

    @pytest.mark.asyncio
    async def test_update_source(self, db_session):
        profile = await _seed_profile(db_session)
        source = await _seed_source(db_session, profile["id"])
        repo = KnowledgeRepository(db_session)

        updated = await repo.update_source(source["id"], title="New Title", content="New content")
        assert updated["title"] == "New Title"
        assert updated["content"] == "New content"
        assert updated["char_count"] == len("New content")

    @pytest.mark.asyncio
    async def test_update_nonexistent_source(self, db_session):
        repo = KnowledgeRepository(db_session)
        with pytest.raises(ValueError, match="not found"):
            await repo.update_source("nonexistent", title="X")

    @pytest.mark.asyncio
    async def test_delete_source(self, db_session):
        profile = await _seed_profile(db_session)
        source = await _seed_source(db_session, profile["id"])
        repo = KnowledgeRepository(db_session)

        deleted = await repo.delete_source(source["id"])
        assert deleted is True

        remaining = await repo.list_sources(profile["id"])
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_enabled_filter(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        await repo.create_source(profile["id"], "Enabled", "A")
        s2 = await repo.create_source(profile["id"], "Disabled", "B")
        await repo.update_source(s2["id"], enabled=False)

        all_sources = await repo.list_sources(profile["id"])
        assert len(all_sources) == 2

        enabled = await repo.list_sources(profile["id"], enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0]["title"] == "Enabled"

    @pytest.mark.asyncio
    async def test_max_sources_limit(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        for i in range(50):
            await repo.create_source(profile["id"], f"Source {i}", f"Content {i}")

        with pytest.raises(ValueError, match="Maximum sources"):
            await repo.create_source(profile["id"], "One too many", "X")

    @pytest.mark.asyncio
    async def test_invalid_source_type(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        with pytest.raises(ValueError, match="Invalid source_type"):
            await repo.create_source(profile["id"], "Bad", "Content", "invalid_type")


# ---------------------------------------------------------------------------
# Source reorder
# ---------------------------------------------------------------------------

class TestSourceReorder:
    @pytest.mark.asyncio
    async def test_reorder_sources(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        s1 = await repo.create_source(profile["id"], "A", "a")
        s2 = await repo.create_source(profile["id"], "B", "b")
        s3 = await repo.create_source(profile["id"], "C", "c")

        await repo.reorder_sources(profile["id"], [s3["id"], s1["id"], s2["id"]])

        sources = await repo.list_sources(profile["id"])
        assert [s["title"] for s in sources] == ["C", "A", "B"]

    @pytest.mark.asyncio
    async def test_reorder_unknown_ids(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        with pytest.raises(ValueError, match="not found"):
            await repo.reorder_sources(profile["id"], ["fake-id"])

    @pytest.mark.asyncio
    async def test_reorder_missing_ids(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        s1 = await repo.create_source(profile["id"], "A", "a")
        await repo.create_source(profile["id"], "B", "b")

        with pytest.raises(ValueError, match="missing"):
            await repo.reorder_sources(profile["id"], [s1["id"]])


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------

class TestCascadeDelete:
    @pytest.mark.asyncio
    async def test_delete_profile_cascades_sources(self, db_session):
        profile = await _seed_profile(db_session)
        await _seed_source(db_session, profile["id"], title="S1")
        await _seed_source(db_session, profile["id"], title="S2")
        repo = KnowledgeRepository(db_session)

        await repo.delete_profile(profile["id"])

        # Sources should be gone too
        sources = await repo.list_sources(profile["id"])
        assert len(sources) == 0


# ---------------------------------------------------------------------------
# Combined resolution
# ---------------------------------------------------------------------------

class TestCombinedResolve:
    @pytest.mark.asyncio
    async def test_resolve_returns_profile_and_sources(self, db_session):
        profile = await _seed_profile(
            db_session, language="Python", framework="FastAPI",
        )
        repo = KnowledgeRepository(db_session)
        await repo.update_profile(
            profile["id"],
            metadata_json={"conventions": ["pep8"]},
        )
        await repo.create_source(profile["id"], "API Ref", "GET /users", "api_reference")
        # Disabled source should not appear
        s2 = await repo.create_source(profile["id"], "Draft", "WIP")
        await repo.update_source(s2["id"], enabled=False)

        result = await repo.resolve("promptforge", "proj-1")
        assert result is not None
        assert result["profile"]["language"] == "Python"
        assert result["profile"]["framework"] == "FastAPI"
        assert result["metadata"]["conventions"] == ["pep8"]
        assert len(result["sources"]) == 1
        assert result["sources"][0]["title"] == "API Ref"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent(self, db_session):
        repo = KnowledgeRepository(db_session)
        result = await repo.resolve("app", "nope")
        assert result is None


# ---------------------------------------------------------------------------
# Aggregate queries
# ---------------------------------------------------------------------------

class TestAggregates:
    @pytest.mark.asyncio
    async def test_source_count(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        assert await repo.get_source_count(profile["id"]) == 0

        await repo.create_source(profile["id"], "A", "a")
        await repo.create_source(profile["id"], "B", "bb")

        assert await repo.get_source_count(profile["id"]) == 2

    @pytest.mark.asyncio
    async def test_source_counts_batch(self, db_session):
        p1 = await _seed_profile(db_session, entity_id="proj-1")
        p2 = await _seed_profile(db_session, entity_id="proj-2")
        p3 = await _seed_profile(db_session, entity_id="proj-3")
        repo = KnowledgeRepository(db_session)

        await repo.create_source(p1["id"], "A", "a")
        await repo.create_source(p1["id"], "B", "b")
        await repo.create_source(p2["id"], "C", "c")
        # p3 has no sources

        counts = await repo.get_source_counts([p1["id"], p2["id"], p3["id"]])
        assert counts[p1["id"]] == 2
        assert counts[p2["id"]] == 1
        assert counts[p3["id"]] == 0

    @pytest.mark.asyncio
    async def test_source_counts_batch_empty(self, db_session):
        repo = KnowledgeRepository(db_session)
        assert await repo.get_source_counts([]) == {}

    @pytest.mark.asyncio
    async def test_total_char_count(self, db_session):
        profile = await _seed_profile(db_session)
        repo = KnowledgeRepository(db_session)

        await repo.create_source(profile["id"], "A", "hello")
        await repo.create_source(profile["id"], "B", "world!")

        total = await repo.get_total_char_count(profile["id"])
        assert total == 11  # 5 + 6


# ---------------------------------------------------------------------------
# REST API (router tests)
# ---------------------------------------------------------------------------

class TestKnowledgeAPI:
    @pytest.mark.asyncio
    async def test_resolve_404(self, client):
        resp = await client.get("/api/kernel/knowledge/promptforge/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_upsert_and_resolve(self, client):
        # Create
        resp = await client.put(
            "/api/kernel/knowledge/promptforge/proj-1",
            json={"name": "Test", "language": "Python", "framework": "FastAPI"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["language"] == "Python"

        # Resolve
        resp = await client.get("/api/kernel/knowledge/promptforge/proj-1")
        assert resp.status_code == 200
        assert resp.json()["profile"]["language"] == "Python"

    @pytest.mark.asyncio
    async def test_delete_profile(self, client):
        await client.put(
            "/api/kernel/knowledge/promptforge/ent1",
            json={"name": "X"},
        )
        resp = await client.delete("/api/kernel/knowledge/promptforge/ent1")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = await client.get("/api/kernel/knowledge/promptforge/ent1")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_auto_detected(self, client):
        await client.put(
            "/api/kernel/knowledge/promptforge/e1",
            json={"name": "Proj"},
        )
        resp = await client.post(
            "/api/kernel/knowledge/promptforge/e1/sync",
            json={"auto_detected": {"language": "Rust", "framework": "Actix"}},
        )
        assert resp.status_code == 200

        # Resolve should show auto-detected fields
        resp = await client.get("/api/kernel/knowledge/promptforge/e1")
        assert resp.json()["profile"]["language"] == "Rust"

    @pytest.mark.asyncio
    async def test_source_crud(self, client):
        # Create profile first
        await client.put(
            "/api/kernel/knowledge/promptforge/e1",
            json={"name": "Proj"},
        )

        # Create source
        resp = await client.post(
            "/api/kernel/knowledge/promptforge/e1/sources",
            json={"title": "API Docs", "content": "GET /users", "source_type": "api_reference"},
        )
        assert resp.status_code == 201
        source_id = resp.json()["id"]

        # List sources
        resp = await client.get("/api/kernel/knowledge/promptforge/e1/sources")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        # Update source
        resp = await client.patch(
            f"/api/kernel/knowledge/sources/{source_id}",
            json={"title": "Updated Docs"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Docs"

        # Toggle
        resp = await client.post(f"/api/kernel/knowledge/sources/{source_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        # Delete source
        resp = await client.delete(f"/api/kernel/knowledge/sources/{source_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    @pytest.mark.asyncio
    async def test_source_reorder(self, client):
        await client.put(
            "/api/kernel/knowledge/promptforge/e1",
            json={"name": "Proj"},
        )

        r1 = await client.post(
            "/api/kernel/knowledge/promptforge/e1/sources",
            json={"title": "A", "content": "a"},
        )
        r2 = await client.post(
            "/api/kernel/knowledge/promptforge/e1/sources",
            json={"title": "B", "content": "b"},
        )
        id1 = r1.json()["id"]
        id2 = r2.json()["id"]

        resp = await client.put(
            "/api/kernel/knowledge/promptforge/e1/sources/reorder",
            json={"source_ids": [id2, id1]},
        )
        assert resp.status_code == 200

        # Verify order
        resp = await client.get("/api/kernel/knowledge/promptforge/e1/sources")
        items = resp.json()["items"]
        assert items[0]["id"] == id2
        assert items[1]["id"] == id1

    @pytest.mark.asyncio
    async def test_sync_auto_creates_profile(self, client):
        """Sync endpoint should auto-create profile if it doesn't exist."""
        resp = await client.post(
            "/api/kernel/knowledge/promptforge/new-entity/sync",
            json={"auto_detected": {"language": "Go"}},
        )
        assert resp.status_code == 200

        resp = await client.get("/api/kernel/knowledge/promptforge/new-entity")
        assert resp.status_code == 200
        assert resp.json()["profile"]["language"] == "Go"
