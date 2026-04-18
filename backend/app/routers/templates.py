"""Template library + lifecycle endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.rate_limit import RateLimit
from app.schemas.templates import RetireRequest, TemplateListResponse, TemplateRead
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api", tags=["templates"])

_svc = TemplateService()


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    project_id: str | None = Query(None),
    include_retired: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> TemplateListResponse:
    page = await _svc.list_for_project(
        project_id,
        db,
        include_retired=include_retired,
        limit=limit,
        offset=offset,
    )
    return TemplateListResponse(
        total=page.total,
        count=page.count,
        offset=page.offset,
        items=[TemplateRead.model_validate(t) for t in page.items],
        has_more=page.has_more,
        next_offset=page.next_offset,
    )


@router.get("/templates/{template_id}", response_model=TemplateRead)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    tpl = await _svc.get(template_id, db)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateRead.model_validate(tpl)


@router.post(
    "/clusters/{cluster_id}/fork-template",
    response_model=TemplateRead,
    dependencies=[Depends(RateLimit(lambda: "10/minute"))],
)
async def fork_template(
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    tpl = await _svc.fork_from_cluster(cluster_id, db, auto=False)
    if tpl is None:
        raise HTTPException(
            status_code=400,
            detail="Cluster has no optimizations to fork from",
        )
    await db.commit()
    return TemplateRead.model_validate(tpl)


@router.post("/templates/{template_id}/retire", response_model=TemplateRead)
async def retire_template(
    template_id: str,
    body: RetireRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    reason = body.reason if body else "manual"
    ok = await _svc.retire(template_id, db, reason=reason)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Template not found or already retired"
        )
    await db.commit()
    tpl = await _svc.get(template_id, db)
    return TemplateRead.model_validate(tpl)


@router.post(
    "/templates/{template_id}/use",
    response_model=TemplateRead,
    dependencies=[Depends(RateLimit(lambda: "30/minute"))],
)
async def use_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> TemplateRead:
    tpl = await _svc.get(template_id, db)
    if tpl is None or tpl.retired_at is not None:
        raise HTTPException(status_code=404, detail="Template not found or retired")
    await _svc.increment_usage(template_id, db)
    await db.commit()
    tpl = await _svc.get(template_id, db)
    return TemplateRead.model_validate(tpl)
