"""Tests for TextForge cross-app integration — auto-simplify on low-score optimizations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.textforge.app import AUTO_SIMPLIFY_THRESHOLD, TextForgeApp
from kernel.services.job_queue import Job, JobQueue, JobStatus


class FakeBus:
    """Minimal bus mock."""
    def __init__(self):
        self.events: list[tuple[str, dict, str]] = []

    def publish(self, event_type: str, data: dict, source: str) -> None:
        self.events.append((event_type, data, source))


class TestAutoSimplifyTrigger:
    """Event handler triggers auto-simplify for low scores."""

    @pytest.mark.asyncio
    async def test_low_score_triggers_auto_simplify_job(self):
        bus = FakeBus()
        queue = JobQueue(max_workers=1, bus=bus)

        app = TextForgeApp()

        # Mock kernel with job queue
        kernel = MagicMock()
        kernel.services.has.return_value = True
        kernel.services.get.return_value = queue
        app._kernel = kernel

        # Register the handler
        queue.register_handler("textforge:auto-simplify", app._auto_simplify_handler)

        # Get the event handler
        handlers = app.get_event_handlers()
        handler = handlers["promptforge:optimization.completed"]

        # Fire event with low score
        await handler(
            {"optimization_id": "opt-123", "overall_score": 5.5},
            "promptforge",
        )

        # Verify a job was submitted
        jobs = queue.list_jobs(app_id="textforge")
        assert len(jobs) == 1
        assert jobs[0].job_type == "textforge:auto-simplify"
        assert jobs[0].payload["optimization_id"] == "opt-123"
        assert jobs[0].payload["original_score"] == 5.5

    @pytest.mark.asyncio
    async def test_high_score_skips_auto_simplify(self):
        bus = FakeBus()
        queue = JobQueue(max_workers=1, bus=bus)

        app = TextForgeApp()
        kernel = MagicMock()
        kernel.services.has.return_value = True
        kernel.services.get.return_value = queue
        app._kernel = kernel

        handlers = app.get_event_handlers()
        handler = handlers["promptforge:optimization.completed"]

        # Fire event with high score (at or above threshold)
        await handler(
            {"optimization_id": "opt-456", "overall_score": AUTO_SIMPLIFY_THRESHOLD},
            "promptforge",
        )

        # No job should be submitted
        jobs = queue.list_jobs(app_id="textforge")
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_score_exactly_below_threshold_triggers(self):
        bus = FakeBus()
        queue = JobQueue(max_workers=1, bus=bus)

        app = TextForgeApp()
        kernel = MagicMock()
        kernel.services.has.return_value = True
        kernel.services.get.return_value = queue
        app._kernel = kernel

        handlers = app.get_event_handlers()
        handler = handlers["promptforge:optimization.completed"]

        # Score just below threshold
        await handler(
            {"optimization_id": "opt-789", "overall_score": AUTO_SIMPLIFY_THRESHOLD - 0.1},
            "promptforge",
        )

        jobs = queue.list_jobs(app_id="textforge")
        assert len(jobs) == 1


class TestAutoSimplifyHandler:
    """Job handler produces a transform result."""

    @pytest.mark.asyncio
    async def test_handler_fetches_and_simplifies(self):
        app = TextForgeApp()

        # Mock kernel
        kernel = MagicMock()
        kernel.services.has.return_value = True
        mock_queue = MagicMock()
        mock_queue.update_progress = AsyncMock()
        kernel.services.get.return_value = mock_queue

        # Mock DB session factory and provider
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = ("Complex prompt text here",)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        kernel.db_session_factory.return_value = mock_session

        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Simplified prompt text"
        mock_provider.complete = AsyncMock(return_value=mock_response)
        kernel.get_provider.return_value = mock_provider

        app._kernel = kernel

        job = Job(
            id="job-1",
            app_id="textforge",
            job_type="textforge:auto-simplify",
            payload={"optimization_id": "opt-1", "original_score": 5.0},
        )

        with patch.object(app, "_store_simplification", new_callable=AsyncMock) as mock_store:
            mock_store.return_value = "transform-1"
            result = await app._auto_simplify_handler(job)

        assert result["optimization_id"] == "opt-1"
        assert result["transform_id"] == "transform-1"
        assert result["input_length"] > 0
        assert result["output_length"] > 0
        assert "improvement_delta" in result

    @pytest.mark.asyncio
    async def test_handler_skips_if_optimization_not_found(self):
        app = TextForgeApp()

        kernel = MagicMock()
        kernel.services.has.return_value = True
        mock_queue = MagicMock()
        mock_queue.update_progress = AsyncMock()
        kernel.services.get.return_value = mock_queue

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None  # Not found
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        kernel.db_session_factory.return_value = mock_session

        app._kernel = kernel

        job = Job(
            id="job-2",
            app_id="textforge",
            job_type="textforge:auto-simplify",
            payload={"optimization_id": "nonexistent", "original_score": 3.0},
        )

        result = await app._auto_simplify_handler(job)
        assert result.get("skipped") is True

    @pytest.mark.asyncio
    async def test_handler_without_kernel_returns_error(self):
        app = TextForgeApp()
        app._kernel = None

        job = Job(
            id="job-3",
            app_id="textforge",
            job_type="textforge:auto-simplify",
            payload={"optimization_id": "opt-x"},
        )

        result = await app._auto_simplify_handler(job)
        assert "error" in result


class TestJobHandlerRegistration:
    """TextForge registers its job handlers."""

    def test_get_job_handlers_returns_auto_simplify(self):
        app = TextForgeApp()
        handlers = app.get_job_handlers()
        assert "textforge:auto-simplify" in handlers
        assert callable(handlers["textforge:auto-simplify"])


class TestEventContracts:
    """TextForge declares auto-simplify event contract."""

    def test_contracts_include_auto_simplify(self):
        app = TextForgeApp()
        contracts = app.get_event_contracts()
        event_types = [c.event_type for c in contracts]
        assert "textforge:auto-simplify.completed" in event_types
        assert "textforge:transform.completed" in event_types
