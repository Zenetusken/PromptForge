"""Kernel router for audit log and usage tracking."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.repositories.audit import AuditRepository
from kernel.security.access import AppContext, check_capability
from kernel.security.dependencies import get_app_context, get_kernel_context

router = APIRouter(prefix="/api/kernel/audit", tags=["kernel-audit"])


def _get_repo(session: AsyncSession = Depends(get_db)) -> AuditRepository:
    return AuditRepository(session)


# --- Cross-app endpoints (no app_id filter) --- must be before /{app_id}

@router.get("/all")
async def list_all_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    ctx: AppContext = Depends(get_kernel_context),
    repo: AuditRepository = Depends(_get_repo),
):
    """List audit log entries across all apps with optional filters."""
    check_capability(ctx, "audit:read")
    logs = await repo.list_all_logs(
        limit=limit, offset=offset, action=action, resource_type=resource_type
    )
    total = await repo.count_all_logs(action=action, resource_type=resource_type)
    return {"logs": logs, "total": total}


@router.get("/summary")
async def get_audit_summary(
    ctx: AppContext = Depends(get_kernel_context),
    repo: AuditRepository = Depends(_get_repo),
):
    """Get aggregate audit counts by app_id and action type."""
    check_capability(ctx, "audit:read")
    summary = await repo.get_summary()
    return {"summary": summary}


@router.get("/usage")
async def get_all_apps_usage(
    ctx: AppContext = Depends(get_kernel_context),
    repo: AuditRepository = Depends(_get_repo),
):
    """Get current-period usage for all apps."""
    check_capability(ctx, "audit:read")
    usage = await repo.get_all_apps_usage()
    return {"usage": usage}


# --- Per-app endpoints ---

# Usage endpoint must be before the catch-all /{app_id} to avoid shadowing
@router.get("/usage/{app_id}")
async def get_usage(
    app_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: AuditRepository = Depends(_get_repo),
):
    """Get current quota usage for an app."""
    check_capability(ctx, "audit:read")
    usage = await repo.get_all_usage(app_id)
    return {"app_id": app_id, "usage": usage}


@router.get("/{app_id}")
async def list_audit_logs(
    app_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: AppContext = Depends(get_app_context),
    repo: AuditRepository = Depends(_get_repo),
):
    """List audit log entries for an app."""
    check_capability(ctx, "audit:read")
    logs = await repo.list_logs(app_id, limit=limit, offset=offset)
    total = await repo.count_logs(app_id)
    return {"app_id": app_id, "logs": logs, "total": total}
