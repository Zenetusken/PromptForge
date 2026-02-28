"""Access control — capability checking and quota enforcement.

Apps declare capabilities in their manifest. Kernel routers use ``AppContext``
to verify that the calling app has the required capability before proceeding.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from kernel.registry.manifest import AppManifest
    from kernel.repositories.audit import AuditRepository

logger = logging.getLogger(__name__)

# Capabilities granted to unknown/unregistered apps (backward compat, tests, ad-hoc API).
PERMISSIVE_CAPABILITIES: frozenset[str] = frozenset({
    "settings:read", "settings:write",
    "storage:read", "storage:write",
    "vfs:read", "vfs:write",
    "llm:invoke",
})


@dataclass(frozen=True)
class AppContext:
    """Request-scoped context identifying the calling app and its permissions."""

    app_id: str
    capabilities: list[str] = field(default_factory=list)
    max_storage_mb: int = 100
    max_api_calls_per_hour: int = 1000
    max_documents: int = 10000

    @classmethod
    def from_manifest(cls, manifest: AppManifest) -> AppContext:
        """Build an AppContext from an app manifest."""
        all_caps = manifest.capabilities.required + manifest.capabilities.optional
        return cls(
            app_id=manifest.id,
            capabilities=all_caps,
            max_storage_mb=manifest.resource_quotas.max_storage_mb,
            max_api_calls_per_hour=manifest.resource_quotas.max_api_calls_per_hour,
            max_documents=manifest.resource_quotas.max_documents,
        )


def check_capability(ctx: AppContext, required: str) -> None:
    """Raise 403 if the app context doesn't include the required capability.

    Parameters
    ----------
    ctx:
        The request-scoped app context.
    required:
        A capability string like ``"storage:read"`` or ``"llm:invoke"``.
    """
    if required not in ctx.capabilities:
        logger.warning(
            "App %r denied: missing capability %r (has: %s)",
            ctx.app_id, required, ctx.capabilities,
        )
        raise HTTPException(
            status_code=403,
            detail=f"App '{ctx.app_id}' lacks required capability: {required}",
        )


async def check_quota(
    ctx: AppContext, resource: str, audit_repo: AuditRepository,
) -> None:
    """Raise 429 if the app has exceeded its quota for the given resource.

    Parameters
    ----------
    ctx:
        The request-scoped app context.
    resource:
        Resource identifier, e.g. ``"api_calls"`` or ``"documents"``.
    audit_repo:
        Repository for usage tracking.
    """
    usage = await audit_repo.get_usage(ctx.app_id, resource)

    limit = None
    if resource == "api_calls":
        limit = ctx.max_api_calls_per_hour
    elif resource == "documents":
        limit = ctx.max_documents

    if limit is not None and usage >= limit:
        logger.warning(
            "App %r quota exceeded for %r: %d >= %d",
            ctx.app_id, resource, usage, limit,
        )
        raise HTTPException(
            status_code=429,
            detail=f"App '{ctx.app_id}' has exceeded quota for {resource}",
        )

    await audit_repo.increment_usage(ctx.app_id, resource)
