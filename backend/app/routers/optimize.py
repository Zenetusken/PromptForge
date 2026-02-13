"""Optimization endpoints for running the prompt optimization pipeline."""

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.constants import OptimizationStatus
from app.converters import optimization_to_response, update_optimization_status
from app.database import get_db
from app.models.optimization import Optimization
from app.repositories.optimization import OptimizationRepository
from app.schemas.optimization import OptimizationResponse, OptimizeRequest
from app.services.pipeline import run_pipeline_streaming

router = APIRouter(tags=["optimize"])


def _create_streaming_response(
    opt_id: str,
    raw_prompt: str,
    start_time: float,
    metadata: dict | None = None,
) -> StreamingResponse:
    """Create a StreamingResponse wrapping the pipeline with DB persistence."""

    # Build complete_metadata with id so the pipeline injects it directly
    complete_metadata: dict = {"id": opt_id}
    if metadata:
        complete_metadata.update(metadata)

    async def event_stream():
        final_data = {}
        try:
            async for event in run_pipeline_streaming(raw_prompt, complete_metadata=complete_metadata):
                # Capture complete event data for DB persistence
                if event.startswith("event: complete"):
                    lines = event.split("\n")
                    for line in lines:
                        if line.startswith("data: "):
                            final_data = json.loads(line[6:])
                            break
                yield event
        except Exception as e:
            error_data = {"status": OptimizationStatus.ERROR, "error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            await update_optimization_status(opt_id, error=str(e))
            return

        await update_optimization_status(
            opt_id,
            result_data=final_data,
            start_time=start_time,
            model_fallback=config.CLAUDE_MODEL,
        )

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

    metadata = {
        "title": request.title or "",
        "project": request.project or "",
        "tags": request.tags or [],
    }
    return _create_streaming_response(optimization_id, request.prompt, start_time, metadata)


@router.get("/api/optimize/{optimization_id}", response_model=OptimizationResponse)
async def get_optimization(
    optimization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single optimization by its ID."""
    repo = OptimizationRepository(db)
    optimization = await repo.get_by_id(optimization_id)

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
    repo = OptimizationRepository(db)
    original = await repo.get_by_id(optimization_id)

    if not original:
        raise HTTPException(status_code=404, detail="Optimization not found")

    # Create a new optimization record for the retry
    start_time = time.time()
    new_id = str(uuid.uuid4())
    raw_prompt = original.raw_prompt
    retry_title = f"Retry: {original.title}" if original.title else "Retry"
    retry_tags = json.loads(original.tags) if original.tags else []
    new_optimization = Optimization(
        id=new_id,
        raw_prompt=raw_prompt,
        status=OptimizationStatus.RUNNING,
        project=original.project,
        tags=original.tags,
        title=retry_title,
    )
    db.add(new_optimization)
    await db.commit()

    metadata = {
        "title": retry_title,
        "project": original.project or "",
        "tags": retry_tags,
    }
    return _create_streaming_response(new_id, raw_prompt, start_time, metadata)
