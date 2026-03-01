"""Kernel router for the background job queue."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from kernel.security.dependencies import get_kernel_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kernel/jobs", tags=["kernel-jobs"])


class SubmitJobRequest(BaseModel):
    app_id: str
    job_type: str
    payload: dict = {}
    priority: int = 0
    max_retries: int = 0


def _get_job_queue(request: Request):
    """Resolve the JobQueue service from the kernel."""
    kernel = getattr(request.app, "_kernel", None)
    if kernel is None:
        from kernel.registry.app_registry import get_app_registry
        registry = get_app_registry()
        kernel = registry.kernel
    if kernel is None or not kernel.services.has("jobs"):
        raise HTTPException(status_code=503, detail="Job queue service not available")
    return kernel.services.get("jobs")


@router.post("/submit", status_code=202)
async def submit_job(body: SubmitJobRequest, request: Request):
    """Submit a background job."""
    queue = _get_job_queue(request)
    job_id = await queue.submit(
        app_id=body.app_id,
        job_type=body.job_type,
        payload=body.payload,
        priority=body.priority,
        max_retries=body.max_retries,
    )
    job = queue.get_job(job_id)
    return {"job_id": job_id, "status": "pending", "job": job.to_dict() if job else None}


@router.get("/{job_id}")
async def get_job(job_id: str, request: Request):
    """Get a job by ID."""
    queue = _get_job_queue(request)
    job = queue.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job.to_dict()


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request):
    """Cancel a pending or running job."""
    queue = _get_job_queue(request)
    cancelled = await queue.cancel(job_id)
    if not cancelled:
        job = queue.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id!r} cannot be cancelled (status: {job.status.value})",
        )
    return {"job_id": job_id, "status": "cancelled"}


@router.get("")
async def list_jobs(
    request: Request,
    app_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List jobs with optional filters."""
    queue = _get_job_queue(request)

    from kernel.services.job_queue import JobStatus
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status!r}")

    jobs = queue.list_jobs(app_id=app_id, status=status_filter)
    # Apply limit
    jobs = jobs[:limit]
    return {"jobs": [j.to_dict() for j in jobs], "total": len(jobs)}
