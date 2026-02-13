"""Optimization endpoints for running the prompt optimization pipeline."""

import asyncio
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.optimization import Optimization
from app.schemas.optimization import OptimizationResponse, OptimizeRequest

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


async def _generate_mock_sse_events(optimization_id: str, raw_prompt: str):
    """Generate mock SSE events simulating the optimization pipeline.

    In production, this would call the actual pipeline stages.
    Each event is a Server-Sent Event with a JSON data payload.
    """
    # Stage 1: Analyzing
    yield f"event: stage\ndata: {json.dumps({'stage': 'analyzing', 'message': 'Analyzing prompt structure and intent...'})}\n\n"
    await asyncio.sleep(0.5)

    analysis = {
        "task_type": "general",
        "complexity": "medium",
        "weaknesses": ["Lacks specificity", "No output format specified"],
        "strengths": ["Clear intent", "Good context"],
    }
    yield f"event: analysis\ndata: {json.dumps(analysis)}\n\n"
    await asyncio.sleep(0.3)

    # Stage 2: Optimizing
    yield f"event: stage\ndata: {json.dumps({'stage': 'optimizing', 'message': 'Applying optimization strategies...'})}\n\n"
    await asyncio.sleep(0.5)

    optimized_prompt = (
        f"You are an expert assistant. Your task is as follows:\n\n"
        f"{raw_prompt}\n\n"
        f"Please provide a detailed, well-structured response. "
        f"Include specific examples where relevant. "
        f"Format your output using clear headings and bullet points."
    )

    optimization = {
        "optimized_prompt": optimized_prompt,
        "framework_applied": "structured-enhancement",
        "changes_made": [
            "Added role definition",
            "Specified output format",
            "Added structure requirements",
            "Enhanced specificity",
        ],
        "optimization_notes": "Applied structured enhancement framework to improve clarity and specificity.",
    }
    yield f"event: optimization\ndata: {json.dumps(optimization)}\n\n"
    await asyncio.sleep(0.3)

    # Stage 3: Validating
    yield f"event: stage\ndata: {json.dumps({'stage': 'validating', 'message': 'Validating optimization quality...'})}\n\n"
    await asyncio.sleep(0.5)

    validation = {
        "clarity_score": 0.85,
        "specificity_score": 0.78,
        "structure_score": 0.90,
        "faithfulness_score": 0.95,
        "overall_score": 0.87,
        "is_improvement": True,
        "verdict": "The optimized prompt significantly improves structure and clarity while maintaining the original intent.",
    }
    yield f"event: validation\ndata: {json.dumps(validation)}\n\n"
    await asyncio.sleep(0.2)

    # Final: Complete
    complete_data = {
        "id": optimization_id,
        "status": "completed",
        **analysis,
        **optimization,
        **validation,
        "duration_ms": 1800,
        "model_used": "mock",
    }
    yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"


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
        """Wrap the SSE generator and update the DB record on completion."""
        final_data = {}
        async for event in _generate_mock_sse_events(optimization_id, request.prompt):
            # Capture complete event data for DB update
            if event.startswith("event: complete"):
                data_line = event.split("data: ", 1)[1].strip()
                final_data = json.loads(data_line)
            yield event

        # Update the database record with final results
        async with get_db_session() as session:
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
                opt.model_used = final_data.get("model_used", "mock")
                await session.commit()

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
    new_id = str(uuid.uuid4())
    new_optimization = Optimization(
        id=new_id,
        raw_prompt=original.raw_prompt,
        status="running",
        project=original.project,
        tags=original.tags,
        title=f"Retry: {original.title}" if original.title else "Retry",
    )
    db.add(new_optimization)
    await db.commit()

    return StreamingResponse(
        _generate_mock_sse_events(new_id, original.raw_prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def get_db_session():
    """Create a standalone async session context manager for use outside of request scope."""
    from app.database import async_session_factory

    class _SessionCtx:
        async def __aenter__(self):
            self.session = async_session_factory()
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
            await self.session.close()

    return _SessionCtx()
