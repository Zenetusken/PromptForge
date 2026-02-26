"""Tests for the converters module — JSON field (de)serialization, display score
conversion, ORM pipeline result application, response/summary conversion,
and update_optimization_status."""

import json
import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.constants import OptimizationStatus
from app.converters import (
    _SCORE_FIELDS,
    _serialize_json_list,
    apply_pipeline_result_to_orm,
    deserialize_json_field,
    optimization_to_response,
    optimization_to_summary,
    update_optimization_status,
    with_display_scores,
)
from app.models.optimization import Optimization

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_optimization(**overrides) -> Optimization:
    """Create an Optimization ORM object without a DB session."""
    defaults = {
        "id": "test-id-001",
        "raw_prompt": "test raw prompt",
        "optimized_prompt": "test optimized",
        "task_type": "coding",
        "complexity": "medium",
        "weaknesses": json.dumps(["vague"]),
        "strengths": json.dumps(["clear"]),
        "changes_made": json.dumps(["added role"]),
        "framework_applied": "persona-assignment",
        "optimization_notes": "Some notes",
        "strategy_reasoning": "Selected role-based for coding",
        "strategy_confidence": 0.85,
        "clarity_score": 0.9,
        "specificity_score": 0.8,
        "structure_score": 0.7,
        "faithfulness_score": 0.85,
        "overall_score": 0.82,
        "is_improvement": True,
        "verdict": "Good improvement",
        "duration_ms": 1500,
        "model_used": "test-model",
        "input_tokens": 100,
        "output_tokens": 50,
        "status": OptimizationStatus.COMPLETED,
        "error_message": None,
        "project": "test-project",
        "tags": json.dumps(["tag1", "tag2"]),
        "title": "Test Title",
        "created_at": datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Optimization(**defaults)


# ---------------------------------------------------------------------------
# TestDeserializeJsonField
# ---------------------------------------------------------------------------

class TestDeserializeJsonField:
    def test_none_returns_none(self):
        assert deserialize_json_field(None) is None

    def test_valid_list(self):
        assert deserialize_json_field('["a", "b"]') == ["a", "b"]

    def test_invalid_json_returns_none(self):
        assert deserialize_json_field("not json") is None

    def test_non_list_json_returns_none(self):
        assert deserialize_json_field('{"key": "value"}') is None

    def test_number_json_returns_none(self):
        assert deserialize_json_field("42") is None

    def test_non_string_items_coerced(self):
        assert deserialize_json_field("[1, 2, 3]") == ["1", "2", "3"]

    def test_empty_list(self):
        assert deserialize_json_field("[]") == []

    def test_nested_items_coerced_to_strings(self):
        result = deserialize_json_field('[{"key": "val"}, [1, 2]]')
        assert len(result) == 2
        # Nested structures are stringified
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)


# ---------------------------------------------------------------------------
# TestSerializeJsonList
# ---------------------------------------------------------------------------

class TestSerializeJsonList:
    def test_none_returns_none(self):
        assert _serialize_json_list(None) is None

    def test_list_returns_json_string(self):
        result = _serialize_json_list(["a", "b"])
        assert json.loads(result) == ["a", "b"]

    def test_empty_list_returns_brackets(self):
        assert _serialize_json_list([]) == "[]"


# ---------------------------------------------------------------------------
# TestWithDisplayScores
# ---------------------------------------------------------------------------

class TestWithDisplayScores:
    def test_scores_converted_to_1_10(self):
        fields = {"clarity_score": 0.85, "specificity_score": 0.5}
        result = with_display_scores(fields)
        assert result["clarity_score"] == 8  # round(8.5) = 8 (banker's)
        assert result["specificity_score"] == 5

    def test_none_stays_none(self):
        fields = {"clarity_score": None}
        result = with_display_scores(fields)
        assert result["clarity_score"] is None

    def test_non_score_fields_unchanged(self):
        fields = {"task_type": "coding", "clarity_score": 0.9}
        result = with_display_scores(fields)
        assert result["task_type"] == "coding"

    def test_all_five_score_fields_converted(self):
        fields = {
            "clarity_score": 0.1,
            "specificity_score": 0.3,
            "structure_score": 0.5,
            "faithfulness_score": 0.7,
            "overall_score": 0.9,
        }
        result = with_display_scores(fields)
        for key in _SCORE_FIELDS:
            assert isinstance(result[key], int)

    def test_returns_new_dict_no_mutation(self):
        fields = {"clarity_score": 0.5}
        result = with_display_scores(fields)
        assert result is not fields
        assert fields["clarity_score"] == 0.5  # original unchanged

    def test_missing_score_fields_ignored(self):
        fields = {"task_type": "coding"}
        result = with_display_scores(fields)
        assert "clarity_score" not in result


