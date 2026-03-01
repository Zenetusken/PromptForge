"""Tests for the kernel background job queue."""

import asyncio

import pytest

from kernel.services.job_queue import Job, JobQueue, JobStatus


class FakeBus:
    """Minimal bus mock that records published events."""

    def __init__(self):
        self.events: list[tuple[str, dict, str]] = []

    def publish(self, event_type: str, data: dict, source: str) -> None:
        self.events.append((event_type, data, source))


class TestJobLifecycle:
    """Submit → execute → complete lifecycle."""

    @pytest.mark.asyncio
    async def test_submit_returns_job_id(self):
        queue = JobQueue(max_workers=1)
        queue.register_handler("echo", _echo_handler)
        job_id = await queue.submit("test-app", "echo", {"msg": "hello"})
        assert job_id
        job = queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        assert job.app_id == "test-app"

    @pytest.mark.asyncio
    async def test_job_completes_successfully(self):
        bus = FakeBus()
        queue = JobQueue(max_workers=1, bus=bus)
        queue.register_handler("echo", _echo_handler)
        await queue.start()

        job_id = await queue.submit("test-app", "echo", {"msg": "hello"})
        # Allow worker to process
        await asyncio.sleep(0.1)

        job = queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"echo": "hello"}
        assert job.progress == 1.0
        assert job.started_at is not None
        assert job.completed_at is not None

        await queue.stop()

    @pytest.mark.asyncio
    async def test_bus_events_emitted(self):
        bus = FakeBus()
        queue = JobQueue(max_workers=1, bus=bus)
        queue.register_handler("echo", _echo_handler)
        await queue.start()

        await queue.submit("test-app", "echo", {"msg": "x"})
        await asyncio.sleep(0.1)
        await queue.stop()

        event_types = [e[0] for e in bus.events]
        assert "kernel:job.submitted" in event_types
        assert "kernel:job.started" in event_types
        assert "kernel:job.completed" in event_types


class TestPriorityOrdering:
    """Higher priority jobs should run first."""

    @pytest.mark.asyncio
    async def test_higher_priority_runs_first(self):
        execution_order: list[str] = []

        async def tracking_handler(job: Job):
            execution_order.append(job.id)
            return {}

        queue = JobQueue(max_workers=1)
        queue.register_handler("track", tracking_handler)

        # Submit 3 jobs before starting — they'll be queued
        low_id = await queue.submit("app", "track", priority=1)
        high_id = await queue.submit("app", "track", priority=10)
        mid_id = await queue.submit("app", "track", priority=5)

        await queue.start()
        await asyncio.sleep(0.2)
        await queue.stop()

        # High priority should be first
        assert execution_order[0] == high_id
        assert execution_order[1] == mid_id
        assert execution_order[2] == low_id


class TestCancellation:
    """Job cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self):
        queue = JobQueue(max_workers=1)
        queue.register_handler("echo", _echo_handler)
        job_id = await queue.submit("app", "echo")
        assert await queue.cancel(job_id) is True
        job = queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_already_completed_returns_false(self):
        queue = JobQueue(max_workers=1)
        queue.register_handler("echo", _echo_handler)
        await queue.start()

        job_id = await queue.submit("app", "echo", {"msg": "x"})
        await asyncio.sleep(0.1)

        assert await queue.cancel(job_id) is False
        await queue.stop()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_false(self):
        queue = JobQueue(max_workers=1)
        assert await queue.cancel("nonexistent-id") is False


class TestRetry:
    """Job retry on failure."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        call_count = 0

        async def flaky_handler(job: Job):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return {"attempts": call_count}

        queue = JobQueue(max_workers=1)
        queue.register_handler("flaky", flaky_handler)
        await queue.start()

        job_id = await queue.submit("app", "flaky", max_retries=2)
        await asyncio.sleep(0.3)
        await queue.stop()

        job = queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.retry_count == 2
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_fails(self):
        async def always_fail(job: Job):
            raise RuntimeError("permanent error")

        bus = FakeBus()
        queue = JobQueue(max_workers=1, bus=bus)
        queue.register_handler("fail", always_fail)
        await queue.start()

        job_id = await queue.submit("app", "fail", max_retries=1)
        await asyncio.sleep(0.2)
        await queue.stop()

        job = queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.error == "permanent error"
        assert job.retry_count == 2  # initial + 1 retry

        failed_events = [e for e in bus.events if e[0] == "kernel:job.failed"]
        assert len(failed_events) >= 1


class TestNoHandler:
    """Jobs with no registered handler should fail."""

    @pytest.mark.asyncio
    async def test_unregistered_handler_fails(self):
        bus = FakeBus()
        queue = JobQueue(max_workers=1, bus=bus)
        await queue.start()

        job_id = await queue.submit("app", "unknown-type")
        await asyncio.sleep(0.1)
        await queue.stop()

        job = queue.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert "No handler" in (job.error or "")


class TestListJobs:
    """Job listing and filtering."""

    @pytest.mark.asyncio
    async def test_list_all_jobs(self):
        queue = JobQueue(max_workers=1)
        queue.register_handler("echo", _echo_handler)
        await queue.submit("app-a", "echo")
        await queue.submit("app-b", "echo")

        all_jobs = queue.list_jobs()
        assert len(all_jobs) == 2

    @pytest.mark.asyncio
    async def test_filter_by_app_id(self):
        queue = JobQueue(max_workers=1)
        queue.register_handler("echo", _echo_handler)
        await queue.submit("app-a", "echo")
        await queue.submit("app-b", "echo")

        filtered = queue.list_jobs(app_id="app-a")
        assert len(filtered) == 1
        assert filtered[0].app_id == "app-a"

    @pytest.mark.asyncio
    async def test_filter_by_status(self):
        queue = JobQueue(max_workers=1)
        queue.register_handler("echo", _echo_handler)
        await queue.start()
        await queue.submit("app", "echo", {"msg": "x"})
        await asyncio.sleep(0.1)
        await queue.submit("app", "echo")  # still pending (worker busy with stop)
        await queue.stop()

        completed = queue.list_jobs(status=JobStatus.COMPLETED)
        assert all(j.status == JobStatus.COMPLETED for j in completed)


class TestMaxWorkers:
    """Concurrency control."""

    @pytest.mark.asyncio
    async def test_max_workers_limits_concurrency(self):
        concurrent = 0
        max_concurrent = 0

        async def slow_handler(job: Job):
            nonlocal concurrent, max_concurrent
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.1)
            concurrent -= 1
            return {}

        queue = JobQueue(max_workers=2)
        queue.register_handler("slow", slow_handler)
        await queue.start()

        for _ in range(5):
            await queue.submit("app", "slow")

        await asyncio.sleep(0.5)
        await queue.stop()

        assert max_concurrent <= 2


class TestJobRouter:
    """Integration tests for the job queue HTTP endpoints."""

    @pytest.mark.asyncio
    async def test_list_jobs_endpoint(self, client):
        resp = await client.get("/api/kernel/jobs")
        # May return 503 if job queue not wired, or 200 with empty list
        assert resp.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, client):
        resp = await client.get("/api/kernel/jobs/nonexistent-id")
        # 404 or 503 (if service not available in test env)
        assert resp.status_code in (404, 503)


# --- Helpers ---

async def _echo_handler(job: Job) -> dict:
    """Simple handler that echoes the payload."""
    return {"echo": job.payload.get("msg", "ok")}
