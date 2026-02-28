"""Repository for kernel audit log and app usage tracking."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from kernel.models.audit import AppUsage, AuditLog


def _current_period() -> str:
    """Return the current hourly period string for quota tracking."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H")


class AuditRepository:
    """Data access for audit_log and app_usage tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Audit log ---

    async def log_action(
        self,
        app_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
    ) -> dict:
        """Record an audit log entry."""
        entry = AuditLog(
            app_id=app_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=json.dumps(details) if details else None,
            timestamp=datetime.now(timezone.utc),
        )
        self.session.add(entry)
        await self.session.flush()
        return self._log_to_dict(entry)

    async def list_logs(
        self, app_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """List audit log entries for an app, most recent first."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.app_id == app_id)
            .order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._log_to_dict(entry) for entry in result.scalars().all()]

    async def count_logs(self, app_id: str) -> int:
        """Count total audit log entries for an app."""
        result = await self.session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.app_id == app_id)
        )
        return result.scalar_one()

    # --- Usage tracking ---

    async def get_usage(self, app_id: str, resource: str) -> int:
        """Get current usage count for a resource in the current period."""
        period = _current_period()
        result = await self.session.execute(
            select(AppUsage).where(
                AppUsage.app_id == app_id,
                AppUsage.resource == resource,
                AppUsage.period == period,
            )
        )
        usage = result.scalar_one_or_none()
        return usage.count if usage else 0

    async def increment_usage(self, app_id: str, resource: str) -> int:
        """Increment usage for a resource in the current period. Returns new count."""
        period = _current_period()
        result = await self.session.execute(
            select(AppUsage).where(
                AppUsage.app_id == app_id,
                AppUsage.resource == resource,
                AppUsage.period == period,
            )
        )
        usage = result.scalar_one_or_none()

        if usage:
            usage.count += 1
            usage.updated_at = datetime.now(timezone.utc)
        else:
            usage = AppUsage(
                app_id=app_id,
                resource=resource,
                period=period,
                count=1,
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(usage)

        await self.session.flush()
        return usage.count

    async def get_all_usage(self, app_id: str) -> list[dict]:
        """Get all current-period usage entries for an app."""
        period = _current_period()
        result = await self.session.execute(
            select(AppUsage).where(
                AppUsage.app_id == app_id,
                AppUsage.period == period,
            ).order_by(AppUsage.resource)
        )
        return [
            {
                "resource": u.resource,
                "count": u.count,
                "period": u.period,
                "updated_at": u.updated_at.isoformat(),
            }
            for u in result.scalars().all()
        ]

    # --- Helpers ---

    def _log_to_dict(self, entry: AuditLog) -> dict:
        return {
            "id": entry.id,
            "app_id": entry.app_id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "details": json.loads(entry.details_json) if entry.details_json else None,
            "timestamp": entry.timestamp.isoformat(),
        }
