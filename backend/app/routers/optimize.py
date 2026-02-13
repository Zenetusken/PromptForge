"""Optimization endpoints for running the prompt optimization pipeline."""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.constants import OptimizationStatus
from app.converters import apply_pipeline_result_to_orm, optimization_to_response
from app.database import async_session_factory, get_db
from app.models.optimization import Optimization
from app.schemas.optimization import OptimizationResponse, OptimizeRequest
from app.services.pipeline import run_pipeline_streaming

logger = logging.getLogger(__name__)

router = APIRouter(tags=["optimize"])


async def _update_db_after_stream(optimization_id: str, final_data: dict, start_time: float):
    """Update the database record with final pipeline results."""
    async with async_session_factory() as session:
        try:
            stmt = select(Optimization).where(Optimization.id == optimization_id)
            result = await session.execute(stmt)
            opt = result.scalar_one_or_none()
            if opt:
                elapsed_ms = int((time.time() - start_time) * 1000)
                apply_pipeline_result_to_orm(opt, final_data, elapsed_ms)
                if not opt.model_used:
                    opt.model_used = config.CLAUDE_MODEL
                await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Error updating optimization %s: %s", optimization_id, e)


def _create_streaming_response(
    opt_id: str, raw_prompt: str, start_time: float
) -> StreamingResponse:
    """Create a StreamingResponse wrapping the pipeline with DB persistence."""

    async def event_stream():
        final_data = {}
        try:
            async for event in run_pipeline_streaming(raw_prompt):
                if event.startswith("event: complete"):
                    lines = event.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith("data: "):
                            final_data = json.loads(line[6:])
                            # Inject ID into the SSE payload without mutating final_data
                            client_data = {**final_data, "id": opt_id}
                            lines[i] = "data: " + json.dumps(client_data)
                            break
                    event = "\n".join(lines)
                yield event
        except Exception as e:
            error_data = {"status": OptimizationStatus.ERROR, "error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            async with async_session_factory() as session:
                try:
                    stmt = select(Optimization).where(Optimization.id == opt_id)
                    result = await session.execute(stmt)
                    opt = result.scalar_one_or_none()
                    if opt:
                        opt.status = OptimizationStatus.ERROR
                        opt.error_message = str(e)
                        await session.commit()
                except Exception:
                    await session.rollback()
            return

        await _update_db_after_stream(opt_id, final_data, start_time)

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
):
    """Run the prompt optimization pipeline.

    Accepts a raw prompt and returns a Server-Sent Events stream with
    real-time updates as the pipeline progresses through analysis,
    optimization, and validation stages.
    """
    start_time = time.time()
    optimization_id = str(uuid.uuid4())

    # Create the initial optimization record
    optimization = Optimization(
        id=optimization_id,
        raw_prompt=request.prompt,
        status=OptimizationStatus.RUNNING,
        project=request.project,
        tags=json.dumps(request.tags) if request.tags else None,
        title=request.title,
    )
    db.add(optimization)
    await db.commit()

    return _create_streaming_response(optimization_id, request.prompt, start_time)


@router.get("/api/optimize/{optimization_id}", response_model=OptimizationResponse)
async def get_optimization(
    optimization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single optimization by its ID."""
    stmt = select(Optimization).where(Optimization.id == optimization_id)
    result = await db.execute(stmt)
    optimization = result.scalar_one_or_none()

    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    return optimization_to_response(optimization)


@router.post("/api/optimize/{optimization_id}/retry")
async def retry_optimization(
    optimization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-run an existing optimization using the same raw prompt.

    Retrieves the original prompt and runs the pipeline again,
    returning a new SSE stream.
    """
    stmt = select(Optimization).where(Optimization.id == optimization_id)
    result = await db.execute(stmt)
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(status_code=404, detail="Optimization not found")

    # Create a new optimization record for the retry
    start_time = time.time()
    new_id = str(uuid.uuid4())
    raw_prompt = original.raw_prompt
    new_optimization = Optimization(
        id=new_id,
        raw_prompt=raw_prompt,
        status=OptimizationStatus.RUNNING,
        project=original.project,
        tags=original.tags,
        title=f"Retry: {original.title}" if original.title else "Retry",
    )
    db.add(new_optimization)
    await db.commit()

    return _create_streaming_response(new_id, raw_prompt, start_time)
