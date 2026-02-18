"""Tests for archive-related mutation guards.

Archived projects must be read-only: all mutation endpoints should return 403.
The optimize endpoint should skip linking new optimizations to archived projects.
"""

import pytest
from sqlalchemy import select

from app.constants import ProjectStatus
from app.database import get_db
from app.main import app
from app.models.project import Project, Prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_archived_project(*, with_prompt: bool = False):
    """Create an archived project (and optionally a prompt) via the DB."""
    override_fn = app.dependency_overrides[get_db]
    gen = override_fn()
    session = await gen.__anext__()

    proj = Project(name="Frozen Project", description="sealed", status=ProjectStatus.ARCHIVED)
    session.add(proj)
    await session.flush()

    prompt_id = None
    if with_prompt:
        prompt = Prompt(content="archived prompt", project_id=proj.id, order_index=0)
        session.add(prompt)
        await session.flush()
        prompt_id = prompt.id

    await session.commit()
    return proj.id, prompt_id


# ---------------------------------------------------------------------------
# Mutation guard tests — all should return 403
# ---------------------------------------------------------------------------

class TestArchiveGuards:
    """Archived projects reject all mutation requests with 403."""

    @pytest.mark.asyncio
    async def test_update_archived_project_returns_403(self, client):
        project_id, _ = await _seed_archived_project()
        resp = await client.put(
            f"/api/projects/{project_id}",
            json={"name": "New Name"},
        )
        assert resp.status_code == 403
        assert "archived" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_prompt_to_archived_project_returns_403(self, client):
        project_id, _ = await _seed_archived_project()
        resp = await client.post(
            f"/api/projects/{project_id}/prompts",
            json={"content": "new prompt"},
        )
        assert resp.status_code == 403
        assert "archived" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_prompt_in_archived_project_returns_403(self, client):
        project_id, prompt_id = await _seed_archived_project(with_prompt=True)
        resp = await client.put(
            f"/api/projects/{project_id}/prompts/{prompt_id}",
            json={"content": "updated content"},
        )
        assert resp.status_code == 403
        assert "archived" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_prompt_in_archived_project_returns_403(self, client):
        project_id, prompt_id = await _seed_archived_project(with_prompt=True)
        resp = await client.delete(
            f"/api/projects/{project_id}/prompts/{prompt_id}",
        )
        assert resp.status_code == 403
        assert "archived" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_reorder_prompts_in_archived_project_returns_403(self, client):
        project_id, prompt_id = await _seed_archived_project(with_prompt=True)
        resp = await client.put(
            f"/api/projects/{project_id}/prompts/reorder",
            json={"prompt_ids": [prompt_id]},
        )
        assert resp.status_code == 403
        assert "archived" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Optimize endpoint — archived project linking skipped
# ---------------------------------------------------------------------------

class TestOptimizeArchivedProject:
    """POST /api/optimize with an archived project name should create the
    optimization but NOT auto-link it to the archived project's prompts."""

    @pytest.mark.asyncio
    async def test_optimize_skips_prompt_linking_for_archived_project(self, client):
        from unittest.mock import AsyncMock, patch

        from app.models.optimization import Optimization as OptModel
        from app.services.pipeline import PipelineComplete

        # Seed an archived project
        override_fn = app.dependency_overrides[get_db]
        gen = override_fn()
        session = await gen.__anext__()
        proj = Project(name="ArchivedProj", status=ProjectStatus.ARCHIVED)
        session.add(proj)
        await session.flush()
        proj_id = proj.id
        await session.commit()

        async def _fake_stream(*args, **kwargs):
            yield PipelineComplete(data={})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch("app.routers.optimize.update_optimization_status", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/optimize",
                json={"prompt": "test prompt", "project": "ArchivedProj"},
            )
            # Consume the SSE stream
            _ = resp.text

        assert resp.status_code == 200

        # Verify: optimization exists but prompt_id is NOT set
        gen2 = override_fn()
        session2 = await gen2.__anext__()
        result = await session2.execute(select(OptModel))
        opt = result.scalar_one()
        assert opt.project == "ArchivedProj"
        assert opt.prompt_id is None, "should NOT auto-link to archived project"

        # Verify: no Prompt records were created for the archived project
        prompt_result = await session2.execute(
            select(Prompt).where(Prompt.project_id == proj_id)
        )
        assert prompt_result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_retry_skips_prompt_linking_for_archived_project(self, client):
        """POST /api/optimize/{id}/retry with an archived project name should
        create the retry but NOT auto-link it to the archived project's prompts."""
        from unittest.mock import AsyncMock, patch

        from app.models.optimization import Optimization as OptModel
        from app.services.pipeline import PipelineComplete

        # Seed an archived project + original optimization
        override_fn = app.dependency_overrides[get_db]
        gen = override_fn()
        session = await gen.__anext__()
        proj = Project(name="RetryArchived", status=ProjectStatus.ARCHIVED)
        session.add(proj)
        await session.flush()
        proj_id = proj.id
        original = OptModel(
            id="orig-001",
            raw_prompt="original prompt",
            status="completed",
            project="RetryArchived",
        )
        session.add(original)
        await session.flush()
        await session.commit()

        async def _fake_stream(*args, **kwargs):
            yield PipelineComplete(data={})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch("app.routers.optimize.update_optimization_status", new_callable=AsyncMock),
        ):
            resp = await client.post("/api/optimize/orig-001/retry")
            _ = resp.text

        assert resp.status_code == 200

        # Verify: retry optimization has no prompt_id
        gen2 = override_fn()
        session2 = await gen2.__anext__()
        result = await session2.execute(
            select(OptModel).where(OptModel.id != "orig-001")
        )
        retry_opt = result.scalar_one()
        assert retry_opt.project == "RetryArchived"
        assert retry_opt.prompt_id is None, "retry should NOT auto-link to archived project"

        # Verify: no Prompt records were created
        prompt_result = await session2.execute(
            select(Prompt).where(Prompt.project_id == proj_id)
        )
        assert prompt_result.scalars().all() == []
