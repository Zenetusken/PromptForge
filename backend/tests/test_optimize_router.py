"""Tests for the optimize router endpoints — POST, GET, retry."""

from unittest.mock import AsyncMock, patch

import pytest

from app.constants import OptimizationStatus
from app.models.optimization import Optimization
from app.services.pipeline import PipelineComplete

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_optimization(client, **overrides) -> str:
    """Insert an optimization record directly via the test DB session.

    Uses the client fixture's dependency override to access the DB.
    Returns the optimization ID.
    """
    from app.database import get_db
    from app.main import app

    override_fn = app.dependency_overrides[get_db]
    # Call the generator to get a session
    gen = override_fn()
    session = await gen.__anext__()
    defaults = {
        "id": "test-opt-001",
        "raw_prompt": "test prompt",
        "status": OptimizationStatus.COMPLETED,
        "task_type": "coding",
        "overall_score": 0.8,
        "optimized_prompt": "better prompt",
    }
    defaults.update(overrides)
    opt = Optimization(**defaults)
    session.add(opt)
    await session.flush()
    await session.commit()
    return defaults["id"]


# ---------------------------------------------------------------------------
# TestGetOptimization
# ---------------------------------------------------------------------------

class TestGetOptimization:
    @pytest.mark.asyncio
    async def test_found(self, client):
        await _seed_optimization(client)
        response = await client.get("/api/optimize/test-opt-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-opt-001"
        assert data["raw_prompt"] == "test prompt"

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        response = await client.get("/api/optimize/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_completed_has_cache_header(self, client):
        await _seed_optimization(client, status=OptimizationStatus.COMPLETED)
        response = await client.get("/api/optimize/test-opt-001")
        assert "max-age=3600" in response.headers.get("cache-control", "")

    @pytest.mark.asyncio
    async def test_running_has_no_cache(self, client):
        await _seed_optimization(client, status=OptimizationStatus.RUNNING)
        response = await client.get("/api/optimize/test-opt-001")
        assert "no-cache" in response.headers.get("cache-control", "")


# ---------------------------------------------------------------------------
# TestPostOptimize
# ---------------------------------------------------------------------------

class TestPostOptimize:
    @pytest.mark.asyncio
    async def test_returns_sse_stream(self, client):
        """POST /api/optimize returns a streaming SSE response."""

        async def _fake_stream(*args, **kwargs):
            yield "event: stage\ndata: {\"stage\": \"analyzing\"}\n\n"
            yield PipelineComplete(data={"optimized_prompt": "better"})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch("app.routers.optimize.update_optimization_status", new_callable=AsyncMock),
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post(
                "/api/optimize",
                json={"prompt": "test prompt"},
            )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_blank_prompt_returns_422(self, client):
        response = await client.post(
            "/api/optimize",
            json={"prompt": "   "},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_strategy_returns_422(self, client):
        response = await client.post(
            "/api/optimize",
            json={"prompt": "test", "strategy": "bogus"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_strategy_accepted(self, client):

        async def _fake_stream(*args, **kwargs):
            yield PipelineComplete(data={})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch("app.routers.optimize.update_optimization_status", new_callable=AsyncMock),
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post(
                "/api/optimize",
                json={"prompt": "test", "strategy": "chain-of-thought"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_provider_returns_400(self, client):
        with patch(
            "app.routers.optimize._resolve_provider",
            side_effect=ValueError("Unknown provider"),
        ):
            response = await client.post(
                "/api/optimize",
                json={"prompt": "test", "provider": "nonexistent"},
            )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestRetryOptimization
# ---------------------------------------------------------------------------

class TestRetryOptimization:
    @pytest.mark.asyncio
    async def test_retry_not_found(self, client):
        with (
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post("/api/optimize/nonexistent/retry")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_creates_new_record(self, client):
        await _seed_optimization(client)

        async def _fake_stream(*args, **kwargs):
            yield PipelineComplete(data={})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch("app.routers.optimize.update_optimization_status", new_callable=AsyncMock),
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post("/api/optimize/test-opt-001/retry")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# TestEventStreamDBPersistence
# ---------------------------------------------------------------------------

class TestEventStreamDBPersistence:
    """Verify that event_stream() correctly persists results to the DB."""

    @pytest.mark.asyncio
    async def test_success_calls_update_with_result_data(self, client):
        """After pipeline yields PipelineComplete, update_optimization_status
        is called with result_data matching the PipelineComplete data."""
        complete_data = {
            "optimized_prompt": "better prompt",
            "overall_score": 0.85,
            "task_type": "coding",
        }

        async def _fake_stream(*args, **kwargs):
            yield "event: stage\ndata: {\"stage\": \"analyzing\"}\n\n"
            yield PipelineComplete(data=complete_data)

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch(
                "app.routers.optimize.update_optimization_status", new_callable=AsyncMock,
            ) as mock_update,
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post(
                "/api/optimize",
                json={"prompt": "test prompt"},
            )
            # Consume the full response body to drive the async generator
            _ = response.text

        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["result_data"] == complete_data
        assert "start_time" in call_kwargs
        assert call_kwargs["model_fallback"] == "test-model"

    @pytest.mark.asyncio
    async def test_pipeline_error_calls_update_with_error(self, client):
        """When the pipeline raises, update_optimization_status is called with
        the error string, and the SSE stream contains an error event."""

        async def _failing_stream(*args, **kwargs):
            raise RuntimeError("LLM exploded")
            # Make it an async generator even though it raises immediately
            yield  # noqa: unreachable  # pragma: no cover

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_failing_stream),
            patch(
                "app.routers.optimize.update_optimization_status", new_callable=AsyncMock,
            ) as mock_update,
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post(
                "/api/optimize",
                json={"prompt": "test prompt"},
            )
            body = response.text

        # Verify the error path called update with the error message
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["error"] == "LLM exploded"

        # Verify the SSE stream contains an error event
        assert "event: error" in body
        assert "LLM exploded" in body

    @pytest.mark.asyncio
    async def test_db_update_failure_emits_error_event(self, client):
        """When update_optimization_status raises on the success path, the SSE
        stream should contain a 'Failed to save result' error event."""

        async def _fake_stream(*args, **kwargs):
            yield PipelineComplete(data={"optimized_prompt": "better"})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch(
                "app.routers.optimize.update_optimization_status",
                new_callable=AsyncMock,
                side_effect=Exception("DB connection lost"),
            ),
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post(
                "/api/optimize",
                json={"prompt": "test prompt"},
            )
            body = response.text

        assert "event: error" in body
        assert "Failed to save result" in body


# ---------------------------------------------------------------------------
# TestAutoPromptCreation
# ---------------------------------------------------------------------------

class TestAutoPromptCreation:
    """Verify that forging with a project name auto-creates a Prompt record."""

    @pytest.mark.asyncio
    async def test_optimize_with_project_creates_prompt(self, client):
        """POST /api/optimize with project name and no prompt_id creates a
        Prompt record linked to the optimization."""

        async def _fake_stream(*args, **kwargs):
            yield PipelineComplete(data={"optimized_prompt": "better"})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch("app.routers.optimize.update_optimization_status", new_callable=AsyncMock),
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post(
                "/api/optimize",
                json={"prompt": "my test prompt", "project": "AutoProject"},
            )
            _ = response.text

        assert response.status_code == 200

        # Verify DB state: optimization should have a prompt_id set
        from sqlalchemy import select

        from app.database import get_db
        from app.main import app
        from app.models.optimization import Optimization as OptModel
        from app.models.project import Project, Prompt

        override_fn = app.dependency_overrides[get_db]
        gen = override_fn()
        session = await gen.__anext__()

        # Find the optimization (there should be exactly one)
        result = await session.execute(select(OptModel))
        opt = result.scalar_one()
        assert opt.prompt_id is not None, "optimization should have auto-created prompt_id"
        assert opt.project == "AutoProject"

        # Verify the Prompt record exists and matches
        prompt = await session.get(Prompt, opt.prompt_id)
        assert prompt is not None
        assert prompt.content == "my test prompt"

        # Verify the Project record exists
        proj_result = await session.execute(
            select(Project).where(Project.name == "AutoProject")
        )
        proj = proj_result.scalar_one()
        assert prompt.project_id == proj.id

    @pytest.mark.asyncio
    async def test_optimize_with_prompt_id_skips_auto_create(self, client):
        """When prompt_id is explicitly provided, no auto-prompt is created."""
        from app.database import get_db
        from app.main import app
        from app.models.project import Project, Prompt

        # Seed a project + prompt first
        override_fn = app.dependency_overrides[get_db]
        gen = override_fn()
        session = await gen.__anext__()
        proj = Project(name="ExistingProject")
        session.add(proj)
        await session.flush()
        prompt = Prompt(content="existing prompt", project_id=proj.id, order_index=0)
        session.add(prompt)
        await session.flush()
        await session.commit()

        async def _fake_stream(*args, **kwargs):
            yield PipelineComplete(data={})

        with (
            patch("app.routers.optimize.run_pipeline_streaming", side_effect=_fake_stream),
            patch("app.routers.optimize.update_optimization_status", new_callable=AsyncMock),
            patch("app.routers.optimize.get_provider") as mock_gp,
        ):
            mock_gp.return_value.model_name = "test-model"
            response = await client.post(
                "/api/optimize",
                json={
                    "prompt": "existing prompt",
                    "project": "ExistingProject",
                    "prompt_id": prompt.id,
                },
            )
            _ = response.text

        assert response.status_code == 200

        # Verify no extra Prompt was created (should still be just 1)
        from sqlalchemy import func
        from sqlalchemy import select as sa_select

        gen2 = override_fn()
        session2 = await gen2.__anext__()
        count_result = await session2.execute(
            sa_select(func.count(Prompt.id)).where(Prompt.project_id == proj.id)
        )
        assert count_result.scalar() == 1
