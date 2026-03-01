"""Repository for persisting kernel jobs to the database."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class JobQueueRepository:
    """Persists job records to the kernel_jobs table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        job_id: str,
        app_id: str,
        job_type: str,
        payload: dict | None = None,
        priority: int = 0,
        max_retries: int = 0,
    ) -> dict:
        """Insert a new job record."""
        now = datetime.now(timezone.utc)
        await self._session.execute(
            text(
                "INSERT INTO kernel_jobs "
                "(id, app_id, job_type, payload_json, priority, status, "
                "progress, max_retries, retry_count, created_at) "
                "VALUES (:id, :app_id, :job_type, :payload_json, :priority, "
                "'pending', 0.0, :max_retries, 0, :created_at)"
            ),
            {
                "id": job_id,
                "app_id": app_id,
                "job_type": job_type,
                "payload_json": json.dumps(payload or {}),
                "priority": priority,
                "max_retries": max_retries,
                "created_at": now,
            },
        )
        return {
            "id": job_id,
            "app_id": app_id,
            "job_type": job_type,
            "status": "pending",
            "created_at": now.isoformat(),
        }

    async def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        result: dict | None = None,
        error: str | None = None,
        progress: float | None = None,
        retry_count: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update job fields."""
        parts: list[str] = []
        params: dict = {"id": job_id}

        if status is not None:
            parts.append("status = :status")
            params["status"] = status
        if result is not None:
            parts.append("result_json = :result_json")
            params["result_json"] = json.dumps(result)
        if error is not None:
            parts.append("error = :error")
            params["error"] = error
        if progress is not None:
            parts.append("progress = :progress")
            params["progress"] = progress
        if retry_count is not None:
            parts.append("retry_count = :retry_count")
            params["retry_count"] = retry_count
        if started_at is not None:
            parts.append("started_at = :started_at")
            params["started_at"] = started_at
        if completed_at is not None:
            parts.append("completed_at = :completed_at")
            params["completed_at"] = completed_at

        if not parts:
            return

        sql = f"UPDATE kernel_jobs SET {', '.join(parts)} WHERE id = :id"
        await self._session.execute(text(sql), params)

    async def get_job(self, job_id: str) -> dict | None:
        """Get a job by ID."""
        result = await self._session.execute(
            text("SELECT * FROM kernel_jobs WHERE id = :id"), {"id": job_id}
        )
        row = result.mappings().first()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def list_jobs(
        self,
        app_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List jobs with optional filters."""
        where: list[str] = []
        params: dict = {"limit": limit, "offset": offset}

        if app_id:
            where.append("app_id = :app_id")
            params["app_id"] = app_id
        if status:
            where.append("status = :status")
            params["status"] = status

        where_clause = f" WHERE {' AND '.join(where)}" if where else ""
        sql = (
            f"SELECT * FROM kernel_jobs{where_clause}"
            " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        )
        result = await self._session.execute(text(sql), params)
        return [self._row_to_dict(row) for row in result.mappings().all()]

    async def get_pending_jobs(self) -> list[dict]:
        """Get all pending jobs (for crash recovery)."""
        result = await self._session.execute(
            text(
                "SELECT * FROM kernel_jobs WHERE status = 'pending'"
                " ORDER BY priority DESC, created_at ASC"
            )
        )
        return [self._row_to_dict(row) for row in result.mappings().all()]

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert a DB row to a dict."""
        d = dict(row)
        # Parse JSON fields
        if d.get("payload_json"):
            try:
                d["payload"] = json.loads(d["payload_json"])
            except (json.JSONDecodeError, TypeError):
                d["payload"] = {}
        else:
            d["payload"] = {}
        del d["payload_json"]

        if d.get("result_json"):
            try:
                d["result"] = json.loads(d["result_json"])
            except (json.JSONDecodeError, TypeError):
                d["result"] = None
        else:
            d["result"] = None
        if "result_json" in d:
            del d["result_json"]

        # Format timestamps
        for ts_field in ("created_at", "started_at", "completed_at"):
            val = d.get(ts_field)
            if val and hasattr(val, "isoformat"):
                d[ts_field] = val.isoformat()

        return d
