"""Optimization endpoints for running the prompt optimization pipeline."""

import dataclasses
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.database import get_db, get_db_readonly
from app.middleware.sanitize import sanitize_text
from app.providers import LLMProvider, get_provider
from app.providers.errors import ProviderError
from apps.promptforge.constants import OptimizationStatus
from apps.promptforge.converters import (
    compute_score_deltas,
    deserialize_json_field,
    extract_raw_scores,
    optimization_to_response,
    update_optimization_status,
)
from apps.promptforge.models.optimization import Optimization
from apps.promptforge.repositories.optimization import OptimizationRepository
from apps.promptforge.repositories.project import (
    ProjectRepository,
    ensure_project_by_name,
    ensure_prompt_in_project,
)
from apps.promptforge.repositories.workspace import WorkspaceRepository
from apps.promptforge.routers._audit import audit_log
from apps.promptforge.schemas.context import (
    CodebaseContext,
    codebase_context_from_dict,
    context_to_dict,
    merge_contexts,
)
from apps.promptforge.schemas.optimization import OptimizationResponse, OptimizeRequest
from apps.promptforge.services.pipeline import (
    PipelineComplete,
    run_pipeline,
    run_pipeline_streaming,
)
from apps.promptforge.services.stats_cache import invalidate_stats_cache
from kernel.bus.helpers import publish_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["optimize"])


def _resolve_provider(
    provider_name: str | None,
    api_key: str | None,
    model: str | None,
) -> LLMProvider | None:
    """Resolve an explicit provider selection, returning None for auto-detect."""
    if not provider_name:
        return None
    return get_provider(provider_name, api_key=api_key, model=model)


async def _resolve_context(
    db: AsyncSession,
    project_name: str | None,
    explicit_dict: dict[str, Any] | None = None,
) -> CodebaseContext | None:
    """Three-layer context resolution: workspace → manual profile → explicit request."""
    explicit = codebase_context_from_dict(explicit_dict)
    workspace = None
    manual = None
    if project_name:
        workspace = await WorkspaceRepository(db).get_workspace_context_by_project_name(
            project_name,
        )
        manual = await ProjectRepository(db).get_context_by_name(project_name)
    base = merge_contexts(workspace, manual)
    return merge_contexts(base, explicit)


async def _audit_log_optimization(opt_id: str, final_data: dict) -> None:
    """Log an optimization audit entry and publish bus event for live updates."""
    await audit_log(
        "optimize",
        "optimization",
        resource_id=opt_id,
        details={
            "strategy": final_data.get("strategy"),
            "score": final_data.get("overall_score"),
        },
    )


