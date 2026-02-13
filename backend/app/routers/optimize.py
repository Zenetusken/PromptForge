"""Optimization endpoints for running the prompt optimization pipeline."""

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.optimization import Optimization
from app.schemas.optimization import OptimizationResponse, OptimizeRequest
from app.services.pipeline import run_pipeline_streaming

router = APIRouter(tags=["optimize"])


def _serialize_json_field(value: str | None) -> list[str] | None:
    """Deserialize a JSON string field to a list, or return None."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _optimization_to_response(opt: Optimization) -> OptimizationResponse:
    """Convert an Optimization ORM object to an OptimizationResponse schema."""
    return OptimizationResponse(
        id=opt.id,
        created_at=opt.created_at,
        raw_prompt=opt.raw_prompt,
        optimized_prompt=opt.optimized_prompt,
        task_type=opt.task_type,
        complexity=opt.complexity,
        weaknesses=_serialize_json_field(opt.weaknesses),
        strengths=_serialize_json_field(opt.strengths),
        changes_made=_serialize_json_field(opt.changes_made),
        framework_applied=opt.framework_applied,
        optimization_notes=opt.optimization_notes,
        clarity_score=opt.clarity_score,
        specificity_score=opt.specificity_score,
        structure_score=opt.structure_score,
        faithfulness_score=opt.faithfulness_score,
        overall_score=opt.overall_score,
        is_improvement=opt.is_improvement,
        verdict=opt.verdict,
        duration_ms=opt.duration_ms,
        model_used=opt.model_used,
        status=opt.status,
        error_message=opt.error_message,
        project=opt.project,
        tags=_serialize_json_field(opt.tags),
        title=opt.title,
    )


async def _update_db_after_stream(optimization_id: str, final_data: dict, start_time: float):
    """Update the database record with final pipeline results."""
    async with async_session_factory() as session:
        try:
            stmt = select(Optimization).where(Optimization.id == optimization_id)
            result = await session.execute(stmt)
            opt = result.scalar_one_or_none()
            if opt:
                elapsed_ms = int((time.time() - start_time) * 1000)
                opt.status = "completed"
                opt.optimized_prompt = final_data.get("optimized_prompt")
                opt.task_type = final_data.get("task_type")
                opt.complexity = final_data.get("complexity")
                opt.weaknesses = json.dumps(final_data.get("weaknesses"))
                opt.strengths = json.dumps(final_data.get("strengths"))
                opt.changes_made = json.dumps(final_data.get("changes_made"))
                opt.framework_applied = final_data.get("framework_applied")
                opt.optimization_notes = final_data.get("optimization_notes")
                opt.clarity_score = final_data.get("clarity_score")
                opt.specificity_score = final_data.get("specificity_score")
                opt.structure_score = final_data.get("structure_score")
                opt.faithfulness_score = final_data.get("faithfulness_score")
                opt.overall_score = final_data.get("overall_score")
                opt.is_improvement = final_data.get("is_improvement")
                opt.verdict = final_data.get("verdict")
                opt.duration_ms = elapsed_ms
                opt.model_used = final_data.get("model_used", "claude-code-sdk")
                await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Error updating optimization {optimization_id}: {e}")


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
        status="running",
        project=request.project,
        tags=json.dumps(request.tags) if request.tags else None,
        title=request.title,
    )
    db.add(optimization)
    await db.commit()

    async def event_stream():
        """Wrap the real pipeline SSE generator and update the DB on completion."""
        final_data = {}
        try:
            async for event in run_pipeline_streaming(request.prompt):
                # Capture complete event data for DB update
                if event.startswith("event: complete"):
                    data_line = event.split("data: ", 1)[1].strip()
                    final_data = json.loads(data_line)
                yield event
        except Exception as e:
            # Emit an error event if the pipeline fails
            error_data = {"status": "error", "error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            # Update the DB record with error status
            async with async_session_factory() as session:
                try:
                    stmt = select(Optimization).where(Optimization.id == optimization_id)
                    result = await session.execute(stmt)
                    opt = result.scalar_one_or_none()
                    if opt:
                        opt.status = "error"
                        opt.error_message = str(e)
                        await session.commit()
                except Exception:
                    await session.rollback()
            return

        # Update the database record with final results
        await _update_db_after_stream(optimization_id, final_data, start_time)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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

    return _optimization_to_response(optimization)


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
        status="running",
        project=original.project,
        tags=original.tags,
        title=f"Retry: {original.title}" if original.title else "Retry",
    )
    db.add(new_optimization)
    await db.commit()

    async def event_stream():
        """Wrap the real pipeline SSE generator and update the DB on completion."""
        final_data = {}
        try:
            async for event in run_pipeline_streaming(raw_prompt):
                if event.startswith("event: complete"):
                    data_line = event.split("data: ", 1)[1].strip()
                    final_data = json.loads(data_line)
                yield event
        except Exception as e:
            error_data = {"status": "error", "error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            async with async_session_factory() as session:
                try:
                    stmt = select(Optimization).where(Optimization.id == new_id)
                    result = await session.execute(stmt)
                    opt = result.scalar_one_or_none()
                    if opt:
                        opt.status = "error"
                        opt.error_message = str(e)
                        await session.commit()
                except Exception:
                    await session.rollback()
            return

        # Update the database record with final results
        await _update_db_after_stream(new_id, final_data, start_time)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