# ---------------------------------------------------------------------------
# TestApplyPipelineResultToOrm
# ---------------------------------------------------------------------------

class TestApplyPipelineResultToOrm:
    def test_all_fields_applied(self):
        opt = _make_optimization(status=OptimizationStatus.PENDING)
        data = {
            "optimized_prompt": "new prompt",
            "task_type": "math",
            "complexity": "high",
            "weaknesses": ["w1"],
            "strengths": ["s1"],
            "changes_made": ["c1"],
            "framework_applied": "chain-of-thought",
            "optimization_notes": "notes",
            "strategy_reasoning": "reasoning",
            "strategy_confidence": 0.95,
            "clarity_score": 0.9,
            "specificity_score": 0.8,
            "structure_score": 0.7,
            "faithfulness_score": 0.85,
            "overall_score": 0.82,
            "is_improvement": True,
            "verdict": "Great",
            "model_used": "test-model",
            "input_tokens": 200,
            "output_tokens": 100,
        }
        apply_pipeline_result_to_orm(opt, data, 1500)

        assert opt.status == OptimizationStatus.COMPLETED
        assert opt.optimized_prompt == "new prompt"
        assert opt.task_type == "math"
        assert opt.duration_ms == 1500
        assert opt.model_used == "test-model"

    def test_status_set_to_completed(self):
        opt = _make_optimization(status=OptimizationStatus.RUNNING)
        apply_pipeline_result_to_orm(opt, {}, 0)
        assert opt.status == OptimizationStatus.COMPLETED

    def test_json_lists_serialized(self):
        opt = _make_optimization()
        data = {
            "weaknesses": ["w1", "w2"],
            "strengths": ["s1"],
            "changes_made": ["c1", "c2", "c3"],
        }
        apply_pipeline_result_to_orm(opt, data, 0)
        assert json.loads(opt.weaknesses) == ["w1", "w2"]
        assert json.loads(opt.strengths) == ["s1"]
        assert json.loads(opt.changes_made) == ["c1", "c2", "c3"]

    def test_duration_from_parameter(self):
        opt = _make_optimization()
        apply_pipeline_result_to_orm(opt, {}, 9999)
        assert opt.duration_ms == 9999

    def test_missing_fields_become_none(self):
        opt = _make_optimization()
        apply_pipeline_result_to_orm(opt, {}, 0)
        assert opt.optimized_prompt is None
        assert opt.task_type is None
        assert opt.clarity_score is None

    def test_none_lists_become_none_not_null_string(self):
        opt = _make_optimization()
        data = {"weaknesses": None, "strengths": None, "changes_made": None}
        apply_pipeline_result_to_orm(opt, data, 0)
        assert opt.weaknesses is None
        assert opt.strengths is None
        assert opt.changes_made is None


# ---------------------------------------------------------------------------
# TestOptimizationToResponse
# ---------------------------------------------------------------------------

class TestOptimizationToResponse:
    def test_creates_valid_schema(self):
        opt = _make_optimization()
        response = optimization_to_response(opt)
        assert response.id == "test-id-001"
        assert response.raw_prompt == "test raw prompt"
        assert response.status == OptimizationStatus.COMPLETED

    def test_json_fields_deserialized(self):
        opt = _make_optimization()
        response = optimization_to_response(opt)
        assert response.weaknesses == ["vague"]
        assert response.strengths == ["clear"]
        assert response.changes_made == ["added role"]
        assert response.tags == ["tag1", "tag2"]

    def test_created_at_included(self):
        opt = _make_optimization()
        response = optimization_to_response(opt)
        assert response.created_at == datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# TestOptimizationToSummary
