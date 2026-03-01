"""Background job queue — kernel service for async task execution.

Provides an in-process priority queue backed by asyncio with configurable
max_workers. Apps register handlers via ``get_job_handlers()``, submit jobs
via the queue, and receive progress/completion events on the EventBus.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from kernel.bus.event_bus import EventBus

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a background job."""

    id: str
    app_id: str
    job_type: str
    payload: dict = field(default_factory=dict)
    priority: int = 0
    status: JobStatus = JobStatus.PENDING
    result: dict | None = None
    error: str | None = None
    progress: float = 0.0
    max_retries: int = 0
    retry_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "app_id": self.app_id,
            "job_type": self.job_type,
            "payload": self.payload,
            "priority": self.priority,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# Priority queue items: (negative priority for max-priority-first, creation order, job)
_QueueItem = tuple[int, int, Job]


class JobQueue:
    """In-process async job queue with bounded concurrency.

    Parameters
    ----------
    max_workers:
        Maximum number of concurrent job workers.
    bus:
        Optional EventBus for publishing job lifecycle events.
    """

    def __init__(
        self,
        max_workers: int = 3,
        bus: EventBus | None = None,
        db_session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._max_workers = max_workers
        self._bus = bus
        self._db_session_factory = db_session_factory
        self._queue: asyncio.PriorityQueue[_QueueItem] = asyncio.PriorityQueue()
        self._handlers: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._jobs: dict[str, Job] = {}
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._counter = 0  # Tiebreaker for equal priorities
        self._last_persisted_progress: dict[str, float] = {}  # For debouncing

    @property
    def running(self) -> bool:
        return self._running

    def register_handler(
        self, job_type: str, handler: Callable[..., Coroutine[Any, Any, Any]]
    ) -> None:
        """Register an async handler for a job type."""
        self._handlers[job_type] = handler
        logger.info("Job handler registered: %s", job_type)

    async def submit(
        self,
        app_id: str,
        job_type: str,
        payload: dict | None = None,
        priority: int = 0,
        max_retries: int = 0,
    ) -> str:
        """Submit a job and return its ID."""
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            app_id=app_id,
            job_type=job_type,
            payload=payload or {},
            priority=priority,
            max_retries=max_retries,
        )
        self._jobs[job_id] = job

        self._counter += 1
        # Negate priority so higher priority values are dequeued first
        await self._queue.put((-priority, self._counter, job))

        await self._persist_create(job)

        self._publish("kernel:job.submitted", job)
        logger.info("Job submitted: %s (type=%s, app=%s)", job_id, job_type, app_id)
        return job_id

    async def cancel(self, job_id: str) -> bool:
        """Cancel a pending or running job. Returns True if cancelled."""
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self._persist_update(
            job.id, status="cancelled", completed_at=job.completed_at,
        )
        self._publish("kernel:job.failed", job, extra={"reason": "cancelled"})
        logger.info("Job cancelled: %s", job_id)
        return True

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        app_id: str | None = None,
        status: JobStatus | None = None,
    ) -> list[Job]:
        """List jobs, optionally filtered by app_id and/or status."""
        jobs = list(self._jobs.values())
        if app_id:
            jobs = [j for j in jobs if j.app_id == app_id]
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def update_progress(self, job_id: str, progress: float) -> None:
        """Update a job's progress (0.0 to 1.0).

        DB persistence is debounced: only persists when progress changes
        by 10% or more from the last persisted value.
        """
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.RUNNING:
            job.progress = min(max(progress, 0.0), 1.0)
            self._publish("kernel:job.progress", job)

            # Debounce DB writes — persist on significant changes (>=10%)
            last = self._last_persisted_progress.get(job_id, 0.0)
            if abs(job.progress - last) >= 0.1 or job.progress >= 1.0:
                self._last_persisted_progress[job_id] = job.progress
                await self._persist_update(job_id, progress=job.progress)

    async def start(self) -> None:
        """Start worker tasks."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker_loop(i), name=f"job-worker-{i}")
            self._workers.append(task)
        logger.info("JobQueue started with %d workers", self._max_workers)

    async def stop(self) -> None:
        """Stop all workers gracefully with a brief grace period."""
        if not self._running:
            return
        self._running = False

        # Put sentinel items to unblock workers waiting on empty queue
        for _ in self._workers:
            await self._queue.put((999, 999, None))  # type: ignore[arg-type]

        # Give workers a grace period to finish current jobs
        if self._workers:
            done, pending = await asyncio.wait(self._workers, timeout=2.0)
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._workers.clear()
        logger.info("JobQueue stopped")

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop: dequeue and execute jobs."""
        while self._running:
            try:
                _priority, _order, job = await self._queue.get()

                # Sentinel check
                if job is None:
                    break

                # Skip cancelled jobs
                if job.status == JobStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                await self._execute_job(job, worker_id)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Worker %d unexpected error", worker_id, exc_info=True)

    async def _execute_job(self, job: Job, worker_id: int) -> None:
        """Execute a single job with retry support."""
        handler = self._handlers.get(job.job_type)
        if handler is None:
            job.status = JobStatus.FAILED
            job.error = f"No handler registered for job type: {job.job_type}"
            job.completed_at = datetime.now(timezone.utc)
            await self._persist_update(
                job.id, status="failed", error=job.error,
                completed_at=job.completed_at,
            )
            self._publish("kernel:job.failed", job)
            logger.error("No handler for job type %r", job.job_type)
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        await self._persist_update(
            job.id, status="running", started_at=job.started_at,
        )
        self._publish("kernel:job.started", job)

        try:
            result = await handler(job)
            # Re-check for cancellation after handler returns
            if job.status == JobStatus.CANCELLED:
                return

            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            job.result = result if isinstance(result, dict) else {"result": result}
            job.completed_at = datetime.now(timezone.utc)
            await self._persist_update(
                job.id, status="completed", progress=1.0,
                result=job.result, completed_at=job.completed_at,
            )
            self._last_persisted_progress.pop(job.id, None)
            self._publish("kernel:job.completed", job)
            logger.info("Job completed: %s (worker=%d)", job.id, worker_id)

        except Exception as exc:
            job.retry_count += 1
            if job.retry_count <= job.max_retries:
                # Re-queue for retry
                job.status = JobStatus.PENDING
                job.error = str(exc)
                await self._persist_update(
                    job.id, status="pending", error=job.error,
                    retry_count=job.retry_count,
                )
                self._counter += 1
                await self._queue.put((-job.priority, self._counter, job))
                logger.warning(
                    "Job %s failed (attempt %d/%d), retrying: %s",
                    job.id, job.retry_count, job.max_retries + 1, exc,
                )
            else:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                await self._persist_update(
                    job.id, status="failed", error=job.error,
                    completed_at=job.completed_at,
                )
                self._last_persisted_progress.pop(job.id, None)
                self._publish("kernel:job.failed", job)
                logger.error("Job failed: %s (worker=%d): %s", job.id, worker_id, exc)

    # ------------------------------------------------------------------
    # DB persistence helpers (non-critical — errors are logged, not raised)
    # ------------------------------------------------------------------

    async def _persist_create(self, job: Job) -> None:
        """Persist a newly created job to the database."""
        if self._db_session_factory is None:
            return
        try:
            async with self._db_session_factory() as session:
                from kernel.repositories.job_queue import JobQueueRepository
                repo = JobQueueRepository(session)
                await repo.create_job(
                    job_id=job.id,
                    app_id=job.app_id,
                    job_type=job.job_type,
                    payload=job.payload,
                    priority=job.priority,
                    max_retries=job.max_retries,
                )
                await session.commit()
        except Exception:
            logger.debug("Failed to persist job creation: %s", job.id, exc_info=True)

    async def _persist_update(self, job_id: str, **kwargs: Any) -> None:
        """Persist job field updates to the database."""
        if self._db_session_factory is None:
            return
        try:
            async with self._db_session_factory() as session:
                from kernel.repositories.job_queue import JobQueueRepository
                repo = JobQueueRepository(session)
                await repo.update_job(job_id, **kwargs)
                await session.commit()
        except Exception:
            logger.debug("Failed to persist job update: %s", job_id, exc_info=True)

    async def recover_pending(self) -> None:
        """Load pending/running jobs from DB and re-queue them.

        Called on startup to recover jobs that were interrupted by a
        previous shutdown or crash. Running jobs are reset to pending
        since the handler is no longer executing.
        """
        if self._db_session_factory is None:
            return
        try:
            async with self._db_session_factory() as session:
                from kernel.repositories.job_queue import JobQueueRepository
                repo = JobQueueRepository(session)

                # Recover pending jobs
                pending = await repo.get_pending_jobs()

                # Also recover jobs that were running (interrupted by crash)
                running = await repo.list_jobs(status="running")

                # Reset running jobs to pending in DB
                for row in running:
                    await repo.update_job(row["id"], status="pending")
                await session.commit()

            recovered = pending + running
            if not recovered:
                return

            for row in recovered:
                job_id = row["id"]
                # Skip if already in memory (shouldn't happen on fresh startup)
                if job_id in self._jobs:
                    continue

                job = Job(
                    id=job_id,
                    app_id=row["app_id"],
                    job_type=row["job_type"],
                    payload=row.get("payload", {}),
                    priority=row.get("priority", 0),
                    status=JobStatus.PENDING,
                    max_retries=row.get("max_retries", 0),
                    retry_count=row.get("retry_count", 0),
                )
                self._jobs[job_id] = job
                self._counter += 1
                await self._queue.put((-job.priority, self._counter, job))

            logger.info("Recovered %d pending jobs from database", len(recovered))
        except Exception:
            logger.debug("Failed to recover pending jobs from database", exc_info=True)

    def _publish(self, event_type: str, job: Job, *, extra: dict | None = None) -> None:
        """Publish a job lifecycle event on the bus."""
        if self._bus is None:
            return
        data = {
            "job_id": job.id,
            "app_id": job.app_id,
            "job_type": job.job_type,
            "status": job.status.value,
            "progress": job.progress,
        }
        if extra:
            data.update(extra)
        try:
            self._bus.publish(event_type, data, "kernel")
        except Exception:
            logger.debug("Failed to publish %r for job %s", event_type, job.id, exc_info=True)
