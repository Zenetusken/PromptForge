"""Optimization endpoints for running the prompt optimization pipeline."""

import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.constants import OptimizationStatus, ProjectStatus
from app.converters import (
    deserialize_json_field,
    optimization_to_response,
    update_optimization_status,
)
from app.database import get_db
from app.models.optimization import Optimization
from app.providers import LLMProvider, get_provider
from app.providers.errors import ProviderError
from app.repositories.optimization import OptimizationRepository
from app.repositories.project import (
    ProjectRepository,
    ensure_project_by_name,
    ensure_prompt_in_project,
)
from app.schemas.optimization import OptimizationResponse, OptimizeRequest
from app.middleware.sanitize import sanitize_text
from app.services.pipeline import PipelineComplete, run_pipeline_streaming

logger = logging.getLogger(__name__)

router = APIRouter(tags=["optimize"])


async def _is_project_archived(db: AsyncSession, project_id: str) -> bool:
    """Return True if the project exists and is archived."""
    proj = await ProjectRepository(db).get_by_id(project_id, load_prompts=False)
    return bool(proj and proj.status == ProjectStatus.ARCHIVED)


def _resolve_provider(
    provider_name: str | None,
    api_key: str | None,
    model: str | None,
) -> LLMProvider | None:
    """Resolve an explicit provider selection, returning None for auto-detect."""
    if not provider_name:
        return None
    return get_provider(provider_name, api_key=api_key, model=model)


def _create_streaming_response(
    opt_id: str,
    raw_prompt: str,
    start_time: float,
    metadata: dict[str, Any] | None = None,
    llm_provider: LLMProvider | None = None,
    strategy_override: str | None = None,
    secondary_frameworks_override: list[str] | None = None,
) -> StreamingResponse:
    """Create a StreamingResponse wrapping the pipeline with DB persistence."""

    # Build complete_metadata with id so the pipeline injects it directly
    complete_metadata: dict = {"id": opt_id}
    if metadata:
        complete_metadata.update(metadata)

    # Eagerly compute model_fallback from the explicit provider or current
    # auto-detect default so we never call get_provider() again at persist time.
    if llm_provider:
        model_fallback = llm_provider.model_name
    else:
        try:
            model_fallback = get_provider().model_name
        except (RuntimeError, ImportError, ProviderError):
            model_fallback = config.CLAUDE_MODEL

    async def event_stream():
        final_data = {}
        pending_complete_event: str | None = None
        try:
            stream = run_pipeline_streaming(
                raw_prompt,
                llm_provider=llm_provider,
                complete_metadata=complete_metadata,
                strategy_override=strategy_override,
                secondary_frameworks_override=secondary_frameworks_override,
            )
            async for event in stream:
                if isinstance(event, PipelineComplete):
                    final_data = event.data
                    continue
                # Hold the SSE complete event so we can persist before sending it
                if isinstance(event, str) and "event: complete\n" in event:
                    pending_complete_event = event
                    continue
                yield event
        except Exception as e:
            from app.providers.errors import RateLimitError as _RLE

            error_data: dict[str, object] = {
                "status": OptimizationStatus.ERROR,
                "error": str(e),
            }
            if isinstance(e, _RLE):
                error_data["error_type"] = "rate_limit"
                if e.retry_after is not None:
                    error_data["retry_after"] = int(e.retry_after)
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            await update_optimization_status(opt_id, error=str(e))
            return

        # Persist to DB BEFORE sending the complete event to the client,
        # so immediate GET /optimize/{id} requests see the updated record.
        try:
            await update_optimization_status(
                opt_id,
                result_data=final_data,
                start_time=start_time,
                model_fallback=model_fallback,
            )
        except Exception:
            logger.error("DB update failed for optimization %s", opt_id, exc_info=True)
            err_payload = json.dumps({
                "status": "error",
                "error": "Failed to save result",
                "persisted": False,
                "id": opt_id,
            })
            yield f"event: error\ndata: {err_payload}\n\n"
            return

        # Now send the complete event after DB is updated
        if pending_complete_event:
            yield pending_complete_event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/optimize")
