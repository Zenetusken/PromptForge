"""Repository for per-app settings CRUD."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel.models.app_settings import AppSettings


class AppSettingsRepository:
    """Data access for the app_settings table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self, app_id: str) -> dict[str, object]:
        """Get all settings for an app as a {key: value} dict."""
        result = await self.session.execute(
            select(AppSettings).where(AppSettings.app_id == app_id)
        )
        rows = result.scalars().all()
        return {row.key: json.loads(row.value) for row in rows}

    async def get(self, app_id: str, key: str) -> object | None:
        """Get a single setting value. Returns None if not found."""
        result = await self.session.execute(
            select(AppSettings).where(
                AppSettings.app_id == app_id, AppSettings.key == key
            )
        )
        row = result.scalar_one_or_none()
        return json.loads(row.value) if row else None

    async def set(self, app_id: str, key: str, value: object) -> None:
        """Set a setting value (upsert)."""
        now = datetime.now(timezone.utc)
        json_value = json.dumps(value)

        result = await self.session.execute(
            select(AppSettings).where(
                AppSettings.app_id == app_id, AppSettings.key == key
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = json_value
            existing.updated_at = now
        else:
            self.session.add(
                AppSettings(
                    app_id=app_id,
                    key=key,
                    value=json_value,
                    created_at=now,
                    updated_at=now,
                )
            )

    async def set_all(self, app_id: str, settings: dict[str, object]) -> None:
        """Set multiple settings at once."""
        for key, value in settings.items():
            await self.set(app_id, key, value)

    async def delete(self, app_id: str, key: str) -> bool:
        """Delete a single setting. Returns True if deleted."""
        result = await self.session.execute(
            delete(AppSettings).where(
                AppSettings.app_id == app_id, AppSettings.key == key
            )
        )
        return result.rowcount > 0

    async def reset(self, app_id: str) -> int:
        """Delete all settings for an app. Returns count deleted."""
        result = await self.session.execute(
            delete(AppSettings).where(AppSettings.app_id == app_id)
        )
        return result.rowcount
