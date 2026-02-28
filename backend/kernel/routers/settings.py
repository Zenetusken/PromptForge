"""Kernel router for per-app settings — CRUD on key/value pairs."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.repositories.app_settings import AppSettingsRepository

router = APIRouter(prefix="/api/kernel/settings", tags=["kernel-settings"])


def _get_repo(session: AsyncSession = Depends(get_db)) -> AppSettingsRepository:
    return AppSettingsRepository(session)


@router.get("/{app_id}")
async def get_settings(app_id: str, repo: AppSettingsRepository = Depends(_get_repo)):
    """Get all settings for an app."""
    settings = await repo.get_all(app_id)
    return {"app_id": app_id, "settings": settings}


@router.put("/{app_id}")
async def update_settings(
    app_id: str,
    body: dict,
    repo: AppSettingsRepository = Depends(_get_repo),
):
    """Update settings for an app (merge — only provided keys are updated)."""
    settings = body.get("settings", body)
    await repo.set_all(app_id, settings)
    # Return updated settings
    all_settings = await repo.get_all(app_id)
    return {"app_id": app_id, "settings": all_settings}


@router.delete("/{app_id}")
async def reset_settings(app_id: str, repo: AppSettingsRepository = Depends(_get_repo)):
    """Reset all settings for an app."""
    count = await repo.reset(app_id)
    return {"app_id": app_id, "deleted": count}
