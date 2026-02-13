"""Shared converters for transforming Optimization ORM objects."""

import json

from app.constants import OptimizationStatus
from app.models.optimization import Optimization
from app.schemas.optimization import OptimizationResponse


def serialize_json_field(value: str | None) -> list[str] | None:
    """Deserialize a JSON string field to a list, or return None."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def optimization_to_response(opt: Optimization) -> OptimizationResponse:
    """Convert an Optimization ORM object to an OptimizationResponse schema."""
    return OptimizationResponse(
        id=opt.id,
        created_at=opt.created_at,
        raw_prompt=opt.raw_prompt,
        optimized_prompt=opt.optimized_prompt,
        task_type=opt.task_type,
        complexity=opt.complexity,
        weaknesses=serialize_json_field(opt.weaknesses),
        strengths=serialize_json_field(opt.strengths),
        changes_made=serialize_json_field(opt.changes_made),
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
        tags=serialize_json_field(opt.tags),
        title=opt.title,
    )


def optimization_to_dict(opt: Optimization) -> dict:
    """Convert an Optimization ORM object to a serializable dict."""
    return {
        "id": opt.id,
        "created_at": opt.created_at.isoformat() if opt.created_at else None,
        "raw_prompt": opt.raw_prompt,
        "optimized_prompt": opt.optimized_prompt,
        "task_type": opt.task_type,
        "complexity": opt.complexity,
        "weaknesses": serialize_json_field(opt.weaknesses),
        "strengths": serialize_json_field(opt.strengths),
        "changes_made": serialize_json_field(opt.changes_made),
        "framework_applied": opt.framework_applied,
        "optimization_notes": opt.optimization_notes,
        "clarity_score": opt.clarity_score,
        "specificity_score": opt.specificity_score,
        "structure_score": opt.structure_score,
        "faithfulness_score": opt.faithfulness_score,
        "overall_score": opt.overall_score,
        "is_improvement": opt.is_improvement,
        "verdict": opt.verdict,
        "duration_ms": opt.duration_ms,
        "model_used": opt.model_used,
        "status": opt.status,
        "error_message": opt.error_message,
        "project": opt.project,
        "tags": serialize_json_field(opt.tags),
        "title": opt.title,
    }


def optimization_to_summary(opt: Optimization) -> dict:
    """Convert an Optimization ORM object to a summary dict (for list views)."""
    raw = opt.raw_prompt or ""
    return {
        "id": opt.id,
        "created_at": opt.created_at.isoformat() if opt.created_at else None,
        "raw_prompt_preview": raw[:100] + ("..." if len(raw) > 100 else ""),
        "task_type": opt.task_type,
        "complexity": opt.complexity,
        "overall_score": score_to_int(opt.overall_score),
        "status": opt.status,
        "project": opt.project,
        "tags": serialize_json_field(opt.tags),
        "title": opt.title,
    }


def score_to_int(score: float | None) -> int | None:
    """Convert a 0.0-1.0 float score to a 1-10 integer scale."""
    if score is None:
        return None
    # Scores may already be on 1-10 scale or 0-1 scale
    if score <= 1.0:
        return max(1, min(10, round(score * 10)))
    return max(1, min(10, round(score)))


def apply_pipeline_result_to_orm(
    opt: Optimization, data: dict, elapsed_ms: int
) -> None:
    """Apply pipeline result data to an ORM Optimization object.

    Handles both dict-based results (from streaming) and dataclass-based
    results (from synchronous pipeline).
    """
    opt.status = OptimizationStatus.COMPLETED
    opt.optimized_prompt = data.get("optimized_prompt")
    opt.task_type = data.get("task_type")
    opt.complexity = data.get("complexity")
    opt.weaknesses = json.dumps(data.get("weaknesses"))
    opt.strengths = json.dumps(data.get("strengths"))
    opt.changes_made = json.dumps(data.get("changes_made"))
    opt.framework_applied = data.get("framework_applied")
    opt.optimization_notes = data.get("optimization_notes")
    opt.clarity_score = data.get("clarity_score")
    opt.specificity_score = data.get("specificity_score")
    opt.structure_score = data.get("structure_score")
    opt.faithfulness_score = data.get("faithfulness_score")
    opt.overall_score = data.get("overall_score")
    opt.is_improvement = data.get("is_improvement")
    opt.verdict = data.get("verdict")
    opt.duration_ms = elapsed_ms
    opt.model_used = data.get("model_used")
