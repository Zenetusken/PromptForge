"""Tests for compare_service — classification and data extraction."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.compare_service import classify_situation, extract_scores, generate_top_insights


def _mock_opt(
    raw_prompt="test prompt",
    optimized_prompt="optimized test",
    primary_framework="CO-STAR",
    overall_score=8.0,
    clarity_score=8,
    faithfulness_score=7,
    specificity_score=8,
    structure_score=9,
    conciseness_score=7,
    task_type="code_review",
    complexity="basic",
    duration_ms=4000,
    total_input_tokens=1000,
    total_output_tokens=1100,
    estimated_cost_usd=0.008,
    strategy_source="llm",
    strategy_rationale="Context grounding needed",
    active_guardrails=None,
    linked_repo_full_name=None,
    weaknesses=None,
    strengths=None,
    changes_made=None,
    verdict="Strong improvement",
    issues=None,
    stage_durations=None,
    codebase_context_snapshot=None,
    per_instruction_compliance=None,
    adaptation_snapshot=None,
    is_improvement=True,
    created_at=None,
    deleted_at=None,
    **kwargs,
):
    opt = MagicMock()
    for k, v in locals().items():
        if k not in ("opt", "kwargs"):
            setattr(opt, k, v)
    for k, v in kwargs.items():
        setattr(opt, k, v)
    opt.to_dict = MagicMock(return_value={
        k: v for k, v in locals().items()
        if k not in ("opt", "kwargs") and not k.startswith("_")
    })
    return opt


class TestClassifySituation:
    def test_high_similarity_same_framework_is_reforge(self):
        assert classify_situation(similarity=0.92, fw_a="CO-STAR", fw_b="CO-STAR") == "REFORGE"

    def test_high_similarity_different_framework_is_strategy(self):
        assert classify_situation(similarity=0.90, fw_a="CO-STAR", fw_b="RISEN") == "STRATEGY"

    def test_moderate_similarity_is_evolved(self):
        assert classify_situation(similarity=0.60, fw_a="CO-STAR", fw_b="CO-STAR") == "EVOLVED"

    def test_low_similarity_is_cross(self):
        assert classify_situation(similarity=0.30, fw_a="CO-STAR", fw_b="RISEN") == "CROSS"

    def test_boundary_high(self):
        assert classify_situation(0.85, "X", "X") == "REFORGE"
        assert classify_situation(0.84, "X", "X") == "EVOLVED"

    def test_boundary_low(self):
        assert classify_situation(0.45, "X", "X") == "EVOLVED"
        assert classify_situation(0.44, "X", "X") == "CROSS"

    # Levenshtein fallback uses lower thresholds (0.80/0.35)
    def test_levenshtein_boundary_high(self):
        assert classify_situation(0.80, "X", "X", used_embeddings=False) == "REFORGE"
        assert classify_situation(0.79, "X", "X", used_embeddings=False) == "EVOLVED"

    def test_levenshtein_boundary_low(self):
        assert classify_situation(0.35, "X", "X", used_embeddings=False) == "EVOLVED"
        assert classify_situation(0.34, "X", "X", used_embeddings=False) == "CROSS"


class TestScoreExtraction:
    def test_extracts_all_dimensions(self):
        opt = _mock_opt(clarity_score=8, faithfulness_score=7, specificity_score=8,
                        structure_score=9, conciseness_score=7, overall_score=8.0)
        scores = extract_scores(opt)
        assert scores["clarity"] == 8
        assert scores["overall"] == 8.0
        assert len(scores) == 6

    def test_handles_none_scores(self):
        opt = _mock_opt(clarity_score=None, overall_score=None)
        scores = extract_scores(opt)
        assert scores["clarity"] is None


class TestInsightGeneration:
    def test_generates_top_3_insights(self):
        scores_data = {
            "deltas": {"clarity": 2.0, "faithfulness": -0.5, "specificity": 1.0,
                       "structure": 1.5, "conciseness": 0.0},
            "floors": ["conciseness"],
            "ceilings": [],
        }
        insights = generate_top_insights(
            scores=scores_data,
            structural={"a_input_words": 45, "b_input_words": 120},
            efficiency={"a_duration_ms": 4100, "b_duration_ms": 6500},
            strategy={"a_framework": "CO-STAR", "b_framework": "RISEN"},
            context={"a_repo": None, "b_repo": "owner/repo", "a_has_codebase": False, "b_has_codebase": True},
            validation={"a_verdict": "Strong improvement", "b_verdict": "Moderate improvement", "a_issues": [], "b_issues": ["verbose"]},
            adaptation={"feedbacks_between": 3, "weight_shifts": {"clarity": 0.08}},
            situation="STRATEGY",
        )
        assert len(insights) <= 3
        assert all(isinstance(i, str) for i in insights)