async def optimize_prompt(
    request: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    """Run the prompt optimization pipeline.

    Accepts a raw prompt and returns a Server-Sent Events stream with
    real-time updates as the pipeline progresses through analysis,
    optimization, and validation stages.

    Optional headers:
    - ``X-LLM-API-Key``: Runtime API key override (never logged)
    - ``X-LLM-Model``: Runtime model override
    - ``X-LLM-Provider``: Provider name (body ``request.provider`` takes precedence)
    """
    # Resolve explicit provider selection BEFORE creating DB record
    # to avoid orphaned "running" records on invalid provider names.
    # Body field takes precedence over header.
    provider_name = request.provider or x_llm_provider
    llm_provider = None
    if provider_name:
        try:
            llm_provider = _resolve_provider(provider_name, x_llm_api_key, x_llm_model)
        except (ValueError, RuntimeError, ImportError, ProviderError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Sanitize input (warn-only — never blocks)
    sanitized_prompt, _sanitize_warnings = sanitize_text(request.prompt)

    start_time = time.time()
    optimization_id = str(uuid.uuid4())

    # Create the initial optimization record
    optimization = Optimization(
        id=optimization_id,
        raw_prompt=sanitized_prompt,
        status=OptimizationStatus.RUNNING,
        project=request.project,
        tags=json.dumps(request.tags) if request.tags else None,
        title=request.title,
        version=request.version,
        prompt_id=request.prompt_id,
    )
    db.add(optimization)

    # Validate prompt_id FK before committing (avoids cryptic IntegrityError)
    resolved_project_id: str | None = None
    if request.prompt_id:
        proj_repo = ProjectRepository(db)
        existing_prompt = await proj_repo.get_prompt_by_id(request.prompt_id)
        if not existing_prompt:
            raise HTTPException(status_code=400, detail="prompt_id does not reference a valid prompt")
        resolved_project_id = existing_prompt.project_id

    # Auto-create a Project record if a project name is provided
    if request.project:
        project_id_from_name = await ensure_project_by_name(db, request.project)
        if not resolved_project_id:
            resolved_project_id = project_id_from_name
        # Auto-create a Prompt record if no explicit prompt_id was provided
        # Skip linking to archived projects — user intended them to be frozen
        if not request.prompt_id and project_id_from_name:
            if not await _is_project_archived(db, project_id_from_name):
                auto_prompt_id = await ensure_prompt_in_project(
                    db, project_id_from_name, sanitized_prompt,
                )
                if auto_prompt_id:
                    optimization.prompt_id = auto_prompt_id

    await db.commit()

    metadata: dict[str, Any] = {
        "title": request.title or "",
        "project": request.project or "",
        "tags": request.tags or [],
        "version": request.version or "",
    }
    if resolved_project_id:
        metadata["project_id"] = resolved_project_id
    return _create_streaming_response(
        optimization_id, sanitized_prompt, start_time, metadata,
        llm_provider=llm_provider, strategy_override=request.strategy,
        secondary_frameworks_override=request.secondary_frameworks,
    )


@router.get("/api/optimize/check-duplicate")
async def check_duplicate_title(
    title: str,
    project: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Check if an optimization with the given title already exists in the project."""
    repo = OptimizationRepository(db)
    duplicate = await repo.title_exists(title, project)
    return {"duplicate": duplicate}


@router.get("/api/optimize/{optimization_id}", response_model=OptimizationResponse)
async def get_optimization(
    optimization_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single optimization by its ID."""
    repo = OptimizationRepository(db)
    optimization = await repo.get_by_id(optimization_id)

    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status == OptimizationStatus.COMPLETED:
        response.headers["Cache-Control"] = "max-age=3600, immutable"
    else:
        response.headers["Cache-Control"] = "no-cache"
    return optimization_to_response(optimization)


@router.post("/api/optimize/{optimization_id}/retry")
async def retry_optimization(
    optimization_id: str,
    db: AsyncSession = Depends(get_db),
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    """Re-run an existing optimization using the same raw prompt.

    Retrieves the original prompt and runs the pipeline again,
    returning a new SSE stream.

    Optional headers:
    - ``X-LLM-API-Key``: Runtime API key override (never logged)
    - ``X-LLM-Model``: Runtime model override
    - ``X-LLM-Provider``: Provider name for retry
    """
    repo = OptimizationRepository(db)
    original = await repo.get_by_id(optimization_id)

    if not original:
        raise HTTPException(status_code=404, detail="Optimization not found")

    # Resolve provider with optional runtime overrides
    llm_provider = None
    if x_llm_provider:
        try:
            llm_provider = _resolve_provider(x_llm_provider, x_llm_api_key, x_llm_model)
        except (ValueError, RuntimeError, ImportError, ProviderError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Create a new optimization record for the retry
    start_time = time.time()
    new_id = str(uuid.uuid4())
    raw_prompt = original.raw_prompt
    retry_title = f"Retry: {original.title}" if original.title else "Retry"
    retry_tags = deserialize_json_field(original.tags) or []
    new_optimization = Optimization(
        id=new_id,
        raw_prompt=raw_prompt,
        status=OptimizationStatus.RUNNING,
        project=original.project,
        tags=json.dumps(retry_tags) if retry_tags else None,
        title=retry_title,
        version=original.version,
        prompt_id=original.prompt_id,
    )
    db.add(new_optimization)

    resolved_project_id: str | None = None
    if original.project:
        project_id_from_name = await ensure_project_by_name(db, original.project)
        resolved_project_id = project_id_from_name
        # Auto-create prompt if original had no prompt_id
        # Skip linking to archived projects — user intended them to be frozen
        if not original.prompt_id and project_id_from_name:
            if not await _is_project_archived(db, project_id_from_name):
                auto_prompt_id = await ensure_prompt_in_project(
                    db, project_id_from_name, raw_prompt,
                )
                if auto_prompt_id:
                    new_optimization.prompt_id = auto_prompt_id

    await db.commit()

    metadata: dict[str, Any] = {
        "title": retry_title,
        "project": original.project or "",
        "tags": retry_tags,
        "version": original.version or "",
    }
    if resolved_project_id:
        metadata["project_id"] = resolved_project_id
    return _create_streaming_response(
        new_id, raw_prompt, start_time, metadata, llm_provider=llm_provider,
    )
