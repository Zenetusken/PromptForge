"""FastAPI dependencies for kernel access control.

Provides ``get_app_context`` and ``get_audit_repo`` for use in kernel router
endpoints. Access control is opt-in: only apps that declare capabilities in
their manifest are subject to enforcement. Unknown or unregistered apps
receive a permissive context.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.repositories.audit import AuditRepository
from kernel.security.access import PERMISSIVE_CAPABILITIES, AppContext

logger = logging.getLogger(__name__)


def get_app_context(app_id: str) -> AppContext:
    """Resolve AppContext from the app's manifest in the registry.

    If the app is not found in the registry (e.g. ad-hoc request,
    test without full registry), returns a permissive context that
    allows all operations. Access control only restricts apps that
    explicitly declare limited capabilities in their manifest.
    """
    from kernel.registry.app_registry import AppStatus, get_app_registry

    registry = get_app_registry()
    record = registry.get(app_id)
    if record:
        if record.status == AppStatus.DISABLED:
            raise HTTPException(
                status_code=503,
                detail=f"App '{app_id}' is currently disabled",
            )
        return AppContext.from_manifest(record.manifest)
    # Unknown app — permissive (backward compat, tests, ad-hoc API calls)
    logger.warning(
        "App %r not found in registry — granting permissive capabilities. "
        "Register the app with a manifest to enforce access control.",
        app_id,
    )
    return AppContext(app_id=app_id, capabilities=list(PERMISSIVE_CAPABILITIES))


def get_audit_repo(session: AsyncSession = Depends(get_db)) -> AuditRepository:
    """Provide an AuditRepository for audit logging."""
    return AuditRepository(session)
