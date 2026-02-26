"""Tests for the projects router — HTTP-level coverage for all project and prompt endpoints.

Archive mutation guards (403) are tested in test_archive_guards.py and not duplicated here.
"""

import json

import pytest

from app.constants import OptimizationStatus
from app.database import get_db
from app.main import app
from app.models.optimization import Optimization
from app.models.project import Project, Prompt, PromptVersion
from app.repositories.project import ProjectRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_project(client, *, project_id: str = "proj-1", name: str = "TestProject",
                        description: str | None = None, status: str = "active") -> str:
    """Insert a Project record via the test DB session."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()
    proj = Project(id=project_id, name=name, description=description, status=status)
    session.add(proj)
    await session.flush()
    await session.commit()
    return project_id


async def _seed_prompt(client, *, prompt_id: str = "prm-1", project_id: str = "proj-1",
                       content: str = "test prompt", order_index: int = 0,
                       version: int = 1) -> str:
    """Insert a Prompt record via the test DB session."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()
    prompt = Prompt(id=prompt_id, project_id=project_id, content=content,
                    order_index=order_index, version=version)
    session.add(prompt)
    await session.flush()
    await session.commit()
    return prompt_id


async def _seed_prompt_version(client, *, version_id: str = "ver-1", prompt_id: str = "prm-1",
                               version: int = 1, content: str = "old content",
                               optimization_id: str | None = None) -> str:
    """Insert a PromptVersion record via the test DB session."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()
    pv = PromptVersion(id=version_id, prompt_id=prompt_id, version=version,
                       content=content, optimization_id=optimization_id)
    session.add(pv)
    await session.flush()
    await session.commit()
    return version_id


async def _seed_optimization(client, *, opt_id: str = "opt-1", raw_prompt: str = "test prompt",
                             project: str | None = None, prompt_id: str | None = None,
                             status: str = OptimizationStatus.COMPLETED,
                             overall_score: float = 0.8,
                             framework_applied: str = "chain-of-thought") -> str:
    """Insert an Optimization record via the test DB session."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()
    opt = Optimization(id=opt_id, raw_prompt=raw_prompt, project=project,
                       prompt_id=prompt_id, status=status,
                       overall_score=overall_score,
                       framework_applied=framework_applied,
                       task_type="coding")
    session.add(opt)
    await session.flush()
    await session.commit()
    return opt_id


# ---------------------------------------------------------------------------
# Project List
# ---------------------------------------------------------------------------

class TestListProjects:
    @pytest.mark.asyncio
    async def test_empty_list(self, client):
        resp = await client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_returns_projects(self, client):
        await _seed_project(client, project_id="p1", name="Alpha")
        await _seed_project(client, project_id="p2", name="Beta")
        resp = await client.get("/api/projects")
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_pagination(self, client):
        for i in range(5):
            await _seed_project(client, project_id=f"p{i}", name=f"Project {i}")
        resp = await client.get("/api/projects?page=2&per_page=2")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 2
        assert data["per_page"] == 2

    @pytest.mark.asyncio
    async def test_search_filter(self, client):
        await _seed_project(client, project_id="p1", name="PromptForge")
        await _seed_project(client, project_id="p2", name="OtherApp")
        resp = await client.get("/api/projects?search=Forge")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "PromptForge"

    @pytest.mark.asyncio
    async def test_search_matches_description(self, client):
        await _seed_project(client, project_id="p1", name="A",
                            description="machine learning project")
        await _seed_project(client, project_id="p2", name="B", description="web app")
        resp = await client.get("/api/projects?search=machine")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "A"

    @pytest.mark.asyncio
    async def test_status_filter(self, client):
        await _seed_project(client, project_id="p1", name="Active", status="active")
        await _seed_project(client, project_id="p2", name="Archived", status="archived")
        resp = await client.get("/api/projects?status=active")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Active"

    @pytest.mark.asyncio
    async def test_deleted_excluded_by_default(self, client):
        await _seed_project(client, project_id="p1", name="Visible")
        await _seed_project(client, project_id="p2", name="Gone", status="deleted")
        resp = await client.get("/api/projects")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Visible"

    @pytest.mark.asyncio
    async def test_sort_ascending(self, client):
        await _seed_project(client, project_id="p1", name="AAA")
        await _seed_project(client, project_id="p2", name="ZZZ")
        resp = await client.get("/api/projects?sort=name&order=asc")
        data = resp.json()
        names = [item["name"] for item in data["items"]]
        assert names == ["AAA", "ZZZ"]

    @pytest.mark.asyncio
    async def test_prompt_count_in_response(self, client):
        await _seed_project(client, project_id="p1", name="WithPrompts")
        await _seed_prompt(client, prompt_id="prm-a", project_id="p1", content="a")
        await _seed_prompt(client, prompt_id="prm-b", project_id="p1", content="b")
        resp = await client.get("/api/projects")
        data = resp.json()
        assert data["items"][0]["prompt_count"] == 2