# ---------------------------------------------------------------------------

class TestOptimizationToSummary:
    def test_long_prompt_truncated_with_ellipsis(self):
        long_prompt = "x" * 200
        opt = _make_optimization(raw_prompt=long_prompt)
        summary = optimization_to_summary(opt)
        assert summary["raw_prompt_preview"] == "x" * 100 + "..."
        assert "raw_prompt" not in summary

    def test_short_prompt_no_ellipsis(self):
        opt = _make_optimization(raw_prompt="short")
        summary = optimization_to_summary(opt)
        assert summary["raw_prompt_preview"] == "short"

    def test_score_display_converted(self):
        opt = _make_optimization(overall_score=0.85)
        summary = optimization_to_summary(opt)
        # score_to_display(0.85) = max(1, min(10, round(8.5))) = 8
        assert summary["overall_score"] == 8

    def test_raw_prompt_removed_preview_added(self):
        opt = _make_optimization()
        summary = optimization_to_summary(opt)
        assert "raw_prompt" not in summary
        assert "raw_prompt_preview" in summary

    def test_only_summary_fields_present(self):
        opt = _make_optimization()
        summary = optimization_to_summary(opt)
        # Should not contain full-detail fields
        assert "optimized_prompt" not in summary
        assert "clarity_score" not in summary
        assert "verdict" not in summary
        assert "optimization_notes" not in summary
        # Should contain summary fields
        assert "id" in summary
        assert "task_type" in summary
        assert "status" in summary


# ---------------------------------------------------------------------------
# TestUpdateOptimizationStatus
# ---------------------------------------------------------------------------

class TestUpdateOptimizationStatus:
    @pytest.mark.asyncio
    async def test_success_path(self, db_session):
        """Successful pipeline result updates the record to COMPLETED."""
        opt = Optimization(
            id="upd-001", raw_prompt="test",
            status=OptimizationStatus.RUNNING,
        )
        db_session.add(opt)
        await db_session.flush()

        result_data = {
            "optimized_prompt": "better",
            "task_type": "coding",
            "overall_score": 0.85,
        }
        await update_optimization_status(
            "upd-001", result_data=result_data,
            start_time=time.time() - 1.5,
            session=db_session,
        )
        stmt = select(Optimization).where(Optimization.id == "upd-001")
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.status == OptimizationStatus.COMPLETED
        assert row.optimized_prompt == "better"
        assert row.duration_ms > 0

    @pytest.mark.asyncio
    async def test_error_path(self, db_session):
        """Error path sets status to ERROR with the error message."""
        opt = Optimization(
            id="upd-002", raw_prompt="test",
            status=OptimizationStatus.RUNNING,
        )
        db_session.add(opt)
        await db_session.flush()

        await update_optimization_status(
            "upd-002", error="Something went wrong",
            session=db_session,
        )
        stmt = select(Optimization).where(Optimization.id == "upd-002")
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.status == OptimizationStatus.ERROR
        assert row.error_message == "Something went wrong"

    @pytest.mark.asyncio
    async def test_not_found_no_crash(self, db_session):
        """Updating a nonexistent record should not raise."""
        await update_optimization_status(
            "nonexistent", error="whatever",
            session=db_session,
        )

    @pytest.mark.asyncio
    async def test_model_fallback_applied(self, db_session):
        """When result has no model_used, model_fallback should be used."""
        opt = Optimization(
            id="upd-003", raw_prompt="test",
            status=OptimizationStatus.RUNNING,
        )
        db_session.add(opt)
        await db_session.flush()

        await update_optimization_status(
            "upd-003",
            result_data={"optimized_prompt": "better"},
            start_time=time.time(),
            model_fallback="claude-opus-4-6",
            session=db_session,
        )
        stmt = select(Optimization).where(Optimization.id == "upd-003")
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.model_used == "claude-opus-4-6"
