"""Tests for history endpoints — pagination, filtering, deletion, stats."""


import pytest

from apps.promptforge.constants import OptimizationStatus
from app.database import get_db
from app.main import app
from apps.promptforge.models.optimization import Optimization
from apps.promptforge.models.project import Project, Prompt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed(client, **overrides) -> str:
    """Insert an optimization record via the test DB session."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()
    defaults = {
        "id": "hist-001",
        "raw_prompt": "test prompt",
        "status": OptimizationStatus.COMPLETED,
        "task_type": "coding",
        "overall_score": 0.8,
    }
    defaults.update(overrides)
    opt = Optimization(**defaults)
    session.add(opt)
    await session.flush()
    await session.commit()
    return defaults["id"]


# ---------------------------------------------------------------------------
# TestEmptyHistory (existing tests preserved)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_history_list(client):
    response = await client.get("/api/apps/promptforge/history")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_empty_stats(client):
    response = await client.get("/api/apps/promptforge/history/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_optimizations"] == 0
    assert data["average_overall_score"] is None
    assert data["improvement_rate"] is None


# ---------------------------------------------------------------------------
# TestHistoryWithData
# ---------------------------------------------------------------------------

class TestHistoryWithData:
    @pytest.mark.asyncio
    async def test_list_returns_seeded_items(self, client):
        await _seed(client, id="a")
        await _seed(client, id="b")
        response = await client.get("/api/apps/promptforge/history")
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_pagination(self, client):
        for i in range(5):
            await _seed(client, id=f"p-{i}")
        response = await client.get("/api/apps/promptforge/history?page=1&per_page=2")
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["per_page"] == 2

    @pytest.mark.asyncio
    async def test_search_filter(self, client):
        await _seed(client, id="a", raw_prompt="optimize my SQL query")
        await _seed(client, id="b", raw_prompt="write a poem")
        response = await client.get("/api/apps/promptforge/history?search=SQL")
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_project_filter(self, client):
        await _seed(client, id="a", project="alpha")
        await _seed(client, id="b", project="beta")
        response = await client.get("/api/apps/promptforge/history?project=alpha")
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_task_type_filter(self, client):
        await _seed(client, id="a", task_type="coding")
        await _seed(client, id="b", task_type="creative")
        response = await client.get("/api/apps/promptforge/history?task_type=coding")
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_sort_by_alias(self, client):
        await _seed(client, id="a")
        # sort_by parameter should work as alias for sort
        response = await client.get("/api/apps/promptforge/history?sort_by=created_at&order=desc")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TestHistoryDeletion
# ---------------------------------------------------------------------------

class TestHistoryDeletion:
    @pytest.mark.asyncio
    async def test_delete_single_record(self, client):
        await _seed(client, id="del-001")
        response = await client.delete("/api/apps/promptforge/history/del-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "del-001"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        response = await client.delete("/api/apps/promptforge/history/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_clear_all(self, client):
        await _seed(client, id="a")
        await _seed(client, id="b")
        response = await client.delete(
            "/api/apps/promptforge/history/all",
            headers={"X-Confirm-Delete": "yes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2

    @pytest.mark.asyncio
    async def test_clear_all_empty(self, client):
        response = await client.delete(
            "/api/apps/promptforge/history/all",
            headers={"X-Confirm-Delete": "yes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0

    @pytest.mark.asyncio
    async def test_clear_all_requires_confirm_header(self, client):
        await _seed(client, id="a")
        response = await client.delete("/api/apps/promptforge/history/all")
        assert response.status_code == 400
        assert "X-Confirm-Delete" in response.json()["detail"]


# ---------------------------------------------------------------------------
# TestHistoryStats
# ---------------------------------------------------------------------------

class TestHistoryStats:
    @pytest.mark.asyncio
    async def test_stats_with_data(self, client):
        await _seed(
            client, id="a", overall_score=0.8,
            is_improvement=True, framework_applied="persona-assignment",
        )
        await _seed(
            client, id="b", overall_score=0.6,
            is_improvement=False, framework_applied="chain-of-thought",
        )
        response = await client.get("/api/apps/promptforge/history/stats")
        data = response.json()
        assert data["total_optimizations"] == 2
        assert data["average_overall_score"] is not None


# ---------------------------------------------------------------------------
# Helpers for archive tests
# ---------------------------------------------------------------------------

async def _seed_project(client, *, project_id: str, name: str, status: str = "active") -> str:
    """Insert a Project record via the test DB session."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()
    proj = Project(id=project_id, name=name, status=status)
    session.add(proj)
    await session.flush()
    await session.commit()
    return project_id


