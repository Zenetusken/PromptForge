"""Kernel router for per-app settings — CRUD on key/value pairs."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.repositories.app_settings import AppSettingsRepository
from kernel.repositories.audit import AuditRepository
from kernel.security.access import AppContext, check_capability, check_quota
from kernel.security.dependencies import get_app_context, get_audit_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kernel/settings", tags=["kernel-settings"])


def _get_repo(session: AsyncSession = Depends(get_db)) -> AppSettingsRepository:
    return AppSettingsRepository(session)


def _validate_settings_schema(app_id: str, settings: dict) -> None:
    """Validate incoming settings keys/types against the app's manifest schema.

    Apps without a settings schema in their manifest accept any key-value.
    Apps *with* a schema reject unknown keys (422) and type mismatches (422).
    """
    from kernel.registry.app_registry import get_app_registry

    registry = get_app_registry()
    record = registry.get(app_id)
    if not record:
        return  # Unknown app — no schema to validate against

    manifest_settings = record.manifest.frontend.settings
    if not manifest_settings or not manifest_settings.schema_:
        return  # No schema defined — accept anything

    schema = manifest_settings.schema_
    for key in settings:
        if key not in schema:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown setting key {key!r} for app {app_id!r}. "
                f"Valid keys: {list(schema.keys())}",
            )
        # Type-check values if a type spec exists
        spec = schema[key]
        if isinstance(spec, dict) and "type" in spec:
            expected_type = spec["type"]
            value = settings[key]
            type_map = {
                "string": str,
                "boolean": bool,
                "integer": int,
                "number": (int, float),
            }
            python_type = type_map.get(expected_type)
            if python_type and (
                not isinstance(value, python_type)
                # bool is a subclass of int in Python — reject booleans for integer/number
                or (expected_type in ("integer", "number") and isinstance(value, bool))
            ):
                raise HTTPException(
                    status_code=422,
                    detail=f"Setting {key!r} expects type {expected_type!r}, "
                    f"got {type(value).__name__!r}",
                )


@router.get("/{app_id}")
async def get_settings(
    app_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: AppSettingsRepository = Depends(_get_repo),
):
    """Get all settings for an app."""
    check_capability(ctx, "settings:read")
    settings = await repo.get_all(app_id)
    return {"app_id": app_id, "settings": settings}


@router.put("/{app_id}")
async def update_settings(
    app_id: str,
    body: dict,
    ctx: AppContext = Depends(get_app_context),
    repo: AppSettingsRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Update settings for an app (merge — only provided keys are updated)."""
    check_capability(ctx, "settings:write")
    await check_quota(ctx, "api_calls", audit)
    settings = body.get("settings", body)
    _validate_settings_schema(app_id, settings)
    await repo.set_all(app_id, settings)
    all_settings = await repo.get_all(app_id)
    await audit.log_action(app_id, "update", "settings", details={"keys": list(settings.keys())})
    return {"app_id": app_id, "settings": all_settings}


@router.delete("/{app_id}")
async def reset_settings(
    app_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: AppSettingsRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Reset all settings for an app."""
    check_capability(ctx, "settings:write")
    await check_quota(ctx, "api_calls", audit)
    count = await repo.reset(app_id)
    await audit.log_action(app_id, "reset", "settings")
    return {"app_id": app_id, "deleted": count}
