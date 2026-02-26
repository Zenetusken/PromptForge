"""Shared converters for transforming Optimization ORM objects."""

import json
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import OptimizationStatus
from app.database import async_session_factory
from app.models.optimization import Optimization
from app.schemas.optimization import HistorySummaryResponse, OptimizationResponse
from app.utils.scores import score_to_display

logger = logging.getLogger(__name__)


def deserialize_json_field(value: str | None) -> list[str] | None:
    """Deserialize a JSON string field to a list of strings, or return None.

    Returns None if the value is not valid JSON or not a list.
    Non-string items within the list are coerced to strings.
    """
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        logger.warning("deserialize_json_field: invalid JSON (%.80r)", value)
        return None
    if not isinstance(parsed, list):
        logger.warning(
            "deserialize_json_field: expected list, got %s", type(parsed).__name__
        )
        return None
    return [str(item) for item in parsed]


def _serialize_json_list(value: Any) -> str | None:
    """Serialize a list to a JSON string, or return None for None values.

    Prevents json.dumps(None) from storing the literal string "null" in the DB.
    """
    return json.dumps(value) if value is not None else None


def _extract_optimization_fields(opt: Optimization) -> dict[str, Any]:
    """Extract the common field set from an Optimization ORM object.

    Returns a dict with all shared fields (JSON list fields already deserialized).
    Used as the single source of truth for both optimization_to_response and
    optimization_to_dict.
    """
    return {
        "id": opt.id,
        "raw_prompt": opt.raw_prompt,
        "optimized_prompt": opt.optimized_prompt,
        "task_type": opt.task_type,
        "complexity": opt.complexity,
        "weaknesses": deserialize_json_field(opt.weaknesses),
        "strengths": deserialize_json_field(opt.strengths),
        "changes_made": deserialize_json_field(opt.changes_made),
        "framework_applied": opt.framework_applied,
        "optimization_notes": opt.optimization_notes,
        "strategy": opt.strategy,
        "strategy_reasoning": opt.strategy_reasoning,
        "strategy_confidence": opt.strategy_confidence,
        "secondary_frameworks": deserialize_json_field(opt.secondary_frameworks),
        "clarity_score": opt.clarity_score,
        "specificity_score": opt.specificity_score,
        "structure_score": opt.structure_score,
        "faithfulness_score": opt.faithfulness_score,
        "overall_score": opt.overall_score,
        "is_improvement": opt.is_improvement,
        "verdict": opt.verdict,
        "duration_ms": opt.duration_ms,
        "model_used": opt.model_used,
        "input_tokens": opt.input_tokens,
        "output_tokens": opt.output_tokens,
        "cache_creation_input_tokens": opt.cache_creation_input_tokens,
        "cache_read_input_tokens": opt.cache_read_input_tokens,
        "status": opt.status,
        "error_message": opt.error_message,
        "project": opt.project,
        "tags": deserialize_json_field(opt.tags),
        "title": opt.title,
        "version": opt.version,
        "prompt_id": opt.prompt_id,
        "project_id": getattr(opt, "_resolved_project_id", None),
        "project_status": getattr(opt, "_resolved_project_status", None),
        "codebase_context_snapshot": _deserialize_json_dict(
            getattr(opt, "codebase_context_snapshot", None)
        ),
    }


def _deserialize_json_dict(value: str | None) -> dict | None:
    """Deserialize a JSON string to a dict, or return None."""
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def optimization_to_response(opt: Optimization) -> OptimizationResponse:
    """Convert an Optimization ORM object to an OptimizationResponse schema."""
    fields = _extract_optimization_fields(opt)
    fields["created_at"] = opt.created_at
    return OptimizationResponse(**fields)


def optimization_to_dict(opt: Optimization) -> dict[str, Any]:
    """Convert an Optimization ORM object to a serializable dict."""
    fields = _extract_optimization_fields(opt)
    fields["created_at"] = opt.created_at.isoformat() if opt.created_at else None
    return fields


def _extract_summary_fields(opt: Optimization) -> dict[str, Any]:
    """Extract the lightweight summary field set directly from an Optimization ORM object.

    Only deserializes the 2 JSON fields needed for summaries (tags, secondary_frameworks),
    avoiding the 4 extra json.loads() calls that _extract_optimization_fields() would do.
    """
    return {
        "id": opt.id,
        "raw_prompt": opt.raw_prompt,
        "task_type": opt.task_type,
        "complexity": opt.complexity,
        "overall_score": opt.overall_score,
        "strategy": opt.strategy,
        "secondary_frameworks": deserialize_json_field(opt.secondary_frameworks),
        "framework_applied": opt.framework_applied,
        "model_used": opt.model_used,
        "status": opt.status,
        "error_message": opt.error_message,
        "project": opt.project,
        "tags": deserialize_json_field(opt.tags),
        "title": opt.title,
        "version": opt.version,
        "prompt_id": opt.prompt_id,
        "project_id": getattr(opt, "_resolved_project_id", None),
        "project_status": getattr(opt, "_resolved_project_status", None),
    }


