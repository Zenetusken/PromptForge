"""Kernel router for Knowledge Base — project knowledge profiles and sources.

Route ordering: specific ``/sources/{source_id}`` paths are defined BEFORE
the catch-all ``/{app_id}/{entity_id}`` to prevent FastAPI from matching
source UUIDs as app_id/entity_id path parameters.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from kernel.bus.helpers import publish_event
from kernel.repositories.audit import AuditRepository
from kernel.repositories.knowledge import KnowledgeRepository
from kernel.security.access import AppContext, check_capability, check_quota
from kernel.security.dependencies import get_app_context, get_audit_repo, get_kernel_context

router = APIRouter(prefix="/api/kernel/knowledge", tags=["kernel-knowledge"])


def _get_repo(session: AsyncSession = Depends(get_db)) -> KnowledgeRepository:
    return KnowledgeRepository(session)


# --- Request schemas ---

class UpdateProfileRequest(BaseModel):
    name: str | None = None
    language: str | None = None
    framework: str | None = None
    description: str | None = None
    test_framework: str | None = None
    metadata_json: dict | None = None


class SyncAutoDetectedRequest(BaseModel):
    auto_detected: dict


class CreateSourceRequest(BaseModel):
    title: str
    content: str
    source_type: str = "document"


class UpdateSourceRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    source_type: str | None = None
    enabled: bool | None = None


class ReorderSourcesRequest(BaseModel):
    source_ids: list[str]


# ------------------------------------------------------------------ #
# Source-level endpoints (no app_id) — MUST come before /{app_id}/…  #
# ------------------------------------------------------------------ #

@router.patch("/sources/{source_id}")
async def update_source(
    source_id: str,
    body: UpdateSourceRequest,
    ctx: AppContext = Depends(get_kernel_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Update a knowledge source."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    source = await repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    fields = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not fields:
        return source

    try:
        updated = await repo.update_source(source_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await audit.log_action(
        source["profile_id"], "update", "knowledge_source", resource_id=source_id,
    )
    publish_event("kernel:knowledge.source_updated", {
        "source_id": source_id,
        "profile_id": source["profile_id"],
        "changed_fields": list(fields.keys()),
    }, "kernel")
    return updated


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    ctx: AppContext = Depends(get_kernel_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Delete a knowledge source."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    source = await repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    await repo.delete_source(source_id)
    await audit.log_action(
        source["profile_id"], "delete", "knowledge_source", resource_id=source_id,
    )
    publish_event("kernel:knowledge.source_removed", {
        "source_id": source_id,
        "profile_id": source["profile_id"],
    }, "kernel")
    return {"deleted": True}


@router.post("/sources/{source_id}/toggle")
async def toggle_source(
    source_id: str,
    ctx: AppContext = Depends(get_kernel_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Toggle a source's enabled state."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    source = await repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    updated = await repo.update_source(source_id, enabled=not source["enabled"])
    await audit.log_action(
        source["profile_id"], "toggle", "knowledge_source",
        resource_id=source_id,
        details={"enabled": updated["enabled"]},
    )
    publish_event("kernel:knowledge.source_updated", {
        "source_id": source_id,
        "profile_id": source["profile_id"],
        "changed_fields": ["enabled"],
    }, "kernel")
    return updated


# ------------------------------------------------------------------ #
# Profile endpoints (with app_id)                                    #
# ------------------------------------------------------------------ #

@router.get("/{app_id}/{entity_id}")
async def resolve_knowledge(
    app_id: str,
    entity_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: KnowledgeRepository = Depends(_get_repo),
):
    """Resolve a profile (manual > auto merge) with enabled sources."""
    check_capability(ctx, "knowledge:read")
    resolved = await repo.resolve(app_id, entity_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Knowledge profile not found")
    return resolved


@router.put("/{app_id}/{entity_id}")
async def upsert_profile(
    app_id: str,
    entity_id: str,
    body: UpdateProfileRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Create or update a knowledge profile."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    # Get or create
    profile = await repo.get_profile(app_id, entity_id)
    if not profile:
        name = body.name or entity_id
        profile = await repo.get_or_create_profile(app_id, entity_id, name)

    # Apply updates — exclude_unset preserves explicit null (to clear a field)
    fields = body.model_dump(exclude_unset=True)
    if fields:
        profile = await repo.update_profile(profile["id"], **fields)

    await audit.log_action(
        app_id, "upsert", "knowledge_profile", resource_id=profile["id"],
    )
    publish_event("kernel:knowledge.profile_updated", {
        "profile_id": profile["id"],
        "app_id": app_id,
        "entity_id": entity_id,
        "changed_fields": list(fields.keys()) if fields else [],
    }, "kernel")
    return profile


@router.delete("/{app_id}/{entity_id}")
async def delete_profile(
    app_id: str,
    entity_id: str,
    ctx: AppContext = Depends(get_app_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Delete a knowledge profile and cascade-delete its sources."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    profile = await repo.get_profile(app_id, entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Knowledge profile not found")

    profile_id = profile["id"]
    await repo.delete_profile(profile_id)
    await audit.log_action(
        app_id, "delete", "knowledge_profile", resource_id=profile_id,
    )
    publish_event("kernel:knowledge.profile_updated", {
        "profile_id": profile_id,
        "app_id": app_id,
        "entity_id": entity_id,
        "changed_fields": ["deleted"],
    }, "kernel")
    return {"deleted": True}


@router.post("/{app_id}/{entity_id}/sync")
async def sync_auto_detected(
    app_id: str,
    entity_id: str,
    body: SyncAutoDetectedRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Update auto_detected_json (workspace sync shadow fields)."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    # Auto-create profile if it doesn't exist
    profile = await repo.get_profile(app_id, entity_id)
    if not profile:
        profile = await repo.get_or_create_profile(app_id, entity_id, entity_id)

    updated = await repo.update_auto_detected(profile["id"], body.auto_detected)
    await audit.log_action(
        app_id, "sync", "knowledge_profile", resource_id=profile["id"],
    )
    publish_event("kernel:knowledge.profile_updated", {
        "profile_id": profile["id"],
        "app_id": app_id,
        "entity_id": entity_id,
        "changed_fields": ["auto_detected"],
    }, "kernel")
    return updated


# --- Source endpoints scoped under profile ---

@router.get("/{app_id}/{entity_id}/sources")
async def list_sources(
    app_id: str,
    entity_id: str,
    enabled_only: bool = Query(False),
    ctx: AppContext = Depends(get_app_context),
    repo: KnowledgeRepository = Depends(_get_repo),
):
    """List knowledge sources for a profile."""
    check_capability(ctx, "knowledge:read")

    profile = await repo.get_profile(app_id, entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Knowledge profile not found")

    sources = await repo.list_sources(profile["id"], enabled_only=enabled_only)
    total_chars = sum(s["char_count"] for s in sources)
    return {
        "items": sources,
        "total": len(sources),
        "total_chars": total_chars,
    }


@router.post("/{app_id}/{entity_id}/sources", status_code=201)
async def create_source(
    app_id: str,
    entity_id: str,
    body: CreateSourceRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Add a knowledge source to a profile."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    profile = await repo.get_profile(app_id, entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Knowledge profile not found")

    try:
        source = await repo.create_source(
            profile["id"], body.title, body.content, body.source_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    await audit.log_action(
        app_id, "create", "knowledge_source", resource_id=source["id"],
    )
    publish_event("kernel:knowledge.source_added", {
        "source_id": source["id"],
        "profile_id": profile["id"],
        "title": body.title,
        "source_type": body.source_type,
    }, "kernel")
    return source


@router.put("/{app_id}/{entity_id}/sources/reorder")
async def reorder_sources(
    app_id: str,
    entity_id: str,
    body: ReorderSourcesRequest,
    ctx: AppContext = Depends(get_app_context),
    repo: KnowledgeRepository = Depends(_get_repo),
    audit: AuditRepository = Depends(get_audit_repo),
):
    """Reorder sources for a profile."""
    check_capability(ctx, "knowledge:write")
    await check_quota(ctx, "api_calls", audit)

    profile = await repo.get_profile(app_id, entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Knowledge profile not found")

    try:
        await repo.reorder_sources(profile["id"], body.source_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await audit.log_action(
        app_id, "reorder", "knowledge_source", resource_id=profile["id"],
    )
    publish_event("kernel:knowledge.source_updated", {
        "source_id": None,
        "profile_id": profile["id"],
        "changed_fields": ["order_index"],
    }, "kernel")
    return {"reordered": True}