async def _seed_prompt(
    client, *, prompt_id: str, project_id: str, content: str = "test"
) -> str:
    """Insert a Prompt record via the test DB session."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()
    prompt = Prompt(id=prompt_id, project_id=project_id, content=content)
    session.add(prompt)
    await session.flush()
    await session.commit()
    return prompt_id


# ---------------------------------------------------------------------------
# TestArchiveFiltering
# ---------------------------------------------------------------------------

class TestArchiveFiltering:
    """Tests for project_status in responses and include_archived filter."""

    @pytest.mark.asyncio
    async def test_project_status_in_history_via_legacy_name(self, client):
        """project_status resolved via legacy project name match."""
        await _seed_project(client, project_id="proj-1", name="MyProject", status="archived")
        await _seed(client, id="opt-1", project="MyProject")
        response = await client.get("/api/apps/promptforge/history")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["project_status"] == "archived"

    @pytest.mark.asyncio
    async def test_project_status_in_history_via_fk(self, client):
        """project_status resolved via FK chain (prompt_id → prompt → project)."""
        await _seed_project(client, project_id="proj-2", name="FKProject", status="active")
        await _seed_prompt(client, prompt_id="prm-1", project_id="proj-2")
        await _seed(client, id="opt-2", prompt_id="prm-1")
        response = await client.get("/api/apps/promptforge/history")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["project_status"] == "active"
        assert data["items"][0]["project_id"] == "proj-2"

    @pytest.mark.asyncio
    async def test_project_status_null_when_no_project(self, client):
        """project_status is null when optimization has no project association."""
        await _seed(client, id="opt-3")
        response = await client.get("/api/apps/promptforge/history")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["project_status"] is None

    @pytest.mark.asyncio
    async def test_include_archived_true_default(self, client):
        """Default include_archived=true includes archived project items."""
        await _seed_project(client, project_id="proj-a", name="Active", status="active")
        await _seed_project(client, project_id="proj-b", name="Archived", status="archived")
        await _seed(client, id="opt-a", project="Active")
        await _seed(client, id="opt-b", project="Archived")
        response = await client.get("/api/apps/promptforge/history")
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_include_archived_false_excludes_archived(self, client):
        """include_archived=false excludes items from archived projects."""
        await _seed_project(client, project_id="proj-a2", name="ActiveP", status="active")
        await _seed_project(client, project_id="proj-b2", name="ArchivedP", status="archived")
        await _seed(client, id="opt-a2", project="ActiveP")
        await _seed(client, id="opt-b2", project="ArchivedP")
        response = await client.get("/api/apps/promptforge/history?include_archived=false")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "opt-a2"

    @pytest.mark.asyncio
    async def test_include_archived_false_excludes_fk_linked(self, client):
        """include_archived=false excludes FK-linked items from archived projects."""
        await _seed_project(client, project_id="proj-fk", name="FKArch", status="archived")
        await _seed_prompt(client, prompt_id="prm-fk", project_id="proj-fk")
        await _seed(client, id="opt-fk", prompt_id="prm-fk")
        await _seed(client, id="opt-no-proj")  # No project at all
        response = await client.get("/api/apps/promptforge/history?include_archived=false")
        data = response.json()
        ids = [item["id"] for item in data["items"]]
        assert "opt-fk" not in ids
        assert "opt-no-proj" in ids

    @pytest.mark.asyncio
    async def test_project_status_in_detail_endpoint(self, client):
        """GET /api/optimize/{id} includes project_status."""
        await _seed_project(client, project_id="proj-det", name="DetailProj", status="archived")
        await _seed(client, id="opt-det", project="DetailProj")
        response = await client.get("/api/apps/promptforge/optimize/opt-det")
        data = response.json()
        assert data["project_status"] == "archived"


# ---------------------------------------------------------------------------
# TestBulkDelete
# ---------------------------------------------------------------------------

class TestBulkDelete:
    @pytest.mark.asyncio
    async def test_bulk_delete_existing(self, client):
        """All IDs exist — all deleted."""
        await _seed(client, id="bd-1")
        await _seed(client, id="bd-2")
        await _seed(client, id="bd-3")
        response = await client.post(
            "/api/apps/promptforge/history/bulk-delete",
            json={"ids": ["bd-1", "bd-2", "bd-3"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3
        assert set(data["deleted_ids"]) == {"bd-1", "bd-2", "bd-3"}
        assert data["not_found_ids"] == []

    @pytest.mark.asyncio
    async def test_bulk_delete_mixed(self, client):
        """Mix of existing and non-existent IDs."""
        await _seed(client, id="bd-a")
        await _seed(client, id="bd-b")
        response = await client.post(
            "/api/apps/promptforge/history/bulk-delete",
            json={"ids": ["bd-a", "bd-b", "no-such-id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert set(data["deleted_ids"]) == {"bd-a", "bd-b"}
        assert data["not_found_ids"] == ["no-such-id"]

    @pytest.mark.asyncio
    async def test_bulk_delete_all_missing(self, client):
        """All IDs are non-existent — none deleted."""
        response = await client.post(
            "/api/apps/promptforge/history/bulk-delete",
            json={"ids": ["ghost-1", "ghost-2"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
        assert data["deleted_ids"] == []
        assert set(data["not_found_ids"]) == {"ghost-1", "ghost-2"}

    @pytest.mark.asyncio
    async def test_bulk_delete_empty_ids_rejected(self, client):
        """Empty ids list triggers 422 validation error."""
        response = await client.post(
            "/api/apps/promptforge/history/bulk-delete",
            json={"ids": []},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_delete_over_limit_rejected(self, client):
        """More than 100 IDs triggers 422 validation error."""
        ids = [f"id-{i}" for i in range(101)]
        response = await client.post(
            "/api/apps/promptforge/history/bulk-delete",
            json={"ids": ids},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_delete_records_actually_gone(self, client):
        """Deleted records are no longer retrievable."""
        await _seed(client, id="bd-gone")
        response = await client.post(
            "/api/apps/promptforge/history/bulk-delete",
            json={"ids": ["bd-gone"]},
        )
        assert response.status_code == 200
        # Verify the record is actually gone
        get_response = await client.get("/api/apps/promptforge/optimize/bd-gone")
        assert get_response.status_code == 404
