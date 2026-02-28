"""Kernel router for app management — list installed apps and their status."""

from fastapi import APIRouter

from kernel.registry.app_registry import get_app_registry

router = APIRouter(prefix="/api/kernel", tags=["kernel"])


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
        from fastapi import HTTPException

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
        "manifest": rec.manifest.model_dump(),
    }
