import asyncio
import datetime as dt
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session, get_session
from app.dependencies.auth import get_current_user
from app.errors import conflict, not_found, service_unavailable
from app.models.optimization import Optimization
from app.schemas.auth import AuthenticatedUser
from app.schemas.optimization import OptimizeRequest, PatchOptimizationRequest, RetryRequest
from app.services.optimization_service import PipelineAccumulator
from app.services.settings_service import load_settings
from app.services.url_fetcher import fetch_url_contexts

logger = logging.getLogger(__name__)
router = APIRouter(tags=["optimize"])


def _default_serializer(obj: object) -> str:
    """JSON fallback serializer for types not handled by default."""
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    if isinstance(obj, Exception):
        return str(obj)
    return repr(obj)  # Last resort — never silently drop data


def _sse_event(event_type: str, data: dict) -> str:
    """Format an SSE event with safe JSON serialization.

    Uses a fallback serializer so that non-serializable values (datetimes,
    exceptions, etc.) never crash the stream silently.
    """
    try:
        payload = json.dumps(data, default=_default_serializer)
    except Exception as e:
        logger.error("SSE serialization failed for event %s: %s", event_type, e)
        payload = json.dumps({"error": f"Serialization error: {e}"})
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/api/optimize")
async def optimize_prompt(
    request: OptimizeRequest,
    req: Request,
    retry_of: str | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Run the optimization pipeline with SSE streaming."""
    if not req.app.state.provider:
        raise service_unavailable("LLM provider not initialized")

    opt_id = str(uuid.uuid4())
    start_time = time.time()

    async def event_stream():
        # Session 1: create the record in pending state
        async with async_session() as s:
            s.add(Optimization(
                id=opt_id,
                raw_prompt=request.prompt,
                status="running",
                project=request.project,
                tags=json.dumps(request.tags or []),
                title=request.title,
                linked_repo_full_name=request.repo_full_name,
                linked_repo_branch=request.repo_branch,
                retry_of=retry_of,
                user_id=current_user.id,
            ))
            await s.commit()

        acc = PipelineAccumulator()

        try:
            from app.services.pipeline import run_pipeline

            url_fetched = await fetch_url_contexts(request.url_contexts)
            user_settings = load_settings()
            effective_timeout = min(
                user_settings.get("pipeline_timeout", settings.PIPELINE_TIMEOUT_SECONDS),
                settings.PIPELINE_TIMEOUT_SECONDS,
            )

            async with asyncio.timeout(effective_timeout):
                async for event_type, event_data in run_pipeline(
                    provider=req.app.state.provider,
                    raw_prompt=request.prompt,
                    optimization_id=opt_id,
                    strategy_override=request.strategy,
                    repo_full_name=request.repo_full_name,
                    repo_branch=request.repo_branch,
                    session_id=req.session.get("session_id"),
                    github_token=request.github_token,
                    file_contexts=request.file_contexts,
                    instructions=request.instructions,
                    url_fetched_contexts=url_fetched,
                ):
                    yield _sse_event(event_type, event_data)

                    if event_type == "validation" and "scores" not in event_data:
                        logger.error(
                            "Validation event missing 'scores' sub-dict for opt %s; keys: %s",
                            opt_id, list(event_data.keys())
                        )
                    acc.process_event(event_type, event_data)

                updates = acc.finalize(req.app.state.provider.name, start_time)

                async with async_session() as s:
                    await s.execute(
                        update(Optimization)
                        .where(Optimization.id == opt_id)
                        .values(**updates)
                    )
                    await s.commit()

                if not acc.pipeline_failed:
                    yield _sse_event("complete", {
                        "optimization_id": opt_id,
                        "total_duration_ms": updates["duration_ms"],
                        "total_tokens": acc.total_tokens,
                    })

        except asyncio.TimeoutError:
            logger.error("Pipeline timeout (%ds) for opt %s", effective_timeout, opt_id)
            updates = acc.finalize(req.app.state.provider.name, start_time,
                                   error=TimeoutError(f"Pipeline timed out after {effective_timeout}s"))
            async with async_session() as s:
                await s.execute(
                    update(Optimization)
                    .where(Optimization.id == opt_id)
                    .values(**updates)
                )
                await s.commit()
            yield _sse_event("error", {
                "stage": "pipeline",
                "error": f"Pipeline timed out after {effective_timeout}s",
                "recoverable": False,
            })
            return

        except Exception as e:
            logger.exception(f"Pipeline error for {opt_id}: {e}")
            updates = acc.finalize(req.app.state.provider.name, start_time, error=e)
            try:
                async with async_session() as s:
                    await s.execute(
                        update(Optimization)
                        .where(Optimization.id == opt_id)
                        .values(**updates)
                    )
                    await s.commit()
            except Exception:
                logger.exception("Failed to save error state")
            yield _sse_event("error", {
                "stage": "pipeline",
                "error": str(e),
                "recoverable": False,
            })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/optimize/{optimization_id}")
async def get_optimization(
    optimization_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get a single optimization by ID."""
    result = await session.execute(
        select(Optimization).where(
            Optimization.id == optimization_id,
            Optimization.deleted_at.is_(None),
            Optimization.user_id == current_user.id,
        )
    )
    optimization = result.scalar_one_or_none()
    if not optimization:
        raise not_found("Optimization not found")
    return optimization.to_dict()


@router.patch("/api/optimize/{optimization_id}")
async def patch_optimization(
    optimization_id: str,
    patch: PatchOptimizationRequest,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Update metadata on an optimization."""
    result = await session.execute(
        select(Optimization).where(
            Optimization.id == optimization_id,
            Optimization.deleted_at.is_(None),
            Optimization.user_id == current_user.id,
        )
    )
    optimization = result.scalar_one_or_none()
    if not optimization:
        raise not_found("Optimization not found")

    if patch.expected_version is not None and optimization.row_version != patch.expected_version:
        raise conflict(
            "Record was modified by another request. Refetch and retry.",
            code="VERSION_CONFLICT",
            current_version=optimization.row_version,
        )

    if patch.title is not None:
        optimization.title = patch.title  # type: ignore[assignment]
    if patch.tags is not None:
        optimization.tags = json.dumps(patch.tags)  # type: ignore[assignment]
    if patch.version is not None:
        optimization.version = patch.version  # type: ignore[assignment]
    if patch.project is not None:
        optimization.project = patch.project  # type: ignore[assignment]

    optimization.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    optimization.row_version += 1
    await session.commit()
    return optimization.to_dict()


@router.post("/api/optimize/{optimization_id}/retry")
async def retry_optimization(
    optimization_id: str,
    body: RetryRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retry an optimization with optional strategy override."""
    result = await session.execute(
        select(Optimization).where(
            Optimization.id == optimization_id,
            Optimization.deleted_at.is_(None),
            Optimization.user_id == current_user.id,
        )
    )
    original = result.scalar_one_or_none()
    if not original:
        raise not_found("Optimization not found")

    # Create a new optimize request based on the original
    retry_request = OptimizeRequest(
        prompt=str(original.raw_prompt),
        project=str(original.project) if original.project else None,
        tags=json.loads(str(original.tags)) if original.tags else None,
        title=str(original.title) if original.title else None,
        strategy=body.strategy,
        repo_full_name=str(original.linked_repo_full_name) if original.linked_repo_full_name else None,
        repo_branch=str(original.linked_repo_branch) if original.linked_repo_branch else None,
        file_contexts=body.file_contexts,    # N32
        instructions=body.instructions,      # N32
        url_contexts=body.url_contexts,      # N32
        github_token=body.github_token,      # N40: re-run Explore on retry
    )

    # Reuse the optimize endpoint logic, linking retry to original.
    # current_user must be passed explicitly — FastAPI won't inject it for inner calls.
    return await optimize_prompt(
        retry_request, req,
        retry_of=optimization_id,
        current_user=current_user,
    )