def _create_streaming_response(
    opt_id: str,
    raw_prompt: str,
    start_time: float,
    metadata: dict[str, Any] | None = None,
    llm_provider: LLMProvider | None = None,
    strategy_override: str | None = None,
    secondary_frameworks_override: list[str] | None = None,
    codebase_context: CodebaseContext | None = None,
    stages: list[str] | None = None,
    max_iterations: int | None = None,
    score_threshold: float | None = None,
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
                codebase_context=codebase_context,
                stages=stages,
                max_iterations=max_iterations,
                score_threshold=score_threshold,
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

        # Compute score deltas for retries (compare new scores against original)
        original_scores = (metadata or {}).pop("_original_scores", None)
        if original_scores and final_data:
            new_scores = {k: final_data.get(k) for k in original_scores}
            _deltas, deltas_raw = compute_score_deltas(new_scores, original_scores)
            if deltas_raw:
                final_data["score_deltas"] = deltas_raw
                # Re-render the complete SSE event with deltas included
                pending_complete_event = (
                    f"event: complete\ndata: {json.dumps(final_data)}\n\n"
                )

        # Persist to DB BEFORE sending the complete event to the client,
        # so immediate GET /optimize/{id} requests see the updated record.
        try:
            await update_optimization_status(
                opt_id,
                result_data=final_data,
                start_time=start_time,
                model_fallback=model_fallback,
            )
            invalidate_stats_cache()
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

        # Publish optimization.completed event
        publish_event("promptforge:optimization.completed", {
            "optimization_id": opt_id,
            "overall_score": final_data.get("overall_score"),
            "strategy": final_data.get("strategy"),
            "project": (metadata or {}).get("project"),
            "duration_ms": final_data.get("duration_ms"),
        }, "promptforge")

        # Audit log + bus event for live AuditLogWindow updates
        await _audit_log_optimization(opt_id, final_data)

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


@router.post("/optimize")
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

    # Quota enforcement — check before creating any DB record
    try:
        from kernel.repositories.audit import AuditRepository
        from kernel.security.access import check_quota
        from kernel.security.dependencies import get_app_context
        ctx = get_app_context("promptforge")
        audit_repo = AuditRepository(db)
        await check_quota(ctx, "api_calls", audit_repo)
    except HTTPException:
        raise  # Re-raise 429 quota exceeded
    except Exception:
        logger.debug("Quota check skipped (kernel not available)", exc_info=True)

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
            raise HTTPException(
                status_code=400,
                detail="prompt_id does not reference a valid prompt",
            )
        resolved_project_id = existing_prompt.project_id

    # Auto-create a Project record if a project name is provided
    if request.project:
        project_info = await ensure_project_by_name(db, request.project)
        if project_info and not resolved_project_id:
            resolved_project_id = project_info.id
        # Auto-create a Prompt record if no explicit prompt_id was provided
        # Skip linking to archived projects — user intended them to be frozen
        if not request.prompt_id and project_info:
            if project_info.status != "archived":
                auto_prompt_id = await ensure_prompt_in_project(
                    db, project_info.id, sanitized_prompt,
                )
                if auto_prompt_id:
                    optimization.prompt_id = auto_prompt_id

    resolved_context = await _resolve_context(db, request.project, request.codebase_context)

    # Snapshot on optimization record
    if resolved_context:
        ctx_dict = context_to_dict(resolved_context)
        if ctx_dict:
            optimization.codebase_context_snapshot = json.dumps(ctx_dict)

    await db.commit()

    # Publish optimization.started event
    publish_event("promptforge:optimization.started", {
        "optimization_id": optimization_id,
        "raw_prompt": sanitized_prompt[:200],
        "project": request.project,
        "strategy": request.strategy,
    }, "promptforge")

    metadata: dict[str, Any] = {
        "title": request.title or "",
        "project": request.project or "",
        "tags": request.tags or [],
        "version": request.version or "",
    }
    if resolved_project_id:
        metadata["project_id"] = resolved_project_id
    if resolved_context:
        ctx_dict = context_to_dict(resolved_context)
        if ctx_dict:
            metadata["codebase_context_snapshot"] = ctx_dict
    return _create_streaming_response(
        optimization_id, sanitized_prompt, start_time, metadata,
        llm_provider=llm_provider, strategy_override=request.strategy,
        secondary_frameworks_override=request.secondary_frameworks,
        codebase_context=resolved_context,
        stages=request.stages,
        max_iterations=request.max_iterations,
        score_threshold=request.score_threshold,
    )

# ---------------------------------------------------------------------------
# Modular Orchestration Endpoints
# ---------------------------------------------------------------------------

from pydantic import BaseModel  # noqa: E402


class AnalyzeRequest(BaseModel):
    prompt: str
    project: str | None = None
    codebase_context: dict[str, Any] | None = None

class StrategyRequest(BaseModel):
    prompt: str
    analysis: dict[str, Any]
    project: str | None = None
    codebase_context: dict[str, Any] | None = None

class OptimizeGenerateRequest(BaseModel):
    prompt: str
    analysis: dict[str, Any]
    strategy: str
    secondary_frameworks: list[str] | None = None
    project: str | None = None
    codebase_context: dict[str, Any] | None = None

class ValidateRequest(BaseModel):
    original_prompt: str
    optimized_prompt: str
    strategy: str | None = None
    project: str | None = None
    codebase_context: dict[str, Any] | None = None

def _timed_result(result: object, start: float) -> dict[str, Any]:
    """Convert a dataclass result to a dict with step_duration_ms timing."""
    d = dataclasses.asdict(result) if dataclasses.is_dataclass(result) else dict(result)  # type: ignore[arg-type]
    d["step_duration_ms"] = round((time.time() - start) * 1000)
    return d


def _resolve_orchestration_provider(
    x_llm_provider: str | None,
    x_llm_api_key: str | None,
    x_llm_model: str | None,
) -> LLMProvider:
    """Resolve provider for orchestration endpoints with proper error handling."""
    try:
        return _resolve_provider(x_llm_provider, x_llm_api_key, x_llm_model) or get_provider()
    except (ValueError, RuntimeError, ImportError, ProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _resolve_orchestration_context(
    project: str | None,
    explicit_dict: dict[str, Any] | None,
) -> CodebaseContext | None:
    """Three-layer resolution for orchestration endpoints.

    When ``project`` is provided, resolves workspace + manual profile layers
    before merging with the explicit dict. Falls back to explicit-only when
    no project is given (backward-compatible).
    """
    if not project:
        return codebase_context_from_dict(explicit_dict)
    from app.database import async_session_factory
    async with async_session_factory() as session:
        return await _resolve_context(session, project, explicit_dict)


@router.post("/orchestrate/analyze")
async def orchestrate_analyze(
    request: AnalyzeRequest,
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    from apps.promptforge.services.analyzer import PromptAnalyzer

    provider = _resolve_orchestration_provider(x_llm_provider, x_llm_api_key, x_llm_model)
    sanitized_prompt, _ = sanitize_text(request.prompt)
    context = await _resolve_orchestration_context(request.project, request.codebase_context)
    start = time.time()
    try:
        result = await PromptAnalyzer(provider).analyze(sanitized_prompt, codebase_context=context)
    except (ProviderError, Exception) as exc:
        logger.exception("Orchestrate analyze failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await audit_log("analyze", "pipeline_step")
    return _timed_result(result, start)


@router.post("/orchestrate/strategy")
async def orchestrate_strategy(
    request: StrategyRequest,
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    from apps.promptforge.services.analyzer import AnalysisResult
    from apps.promptforge.services.strategy_selector import StrategySelector

    provider = _resolve_orchestration_provider(x_llm_provider, x_llm_api_key, x_llm_model)
    sanitized_prompt, _ = sanitize_text(request.prompt)
    context = await _resolve_orchestration_context(request.project, request.codebase_context)
    try:
        analysis = AnalysisResult(**request.analysis)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid analysis data: {exc}") from exc
    start = time.time()
    try:
        result = await StrategySelector(provider).select(
            analysis,
            raw_prompt=sanitized_prompt,
            prompt_length=len(sanitized_prompt),
            codebase_context=context,
        )
    except (ProviderError, Exception) as exc:
        logger.exception("Orchestrate strategy failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await audit_log("strategy", "pipeline_step")
    return _timed_result(result, start)


@router.post("/orchestrate/optimize")
async def orchestrate_optimize(
    request: OptimizeGenerateRequest,
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    from apps.promptforge.services.analyzer import AnalysisResult
    from apps.promptforge.services.optimizer import PromptOptimizer

    provider = _resolve_orchestration_provider(x_llm_provider, x_llm_api_key, x_llm_model)
    sanitized_prompt, _ = sanitize_text(request.prompt)
    context = await _resolve_orchestration_context(request.project, request.codebase_context)
    try:
        analysis = AnalysisResult(**request.analysis)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid analysis data: {exc}") from exc
    start = time.time()
    try:
        result = await PromptOptimizer(provider).optimize(
            sanitized_prompt,
            analysis,
            request.strategy,
            secondary_frameworks=request.secondary_frameworks,
            codebase_context=context,
        )
    except (ProviderError, Exception) as exc:
        logger.exception("Orchestrate optimize failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await audit_log("optimize_step", "pipeline_step")
    return _timed_result(result, start)


@router.post("/orchestrate/validate")
async def orchestrate_validate(
    request: ValidateRequest,
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    from apps.promptforge.services.validator import PromptValidator

    provider = _resolve_orchestration_provider(x_llm_provider, x_llm_api_key, x_llm_model)
    sanitized_orig, _ = sanitize_text(request.original_prompt)
    sanitized_opt, _ = sanitize_text(request.optimized_prompt)
    context = await _resolve_orchestration_context(request.project, request.codebase_context)
    start = time.time()
    try:
        result = await PromptValidator(provider).validate(
            sanitized_orig, sanitized_opt,
            strategy=request.strategy, codebase_context=context,
        )
    except (ProviderError, Exception) as exc:
        logger.exception("Orchestrate validate failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await audit_log("validate", "pipeline_step")
    return _timed_result(result, start)


@router.post("/optimize/{optimization_id}/cancel")
async def cancel_optimization(
    optimization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running optimization.

    Sets optimization status to CANCELLED for bookkeeping. The client's
    AbortController already closes the SSE connection; this endpoint ensures
    cancelled forges don't remain as RUNNING forever.
    """
    repo = OptimizationRepository(db)
    optimization = await repo.get_by_id(optimization_id)

    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status != OptimizationStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel optimization in '{optimization.status}' status",
        )

    optimization.status = OptimizationStatus.CANCELLED
    await db.commit()
    invalidate_stats_cache()

    await audit_log("cancel", "optimization", resource_id=optimization_id)
    return {"id": optimization_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Batch Optimization
# ---------------------------------------------------------------------------

from pydantic import Field as PydanticField  # noqa: E402 — batch schemas below


class BatchOptimizeRequest(BaseModel):
    """Request for batch optimization of multiple prompts."""
    prompts: list[str] = PydanticField(
        ..., min_length=1, max_length=20,
        description="List of prompts to optimize (1-20)",
    )
    strategy: str | None = PydanticField(None, description="Strategy override for all prompts")
    project: str | None = PydanticField(None, description="Project to associate results with")
    tags: list[str] | None = PydanticField(None, description="Tags for all results")
    codebase_context: dict[str, Any] | None = PydanticField(
        None, description="Codebase context for all prompts in the batch",
    )

class BatchItemResult(BaseModel):
    """Result for a single item in a batch."""
    index: int
    optimization_id: str | None = None
    overall_score: float | None = None
    status: str = "pending"
    error: str | None = None

class BatchOptimizeResponse(BaseModel):
    """Response for batch optimization."""
    total: int
    completed: int
    failed: int
    results: list[BatchItemResult]


@router.post("/optimize/batch", response_model=BatchOptimizeResponse)
async def batch_optimize(
    request: BatchOptimizeRequest,
    db: AsyncSession = Depends(get_db),
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    """Run optimization pipeline on multiple prompts sequentially.

    Returns results for all prompts. Failed items don't stop the batch.
    """
    from dataclasses import asdict

    # Quota enforcement for batch — check once for the entire batch
    try:
        from kernel.repositories.audit import AuditRepository as _AR
        from kernel.security.access import check_quota as _check_quota
        from kernel.security.dependencies import get_app_context as _get_ctx
        _ctx = _get_ctx("promptforge")
        _audit = _AR(db)
        await _check_quota(_ctx, "api_calls", _audit)
    except HTTPException:
        raise
    except Exception:
        logger.debug("Batch quota check skipped", exc_info=True)

    llm_provider = _resolve_provider(x_llm_provider, x_llm_api_key, x_llm_model)

    # Pre-compute model fallback (same pattern as _create_streaming_response)
    if llm_provider:
        model_fallback = llm_provider.model_name
    else:
        try:
            model_fallback = get_provider().model_name
        except (RuntimeError, ImportError, ProviderError):
            model_fallback = config.CLAUDE_MODEL

    # Resolved once for the entire batch (all items share the same project context)
    resolved_context = await _resolve_context(db, request.project, request.codebase_context)

    results: list[BatchItemResult] = []
    completed = 0
    failed = 0

    for i, prompt_text in enumerate(request.prompts):
        sanitized, _ = sanitize_text(prompt_text)
        if not sanitized.strip():
            results.append(BatchItemResult(index=i, status="error", error="Empty prompt"))
            failed += 1
            continue

        optimization_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            optimization = Optimization(
                id=optimization_id,
                raw_prompt=sanitized,
                status=OptimizationStatus.RUNNING,
                project=request.project,
                tags=json.dumps(request.tags or ["batch"]),
                title=f"Batch #{i + 1}",
            )
            # Auto-create prompt record (same as single optimize)
            if request.project:
                project_info = await ensure_project_by_name(db, request.project)
                if project_info and project_info.status != "archived":
                    auto_prompt_id = await ensure_prompt_in_project(
                        db, project_info.id, sanitized,
                    )
                    if auto_prompt_id:
                        optimization.prompt_id = auto_prompt_id
            # Snapshot resolved context on the optimization record
            if resolved_context:
                ctx_dict = context_to_dict(resolved_context)
                if ctx_dict:
                    optimization.codebase_context_snapshot = json.dumps(ctx_dict)
            db.add(optimization)
            await db.commit()

            publish_event("promptforge:optimization.started", {
                "optimization_id": optimization_id,
                "raw_prompt": sanitized[:200],
                "project": request.project,
                "strategy": request.strategy,
            }, "promptforge")

            # Run pipeline (non-streaming — returns PipelineResult dataclass)
            pipeline_result = await run_pipeline(
                sanitized,
                llm_provider=llm_provider,
                strategy_override=request.strategy,
                codebase_context=resolved_context,
            )

            await update_optimization_status(
                optimization_id,
                result_data=asdict(pipeline_result),
                start_time=start_time,
                model_fallback=model_fallback,
                session=db,
            )
            publish_event("promptforge:optimization.completed", {
                "optimization_id": optimization_id,
                "overall_score": pipeline_result.overall_score,
                "strategy": pipeline_result.strategy,
                "project": request.project,
                "duration_ms": int((time.time() - start_time) * 1000),
            }, "promptforge")

            # Audit log for batch item
            await _audit_log_optimization(optimization_id, asdict(pipeline_result))

            results.append(BatchItemResult(
                index=i,
                optimization_id=optimization_id,
                overall_score=pipeline_result.overall_score,
                status="completed",
            ))
            completed += 1

        except Exception as exc:
            logger.exception("Batch item %d failed: %s", i, exc)
            try:
                await update_optimization_status(
                    optimization_id, error=str(exc)[:500], session=db,
                )
            except Exception:
                pass
            results.append(BatchItemResult(
                index=i,
                optimization_id=optimization_id,
                status="error",
                error=str(exc)[:200],
            ))
            failed += 1

    if completed > 0:
        invalidate_stats_cache()

    return BatchOptimizeResponse(
        total=len(request.prompts),
        completed=completed,
        failed=failed,
        results=results,
    )


@router.get("/optimize/check-duplicate")
async def check_duplicate_title(
    title: str,
    project: str | None = None,
    db: AsyncSession = Depends(get_db_readonly),
):
    """Check if an optimization with the given title already exists in the project."""
    repo = OptimizationRepository(db)
    duplicate = await repo.title_exists(title, project)
    return {"duplicate": duplicate}


@router.get("/optimize/{optimization_id}", response_model=OptimizationResponse)
async def get_optimization(
    optimization_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db_readonly),
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

    resp = optimization_to_response(optimization)

    # Compute score deltas for retries on-the-fly
    retry_of_id = getattr(optimization, "retry_of", None)
    if retry_of_id and optimization.status == OptimizationStatus.COMPLETED:
        original = await repo.get_by_id(retry_of_id)
        if original:
            _deltas, deltas_raw = compute_score_deltas(
                extract_raw_scores(optimization), extract_raw_scores(original),
            )
            if deltas_raw:
                resp.score_deltas = deltas_raw

    return resp


class RetryRequest(BaseModel):
    """Optional body for retry — allows overriding context on re-run."""
    strategy: str | None = None
    secondary_frameworks: list[str] | None = None
    codebase_context: dict[str, Any] | None = None


@router.post("/optimize/{optimization_id}/retry")
async def retry_optimization(
    optimization_id: str,
    request: RetryRequest | None = None,
    db: AsyncSession = Depends(get_db),
    x_llm_api_key: str | None = Header(None, alias="X-LLM-API-Key"),
    x_llm_model: str | None = Header(None, alias="X-LLM-Model"),
    x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
):
    """Re-run an existing optimization using the same raw prompt.

    Retrieves the original prompt and runs the pipeline again,
    returning a new SSE stream. Accepts an optional JSON body with
    ``strategy``, ``secondary_frameworks``, and ``codebase_context``
    overrides.

    Optional headers:
    - ``X-LLM-API-Key``: Runtime API key override (never logged)
    - ``X-LLM-Model``: Runtime model override
    - ``X-LLM-Provider``: Provider name for retry
    """
    request = request or RetryRequest()
    # Quota enforcement for retry
    try:
        from kernel.repositories.audit import AuditRepository as _AR
        from kernel.security.access import check_quota as _check_quota
        from kernel.security.dependencies import get_app_context as _get_ctx
        _ctx = _get_ctx("promptforge")
        _audit = _AR(db)
        await _check_quota(_ctx, "api_calls", _audit)
    except HTTPException:
        raise
    except Exception:
        logger.debug("Retry quota check skipped", exc_info=True)

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
        retry_of=optimization_id,
    )
    db.add(new_optimization)

    resolved_project_id: str | None = None
    if original.project:
        project_info = await ensure_project_by_name(db, original.project)
        if project_info:
            resolved_project_id = project_info.id
        # Auto-create prompt if original had no prompt_id
        # Skip linking to archived projects — user intended them to be frozen
        if not original.prompt_id and project_info:
            if project_info.status != "archived":
                auto_prompt_id = await ensure_prompt_in_project(
                    db, project_info.id, raw_prompt,
                )
                if auto_prompt_id:
                    new_optimization.prompt_id = auto_prompt_id

    # Re-resolve context from workspace + manual profile (picks up updates since original)
    # Layer 3: explicit codebase_context from retry request body overrides layers 1+2
    resolved_context = await _resolve_context(db, original.project, request.codebase_context)

    if resolved_context:
        ctx_dict = context_to_dict(resolved_context)
        if ctx_dict:
            new_optimization.codebase_context_snapshot = json.dumps(ctx_dict)

    await db.commit()

    metadata: dict[str, Any] = {
        "title": retry_title,
        "project": original.project or "",
        "tags": retry_tags,
        "version": original.version or "",
        "retry_of": optimization_id,
    }
    if resolved_project_id:
        metadata["project_id"] = resolved_project_id
    if resolved_context:
        ctx_dict = context_to_dict(resolved_context)
        if ctx_dict:
            metadata["codebase_context_snapshot"] = ctx_dict

    # Collect original scores for comparative delta computation in the SSE stream
    metadata["_original_scores"] = extract_raw_scores(original)
    return _create_streaming_response(
        new_id, raw_prompt, start_time, metadata, llm_provider=llm_provider,
        strategy_override=request.strategy,
        secondary_frameworks_override=request.secondary_frameworks,
        codebase_context=resolved_context,
    )