# ---------------------------------------------------------------------------
# Project Create
# ---------------------------------------------------------------------------

class TestCreateProject:
    @pytest.mark.asyncio
    async def test_create_success(self, client):
        resp = await client.post("/api/projects", json={"name": "New Project"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Project"
        assert data["status"] == "active"
        assert data["prompts"] == []
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_with_description(self, client):
        resp = await client.post(
            "/api/projects",
            json={"name": "Described", "description": "A great project"},
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "A great project"

    @pytest.mark.asyncio
    async def test_duplicate_name_returns_409(self, client):
        await _seed_project(client, project_id="p1", name="Taken")
        resp = await client.post("/api/projects", json={"name": "Taken"})
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_duplicate_name_of_deleted_project_succeeds(self, client):
        await _seed_project(client, project_id="p1", name="Recycled", status="deleted")
        resp = await client.post("/api/projects", json={"name": "Recycled"})
        # Should succeed since the existing one is soft-deleted
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_empty_name_rejected(self, client):
        resp = await client.post("/api/projects", json={"name": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_whitespace_name_rejected(self, client):
        resp = await client.post("/api/projects", json={"name": "   "})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_name_whitespace_stripped(self, client):
        resp = await client.post("/api/projects", json={"name": "  Trimmed  "})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Trimmed"


# ---------------------------------------------------------------------------
# Project Get Detail
# ---------------------------------------------------------------------------

class TestGetProject:
    @pytest.mark.asyncio
    async def test_get_existing(self, client):
        await _seed_project(client, project_id="p1", name="Detail",
                            description="desc here")
        resp = await client.get("/api/projects/p1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Detail"
        assert data["description"] == "desc here"
        assert data["status"] == "active"
        assert "prompts" in data

    @pytest.mark.asyncio
    async def test_get_with_prompts(self, client):
        await _seed_project(client, project_id="p1", name="WithP")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="first prompt")
        resp = await client.get("/api/projects/p1")
        data = resp.json()
        assert len(data["prompts"]) == 1
        assert data["prompts"][0]["content"] == "first prompt"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client):
        resp = await client.get("/api/projects/no-such-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_deleted_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="Deleted", status="deleted")
        resp = await client.get("/api/projects/p1")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_archived_allowed(self, client):
        """Archived projects are readable — only mutations are blocked."""
        await _seed_project(client, project_id="p1", name="Frozen", status="archived")
        resp = await client.get("/api/projects/p1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"


# ---------------------------------------------------------------------------
# Project Update
# ---------------------------------------------------------------------------

class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_update_name(self, client):
        await _seed_project(client, project_id="p1", name="OldName")
        resp = await client.put("/api/projects/p1", json={"name": "NewName"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    @pytest.mark.asyncio
    async def test_update_description(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.put("/api/projects/p1", json={"description": "updated desc"})
        assert resp.status_code == 200
        assert resp.json()["description"] == "updated desc"

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self, client):
        resp = await client.put("/api/projects/no-such", json={"name": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_deleted_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="Gone", status="deleted")
        resp = await client.put("/api/projects/p1", json={"name": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_name_to_existing_returns_409(self, client):
        await _seed_project(client, project_id="p1", name="Original")
        await _seed_project(client, project_id="p2", name="Taken")
        resp = await client.put("/api/projects/p1", json={"name": "Taken"})
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_name_to_same_succeeds(self, client):
        """Renaming to the same name should not trigger a conflict."""
        await _seed_project(client, project_id="p1", name="Same")
        resp = await client.put("/api/projects/p1", json={"name": "Same"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_optimistic_concurrency_conflict(self, client):
        """If-Unmodified-Since header triggers 409 when project was modified."""
        await _seed_project(client, project_id="p1", name="Concurrent")
        # First update — succeeds
        resp1 = await client.put("/api/projects/p1", json={"name": "Updated"})
        assert resp1.status_code == 200
        # Second update with a stale timestamp — should 409
        resp2 = await client.put(
            "/api/projects/p1",
            json={"name": "Again"},
            headers={"If-Unmodified-Since": "Thu, 01 Jan 2020 00:00:00 GMT"},
        )
        assert resp2.status_code == 409
        assert "modified" in resp2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_response_includes_prompts(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="my prompt")
        resp = await client.put("/api/projects/p1", json={"description": "d"})
        assert resp.status_code == 200
        assert len(resp.json()["prompts"]) == 1


# ---------------------------------------------------------------------------
# Project Delete
# ---------------------------------------------------------------------------

class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_delete_success(self, client):
        await _seed_project(client, project_id="p1", name="ToDelete")
        resp = await client.delete("/api/projects/p1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "p1"
        # Verify it's gone from listing
        list_resp = await client.get("/api/projects")
        assert list_resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        resp = await client.delete("/api/projects/no-such")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_already_deleted_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="AlreadyGone", status="deleted")
        resp = await client.delete("/api/projects/p1")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_archived_succeeds(self, client):
        """Even archived projects can be deleted (soft-delete is not a mutation guard)."""
        await _seed_project(client, project_id="p1", name="ArchDel", status="archived")
        resp = await client.delete("/api/projects/p1")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Archive / Unarchive
# ---------------------------------------------------------------------------

class TestArchiveUnarchive:
    @pytest.mark.asyncio
    async def test_archive_success(self, client):
        await _seed_project(client, project_id="p1", name="ToArchive")
        resp = await client.post("/api/projects/p1/archive")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
        # Verify via GET
        get_resp = await client.get("/api/projects/p1")
        assert get_resp.json()["status"] == "archived"

    @pytest.mark.asyncio
    async def test_archive_already_archived_returns_400(self, client):
        await _seed_project(client, project_id="p1", name="Frozen", status="archived")
        resp = await client.post("/api/projects/p1/archive")
        assert resp.status_code == 400
        assert "already archived" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_archive_nonexistent_returns_404(self, client):
        resp = await client.post("/api/projects/no-such/archive")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_archive_deleted_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="Del", status="deleted")
        resp = await client.post("/api/projects/p1/archive")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unarchive_success(self, client):
        await _seed_project(client, project_id="p1", name="ToRestore", status="archived")
        resp = await client.post("/api/projects/p1/unarchive")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_unarchive_already_active_returns_400(self, client):
        await _seed_project(client, project_id="p1", name="Active")
        resp = await client.post("/api/projects/p1/unarchive")
        assert resp.status_code == 400
        assert "already active" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_unarchive_nonexistent_returns_404(self, client):
        resp = await client.post("/api/projects/no-such/unarchive")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_archive_unarchive_roundtrip(self, client):
        await _seed_project(client, project_id="p1", name="Roundtrip")
        # Archive
        resp = await client.post("/api/projects/p1/archive")
        assert resp.status_code == 200
        # Unarchive
        resp = await client.post("/api/projects/p1/unarchive")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


# ---------------------------------------------------------------------------
# Add Prompt
# ---------------------------------------------------------------------------

class TestAddPrompt:
    @pytest.mark.asyncio
    async def test_add_prompt_success(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.post(
            "/api/projects/p1/prompts",
            json={"content": "Write a haiku about testing"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Write a haiku about testing"
        assert data["version"] == 1
        assert data["project_id"] == "p1"
        assert data["order_index"] == 0

    @pytest.mark.asyncio
    async def test_add_multiple_prompts_increment_order(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp1 = await client.post("/api/projects/p1/prompts", json={"content": "first"})
        resp2 = await client.post("/api/projects/p1/prompts", json={"content": "second"})
        assert resp1.json()["order_index"] == 0
        assert resp2.json()["order_index"] == 1

    @pytest.mark.asyncio
    async def test_add_prompt_to_nonexistent_project_returns_404(self, client):
        resp = await client.post(
            "/api/projects/no-such/prompts",
            json={"content": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_add_empty_content_rejected(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.post("/api/projects/p1/prompts", json={"content": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_add_whitespace_content_rejected(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.post("/api/projects/p1/prompts", json={"content": "   "})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Update Prompt
# ---------------------------------------------------------------------------

class TestUpdatePrompt:
    @pytest.mark.asyncio
    async def test_update_content(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="original")
        resp = await client.put(
            "/api/projects/p1/prompts/prm-1",
            json={"content": "updated content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "updated content"
        assert data["version"] == 2  # Should increment

    @pytest.mark.asyncio
    async def test_update_creates_version_snapshot(self, client):
        """Updating prompt content should create a PromptVersion snapshot."""
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="v1 content")
        # Update to v2
        await client.put(
            "/api/projects/p1/prompts/prm-1",
            json={"content": "v2 content"},
        )
        # Check versions endpoint
        resp = await client.get("/api/projects/p1/prompts/prm-1/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["version"] == 1
        assert data["items"][0]["content"] == "v1 content"

    @pytest.mark.asyncio
    async def test_update_nonexistent_prompt_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.put(
            "/api/projects/p1/prompts/no-such",
            json={"content": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_prompt_wrong_project_returns_404(self, client):
        """Prompt exists but belongs to a different project."""
        await _seed_project(client, project_id="p1", name="P1")
        await _seed_project(client, project_id="p2", name="P2")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1")
        resp = await client.put(
            "/api/projects/p2/prompts/prm-1",
            json={"content": "x"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete Prompt
# ---------------------------------------------------------------------------

class TestDeletePrompt:
    @pytest.mark.asyncio
    async def test_delete_success(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1")
        resp = await client.delete("/api/projects/p1/prompts/prm-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "prm-1"
        # Verify prompt is gone
        get_resp = await client.get("/api/projects/p1")
        assert len(get_resp.json()["prompts"]) == 0

    @pytest.mark.asyncio
    async def test_delete_cascades_optimizations(self, client):
        """Deleting a prompt should cascade-delete linked optimizations."""
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="my prompt")
        await _seed_optimization(client, opt_id="opt-1", raw_prompt="my prompt",
                                 prompt_id="prm-1", project="P")
        resp = await client.delete("/api/projects/p1/prompts/prm-1")
        assert resp.status_code == 200
        assert resp.json()["deleted_optimizations"] >= 1

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.delete("/api/projects/p1/prompts/no-such")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_prompt_wrong_project_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="P1")
        await _seed_project(client, project_id="p2", name="P2")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1")
        resp = await client.delete("/api/projects/p2/prompts/prm-1")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reorder Prompts
# ---------------------------------------------------------------------------

class TestReorderPrompts:
    @pytest.mark.asyncio
    async def test_reorder_success(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="a", project_id="p1",
                           content="first", order_index=0)
        await _seed_prompt(client, prompt_id="b", project_id="p1",
                           content="second", order_index=1)
        resp = await client.put(
            "/api/projects/p1/prompts/reorder",
            json={"prompt_ids": ["b", "a"]},
        )
        assert resp.status_code == 200
        prompts = resp.json()["prompts"]
        assert prompts[0]["id"] == "b"
        assert prompts[0]["order_index"] == 0
        assert prompts[1]["id"] == "a"
        assert prompts[1]["order_index"] == 1

    @pytest.mark.asyncio
    async def test_reorder_unknown_id_returns_400(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="a", project_id="p1")
        resp = await client.put(
            "/api/projects/p1/prompts/reorder",
            json={"prompt_ids": ["a", "nonexistent"]},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reorder_missing_prompts_returns_400(self, client):
        """Must include all prompts in the project."""
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="a", project_id="p1",
                           content="first", order_index=0)
        await _seed_prompt(client, prompt_id="b", project_id="p1",
                           content="second", order_index=1)
        # Only include one of two prompts
        resp = await client.put(
            "/api/projects/p1/prompts/reorder",
            json={"prompt_ids": ["a"]},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reorder_nonexistent_project_returns_404(self, client):
        resp = await client.put(
            "/api/projects/no-such/prompts/reorder",
            json={"prompt_ids": ["a"]},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reorder_empty_ids_rejected(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.put(
            "/api/projects/p1/prompts/reorder",
            json={"prompt_ids": []},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Prompt Versions
# ---------------------------------------------------------------------------

class TestPromptVersions:
    @pytest.mark.asyncio
    async def test_versions_empty(self, client):
        """A prompt with no updates has no version history."""
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1")
        resp = await client.get("/api/projects/p1/prompts/prm-1/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_versions_after_updates(self, client):
        """Multiple updates should create multiple version snapshots."""
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="v1")
        # Update to v2
        await client.put(
            "/api/projects/p1/prompts/prm-1",
            json={"content": "v2"},
        )
        # Update to v3
        await client.put(
            "/api/projects/p1/prompts/prm-1",
            json={"content": "v3"},
        )
        resp = await client.get("/api/projects/p1/prompts/prm-1/versions")
        data = resp.json()
        assert data["total"] == 2
        # Newest first
        assert data["items"][0]["version"] == 2
        assert data["items"][0]["content"] == "v2"
        assert data["items"][1]["version"] == 1
        assert data["items"][1]["content"] == "v1"

    @pytest.mark.asyncio
    async def test_versions_pagination(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="v1")
        # Seed 3 version snapshots directly
        for i in range(1, 4):
            await _seed_prompt_version(
                client, version_id=f"ver-{i}", prompt_id="prm-1",
                version=i, content=f"v{i}",
            )
        resp = await client.get(
            "/api/projects/p1/prompts/prm-1/versions?limit=2&offset=0"
        )
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_versions_nonexistent_prompt_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.get("/api/projects/p1/prompts/no-such/versions")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_versions_wrong_project_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="P1")
        await _seed_project(client, project_id="p2", name="P2")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1")
        resp = await client.get("/api/projects/p2/prompts/prm-1/versions")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Prompt Forges
# ---------------------------------------------------------------------------

class TestPromptForges:
    @pytest.mark.asyncio
    async def test_forges_empty(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1")
        resp = await client.get("/api/projects/p1/prompts/prm-1/forges")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_forges_returns_linked_optimizations(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="my prompt")
        await _seed_optimization(
            client, opt_id="opt-1", raw_prompt="my prompt",
            prompt_id="prm-1", project="P",
        )
        resp = await client.get("/api/projects/p1/prompts/prm-1/forges")
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["id"] == "opt-1"
        assert data["items"][0]["framework_applied"] == "chain-of-thought"

    @pytest.mark.asyncio
    async def test_forges_nonexistent_prompt_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="P")
        resp = await client.get("/api/projects/p1/prompts/no-such/forges")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_forges_wrong_project_returns_404(self, client):
        await _seed_project(client, project_id="p1", name="P1")
        await _seed_project(client, project_id="p2", name="P2")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1")
        resp = await client.get("/api/projects/p2/prompts/prm-1/forges")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_forges_pagination(self, client):
        await _seed_project(client, project_id="p1", name="P")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="my prompt")
        for i in range(5):
            await _seed_optimization(
                client, opt_id=f"opt-{i}", raw_prompt="my prompt",
                prompt_id="prm-1", project="P",
            )
        resp = await client.get(
            "/api/projects/p1/prompts/prm-1/forges?limit=2&offset=0"
        )
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# Delete Cascade (project → prompts → optimizations)
# ---------------------------------------------------------------------------

class TestDeleteCascade:
    @pytest.mark.asyncio
    async def test_delete_cascades_prompts_and_optimizations(self, client):
        """Deleting a project should remove all prompts and optimizations."""
        await _seed_project(client, project_id="p1", name="CascadeProject")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="prompt one")
        await _seed_prompt(client, prompt_id="prm-2", project_id="p1",
                           content="prompt two")
        # FK-linked optimizations
        await _seed_optimization(client, opt_id="opt-fk1", raw_prompt="prompt one",
                                 prompt_id="prm-1", project="CascadeProject")
        await _seed_optimization(client, opt_id="opt-fk2", raw_prompt="prompt two",
                                 prompt_id="prm-2", project="CascadeProject")
        # Legacy optimization (no prompt_id, matched by project name)
        await _seed_optimization(client, opt_id="opt-leg", raw_prompt="old prompt",
                                 prompt_id=None, project="CascadeProject")

        # Delete the project
        resp = await client.delete("/api/projects/p1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_optimizations"] >= 3

        # Project should be gone from listing
        list_resp = await client.get("/api/projects")
        assert list_resp.json()["total"] == 0

        # Optimizations should be gone from history
        history_resp = await client.get("/api/history")
        assert history_resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_delete_cascade_with_versions(self, client):
        """Prompt versions should also be cleaned up on project deletion."""
        await _seed_project(client, project_id="p1", name="VersionProject")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="v1 content")
        await _seed_prompt_version(client, version_id="ver-1", prompt_id="prm-1",
                                   version=1, content="old content")

        resp = await client.delete("/api/projects/p1")
        assert resp.status_code == 200

        # Project is deleted — get returns 404
        get_resp = await client.get("/api/projects/p1")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_cascade_preserves_unrelated(self, client):
        """Deleting one project should not affect another project's data."""
        await _seed_project(client, project_id="p1", name="ToDelete")
        await _seed_project(client, project_id="p2", name="ToKeep")
        await _seed_prompt(client, prompt_id="prm-1", project_id="p1",
                           content="delete me")
        await _seed_prompt(client, prompt_id="prm-2", project_id="p2",
                           content="keep me")
        await _seed_optimization(client, opt_id="opt-del", raw_prompt="delete me",
                                 prompt_id="prm-1", project="ToDelete")
        await _seed_optimization(client, opt_id="opt-keep", raw_prompt="keep me",
                                 prompt_id="prm-2", project="ToKeep")

        # Delete only p1
        resp = await client.delete("/api/projects/p1")
        assert resp.status_code == 200

        # p2 should still be intact
        get_resp = await client.get("/api/projects/p2")
        assert get_resp.status_code == 200
        assert len(get_resp.json()["prompts"]) == 1

        # History should only contain p2's optimization
        history_resp = await client.get("/api/history")
        assert history_resp.json()["total"] == 1
        assert history_resp.json()["items"][0]["id"] == "opt-keep"


# ---------------------------------------------------------------------------
# get_context_by_name — project description fallback
# ---------------------------------------------------------------------------

class TestGetContextByNameDescriptionFallback:
    """Verify that Project.description is injected as a fallback for
    CodebaseContext.description when the context profile doesn't provide one."""

    @pytest.mark.asyncio
    async def test_no_profile_no_description_returns_none(self, db_session):
        """Project with neither description nor context profile → None."""
        db_session.add(Project(id="p1", name="Empty"))
        await db_session.flush()
        ctx = await ProjectRepository(db_session).get_context_by_name("Empty")
        assert ctx is None

    @pytest.mark.asyncio
    async def test_description_only_creates_context(self, db_session):
        """Project with description but no context profile → CodebaseContext(description=...)."""
        db_session.add(Project(id="p1", name="Described", description="A React dashboard"))
        await db_session.flush()
        ctx = await ProjectRepository(db_session).get_context_by_name("Described")
        assert ctx is not None
        assert ctx.description == "A React dashboard"
        # Other fields should be defaults
        assert ctx.language is None
        assert ctx.framework is None

    @pytest.mark.asyncio
    async def test_profile_without_description_gets_fallback(self, db_session):
        """Profile without description gets project description fallback."""
        profile = json.dumps({"language": "Python", "framework": "FastAPI"})
        db_session.add(Project(
            id="p1", name="Partial", description="Inventory management API",
            context_profile=profile,
        ))
        await db_session.flush()
        ctx = await ProjectRepository(db_session).get_context_by_name("Partial")
        assert ctx is not None
        assert ctx.language == "Python"
        assert ctx.framework == "FastAPI"
        assert ctx.description == "Inventory management API"

    @pytest.mark.asyncio
    async def test_profile_description_wins_over_project_description(self, db_session):
        """Context profile's own description takes priority over Project.description."""
        profile = json.dumps({"description": "Profile-level description", "language": "Go"})
        db_session.add(Project(
            id="p1", name="Both", description="Project-level description",
            context_profile=profile,
        ))
        await db_session.flush()
        ctx = await ProjectRepository(db_session).get_context_by_name("Both")
        assert ctx is not None
        assert ctx.description == "Profile-level description"

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_none(self, db_session):
        ctx = await ProjectRepository(db_session).get_context_by_name("NoSuchProject")
        assert ctx is None
