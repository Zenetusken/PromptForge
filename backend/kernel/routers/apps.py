"""Kernel router for app management — list installed apps and their status."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from kernel.bus.helpers import publish_event
from kernel.registry.app_registry import AppStatus, get_app_registry
from kernel.repositories.audit import AuditRepository
from kernel.security.dependencies import get_audit_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kernel", tags=["kernel"])


def _check_services_satisfied(required: list[str]) -> bool:
    """Check if all required services are registered in the kernel."""
    if not required:
        return True
    registry = get_app_registry()
    kernel = registry.kernel
    if kernel is not None and hasattr(kernel, "services"):
        return len(kernel.services.validate_requirements(required)) == 0
    return True  # Assume satisfied if kernel not yet booted


@router.get("/apps")
async def list_apps():
    """List all installed apps and their status."""
    registry = get_app_registry()
    return {
        "apps": [
            {
                "id": rec.manifest.id,
                "name": rec.manifest.name,
                "version": rec.manifest.version,
                "icon": rec.manifest.icon,
                "accent_color": rec.manifest.accent_color,
                "status": rec.status,
                "error": rec.error,
                "requires_services": rec.manifest.requires_services,
                "services_satisfied": _check_services_satisfied(
                    rec.manifest.requires_services,
                ),
                "resource_quotas": {
                    "max_storage_mb": rec.manifest.resource_quotas.max_storage_mb,
                    "max_api_calls_per_hour": rec.manifest.resource_quotas.max_api_calls_per_hour,
                    "max_documents": rec.manifest.resource_quotas.max_documents,
                },
                "windows": len(rec.manifest.frontend.windows),
                "routers": len(rec.manifest.backend.routers),
            }
            for rec in registry.list_all()
        ]
    }


@router.get("/apps/{app_id}")
async def get_app(app_id: str):
    """Get details for a specific app."""
    registry = get_app_registry()
    rec = registry.get(app_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"App {app_id!r} not found")
    return {
        "id": rec.manifest.id,
        "name": rec.manifest.name,
        "version": rec.manifest.version,
        "icon": rec.manifest.icon,
        "accent_color": rec.manifest.accent_color,
        "status": rec.status,
        "error": rec.error,
        "requires_services": rec.manifest.requires_services,
        "services_satisfied": _check_services_satisfied(
            rec.manifest.requires_services,
        ),
        "manifest": rec.manifest.model_dump(),
    }


@router.get("/apps/{app_id}/status")
async def get_app_status(app_id: str):
    """Get detailed status for a specific app."""
    registry = get_app_registry()
    rec = registry.get(app_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"App {app_id!r} not found")
    return {
        "id": rec.manifest.id,
        "status": rec.status,
        "error": rec.error,
        "capabilities": {
            "required": rec.manifest.capabilities.required,
            "optional": rec.manifest.capabilities.optional,
        },
        "resource_quotas": {
            "max_storage_mb": rec.manifest.resource_quotas.max_storage_mb,
            "max_api_calls_per_hour": rec.manifest.resource_quotas.max_api_calls_per_hour,
            "max_documents": rec.manifest.resource_quotas.max_documents,
        },
        "services_satisfied": _check_services_satisfied(
            rec.manifest.requires_services,
        ),
    }


async def _persist_app_states(registry, kernel) -> None:
    """Persist current app states to the database (best-effort)."""
    if kernel and hasattr(kernel, "db_session_factory") and kernel.db_session_factory:
        try:
            await registry.persist_app_states(kernel.db_session_factory)
        except Exception:
            logger.debug("Failed to persist app states", exc_info=True)


@router.post("/apps/{app_id}/enable")
async def enable_app(
    app_id: str,
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Enable a disabled app."""
    registry = get_app_registry()
    rec = registry.get(app_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"App {app_id!r} not found")
    if rec.status == AppStatus.ENABLED:
        return {"id": app_id, "status": rec.status, "message": "Already enabled"}

    registry.enable_app(app_id)
    kernel = registry.kernel

    # Call on_enable lifecycle hook
    try:
        await rec.instance.on_enable(kernel)
    except Exception as exc:
        logger.error("App %r on_enable failed: %s", app_id, exc)

    # Call on_startup lifecycle hook
    try:
        await rec.instance.on_startup(kernel)
    except Exception as exc:
        logger.error("App %r on_startup failed: %s", app_id, exc)

    await _persist_app_states(registry, kernel)
    await audit.log_action(app_id, "enable", "app", resource_id=app_id)

    publish_event("kernel:app.enabled", {"app_id": app_id, "status": rec.status}, "kernel")
    publish_event("kernel:audit.logged", {
        "app_id": app_id, "action": "enable", "resource_type": "app",
    }, "kernel")

    return {"id": app_id, "status": rec.status}


@router.post("/apps/{app_id}/disable")
async def disable_app(
    app_id: str,
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Disable an enabled app."""
    registry = get_app_registry()
    rec = registry.get(app_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"App {app_id!r} not found")
    if rec.status == AppStatus.DISABLED:
        return {"id": app_id, "status": rec.status, "message": "Already disabled"}

    kernel = registry.kernel

    # Call on_shutdown lifecycle hook
    try:
        await rec.instance.on_shutdown(kernel)
    except Exception as exc:
        logger.error("App %r on_shutdown failed: %s", app_id, exc)

    # Call on_disable lifecycle hook
    try:
        await rec.instance.on_disable(kernel)
    except Exception as exc:
        logger.error("App %r on_disable failed: %s", app_id, exc)

    registry.disable_app(app_id)

    await _persist_app_states(registry, kernel)
    await audit.log_action(app_id, "disable", "app", resource_id=app_id)

    publish_event("kernel:app.disabled", {"app_id": app_id, "status": rec.status}, "kernel")
    publish_event("kernel:audit.logged", {
        "app_id": app_id, "action": "disable", "resource_type": "app",
    }, "kernel")

    return {"id": app_id, "status": rec.status}