def optimization_to_summary_response(opt: Optimization) -> HistorySummaryResponse:
    """Convert an Optimization ORM object to a lightweight HistorySummaryResponse."""
    fields = _extract_summary_fields(opt)
    fields["created_at"] = opt.created_at
    return HistorySummaryResponse(**fields)


def optimization_to_summary(opt: Optimization) -> dict[str, Any]:
    """Convert an Optimization ORM object to a summary dict (for MCP list views)."""
    fields = _extract_summary_fields(opt)
    fields["created_at"] = opt.created_at.isoformat() if opt.created_at else None
    fields["overall_score"] = score_to_display(fields.get("overall_score"))
    raw = opt.raw_prompt or ""
    fields["raw_prompt_preview"] = raw[:100] + ("..." if len(raw) > 100 else "")
    del fields["raw_prompt"]
    return fields


_SCORE_FIELDS = (
    "clarity_score", "specificity_score", "structure_score",
    "faithfulness_score", "overall_score",
)


def with_display_scores(fields: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *fields* with score values converted to 1-10 integers.

    Used by MCP-facing converters so all MCP tools return scores on the same
    display scale.
    """
    out = dict(fields)
    for key in _SCORE_FIELDS:
        if key in out:
            out[key] = score_to_display(out[key])
    return out


def apply_pipeline_result_to_orm(
    opt: Optimization, data: dict[str, Any], elapsed_ms: int
) -> None:
    """Apply pipeline result data to an ORM Optimization object.

    Handles both dict-based results (from streaming) and dataclass-based
    results (from synchronous pipeline).
    """
    opt.status = OptimizationStatus.COMPLETED
    opt.optimized_prompt = data.get("optimized_prompt")
    opt.task_type = data.get("task_type")
    opt.complexity = data.get("complexity")
    opt.weaknesses = _serialize_json_list(data.get("weaknesses"))
    opt.strengths = _serialize_json_list(data.get("strengths"))
    opt.changes_made = _serialize_json_list(data.get("changes_made"))
    opt.framework_applied = data.get("framework_applied")
    opt.optimization_notes = data.get("optimization_notes")
    opt.strategy = data.get("strategy")
    opt.strategy_reasoning = data.get("strategy_reasoning")
    opt.strategy_confidence = data.get("strategy_confidence")
    opt.secondary_frameworks = _serialize_json_list(data.get("secondary_frameworks"))
    opt.clarity_score = data.get("clarity_score")
    opt.specificity_score = data.get("specificity_score")
    opt.structure_score = data.get("structure_score")
    opt.faithfulness_score = data.get("faithfulness_score")
    opt.overall_score = data.get("overall_score")
    opt.is_improvement = data.get("is_improvement")
    opt.verdict = data.get("verdict")
    opt.duration_ms = elapsed_ms
    opt.model_used = data.get("model_used")
    opt.input_tokens = data.get("input_tokens")
    opt.output_tokens = data.get("output_tokens")
    opt.cache_creation_input_tokens = data.get("cache_creation_input_tokens")
    opt.cache_read_input_tokens = data.get("cache_read_input_tokens")


async def update_optimization_status(
    optimization_id: str,
    *,
    result_data: dict[str, Any] | None = None,
    start_time: float | None = None,
    error: str | None = None,
    model_fallback: str | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Update a DB optimization record after pipeline completes (success or error).

    Shared by the streaming router and the MCP server to avoid duplicating
    the fetch-record → apply-result → commit pattern.

    Args:
        optimization_id: The optimization UUID.
        result_data: Pipeline result dict (for success path).
        start_time: Pipeline start timestamp for elapsed_ms calculation.
        error: Error message string (for error path).
        model_fallback: Fallback model name if result doesn't include one.
        session: Optional existing session. If None, creates a new one.
    """
    async def _do_update(sess):
        stmt = select(Optimization).where(Optimization.id == optimization_id)
        result = await sess.execute(stmt)
        opt = result.scalar_one_or_none()
        if not opt:
            return
        if error is not None:
            opt.status = OptimizationStatus.ERROR
            opt.error_message = error
        elif result_data is not None:
            elapsed_ms = int((time.time() - start_time) * 1000) if start_time else 0
            apply_pipeline_result_to_orm(opt, result_data, elapsed_ms)
            if not opt.model_used and model_fallback:
                logger.info(
                    "optimization %s: pipeline did not set model_used; recording fallback %r",
                    optimization_id, model_fallback,
                )
                opt.model_used = model_fallback

    if session is not None:
        await _do_update(session)
        await session.commit()
    else:
        async with async_session_factory() as new_session:
            try:
                await _do_update(new_session)
                await new_session.commit()
            except SQLAlchemyError as e:
                await new_session.rollback()
                logger.error("Error updating optimization %s: %s", optimization_id, e)
