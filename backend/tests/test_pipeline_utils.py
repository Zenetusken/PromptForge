"""Tests for pipeline utility functions — _add_usage, _sse_event,
_select_strategy, _assemble_result, and compute_progress."""

import json

import pytest

from app.constants import Strategy, compute_progress
from app.providers.types import TokenUsage
from app.services.analyzer import AnalysisResult
from app.services.optimizer import OptimizationResult
from app.services.pipeline import (
    PipelineResult,
    _add_usage,
    _assemble_result,
    _select_strategy,
    _sse_event,
)
from app.services.strategy_selector import StrategySelection
from app.services.validator import ValidationResult

# ---------------------------------------------------------------------------
# TestAddUsage
# ---------------------------------------------------------------------------

class TestAddUsage:
    def test_none_plus_none(self):
        assert _add_usage(None, None) is None

    def test_none_plus_usage(self):
        u = TokenUsage(input_tokens=10, output_tokens=5)
        assert _add_usage(None, u) is u

    def test_usage_plus_none(self):
        u = TokenUsage(input_tokens=10, output_tokens=5)
        assert _add_usage(u, None) is u

    def test_sum_both(self):
        a = TokenUsage(input_tokens=10, output_tokens=5)
        b = TokenUsage(input_tokens=20, output_tokens=15)
        result = _add_usage(a, b)
        assert result.input_tokens == 30
        assert result.output_tokens == 20

    def test_none_input_tokens_treated_as_zero(self):
        a = TokenUsage(input_tokens=None, output_tokens=5)
        b = TokenUsage(input_tokens=10, output_tokens=None)
        result = _add_usage(a, b)
        assert result.input_tokens == 10
        assert result.output_tokens == 5

    def test_both_fields_none_gives_zeros(self):
        a = TokenUsage(input_tokens=None, output_tokens=None)
        b = TokenUsage(input_tokens=None, output_tokens=None)
        result = _add_usage(a, b)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_returns_new_token_usage(self):
        a = TokenUsage(input_tokens=1, output_tokens=1)
        b = TokenUsage(input_tokens=1, output_tokens=1)
        result = _add_usage(a, b)
        assert result is not a
        assert result is not b


# ---------------------------------------------------------------------------
# TestSseEvent
# ---------------------------------------------------------------------------

class TestSseEvent:
    def test_correct_format(self):
        result = _sse_event("test", {"key": "value"})
        assert result.startswith("event: test\n")
        assert result.endswith("\n\n")

    def test_data_is_json(self):
        result = _sse_event("test", {"key": "value"})
        lines = result.strip().split("\n")
        data_line = lines[1]
        assert data_line.startswith("data: ")
        parsed = json.loads(data_line[6:])
        assert parsed == {"key": "value"}

    def test_nested_data(self):
        data = {"outer": {"inner": [1, 2, 3]}}
        result = _sse_event("nested", data)
        data_line = result.strip().split("\n")[1]
        parsed = json.loads(data_line[6:])
        assert parsed["outer"]["inner"] == [1, 2, 3]

    def test_list_data(self):
        # data param is typed dict, but json.dumps handles any serializable
        data = {"items": ["a", "b", "c"]}
        result = _sse_event("list", data)
        data_line = result.strip().split("\n")[1]
        parsed = json.loads(data_line[6:])
        assert parsed["items"] == ["a", "b", "c"]

    def test_double_newline_terminator(self):
        result = _sse_event("test", {"k": "v"})
        assert result[-2:] == "\n\n"

    def test_event_type_in_first_line(self):
        result = _sse_event("my_event", {"k": "v"})
        first_line = result.split("\n")[0]
        assert first_line == "event: my_event"

    def test_special_characters_escaped(self):
        data = {"text": 'quote "here" and\nnewline'}
        result = _sse_event("test", data)
        data_line = result.strip().split("\n")[1]
        parsed = json.loads(data_line[6:])
        assert parsed["text"] == 'quote "here" and\nnewline'


# ---------------------------------------------------------------------------
# TestSelectStrategy
# ---------------------------------------------------------------------------

class TestSelectStrategy:
    @pytest.mark.asyncio
    async def test_valid_override_returns_confidence_one(self):
        analysis = AnalysisResult("general", "medium", [], [])
        result, usage = await _select_strategy(analysis, "chain-of-thought")
        assert result.strategy == Strategy.CHAIN_OF_THOUGHT
        assert result.confidence == 1.0
        assert usage is None

    @pytest.mark.asyncio
    async def test_override_reasoning_mentions_user_specified(self):
        analysis = AnalysisResult("general", "medium", [], [])
        result, _ = await _select_strategy(analysis, "few-shot-scaffolding")
        assert "User-specified" in result.reasoning

    @pytest.mark.parametrize("strategy", [s.value for s in Strategy])
    @pytest.mark.asyncio
    async def test_each_strategy_as_override(self, strategy):
        analysis = AnalysisResult("general", "medium", [], [])
        result, _ = await _select_strategy(analysis, strategy)
        assert result.strategy == strategy
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_invalid_override_raises_value_error(self):
        analysis = AnalysisResult("general", "medium", [], [])
        with pytest.raises(ValueError, match="Unknown strategy"):
            await _select_strategy(analysis, "nonexistent-strategy")

    @pytest.mark.asyncio
    async def test_invalid_override_error_lists_valid_strategies(self):
        analysis = AnalysisResult("general", "medium", [], [])
        with pytest.raises(ValueError) as exc_info:
            await _select_strategy(analysis, "bad")
        for s in Strategy:
            assert s.value in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_none_override_delegates_to_llm_selector(self):
        """None override should delegate to the LLM-based selector."""
        from unittest.mock import AsyncMock, MagicMock

        provider = MagicMock()
        provider.model_name = "mock-model"
        completion = MagicMock()
        completion.usage = None
        provider.complete_json = AsyncMock(return_value=(
            {
                "strategy": "persona-assignment",
                "reasoning": "Coding needs expert.",
                "confidence": 0.78,
            },
            completion,
        ))
        analysis = AnalysisResult("coding", "medium", [], [])
        result, _ = await _select_strategy(analysis, None, llm_provider=provider)
        assert result.strategy == Strategy.PERSONA_ASSIGNMENT

    @pytest.mark.asyncio
    async def test_empty_string_override_delegates_to_llm_selector(self):
        """Empty string is falsy, so it should delegate to the LLM selector."""
        from unittest.mock import AsyncMock, MagicMock

        provider = MagicMock()
        provider.model_name = "mock-model"
        completion = MagicMock()
        completion.usage = None
        provider.complete_json = AsyncMock(return_value=(
            {
                "strategy": "persona-assignment",
                "reasoning": "Coding needs expert.",
                "confidence": 0.78,
            },
            completion,
        ))
        analysis = AnalysisResult("coding", "medium", [], [])
        result, _ = await _select_strategy(analysis, "", llm_provider=provider)
        assert result.strategy == Strategy.PERSONA_ASSIGNMENT


# ---------------------------------------------------------------------------
# TestAssembleResult
# ---------------------------------------------------------------------------

class TestAssembleResult:
    def _make_inputs(self):
        analysis = AnalysisResult("coding", "high", ["vague"], ["clear"])
        strategy = StrategySelection(Strategy.PERSONA_ASSIGNMENT, "test reasoning", 0.85)
        optimization = OptimizationResult("optimized", "persona-assignment", ["change1"], "notes")
        validation = ValidationResult(0.9, 0.8, 0.7, 0.85, 0.82, True, "Good")
        return analysis, strategy, optimization, validation

    def test_all_fields_mapped(self):
        analysis, strategy, optimization, validation = self._make_inputs()
        result = _assemble_result(
            analysis, strategy, optimization, validation, 1000, "test-model",
        )
        assert isinstance(result, PipelineResult)
        assert result.task_type == "coding"
        assert result.complexity == "high"
        assert result.weaknesses == ["vague"]
        assert result.strengths == ["clear"]
        assert result.optimized_prompt == "optimized"
        assert result.framework_applied == "persona-assignment"
        assert result.changes_made == ["change1"]
        assert result.optimization_notes == "notes"
        assert result.clarity_score == 0.9
        assert result.overall_score == 0.82
        assert result.is_improvement is True
        assert result.verdict == "Good"
        assert result.duration_ms == 1000
        assert result.model_used == "test-model"
        assert result.strategy_reasoning == "test reasoning"
        assert result.strategy_confidence == 0.85

    def test_usage_none_gives_none_tokens(self):
        analysis, strategy, optimization, validation = self._make_inputs()
        result = _assemble_result(
            analysis, strategy, optimization, validation, 500, "m", None,
        )
        assert result.input_tokens is None
        assert result.output_tokens is None

    def test_usage_present_gives_token_counts(self):
        analysis, strategy, optimization, validation = self._make_inputs()
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        result = _assemble_result(
            analysis, strategy, optimization, validation, 500, "m", usage,
        )
        assert result.input_tokens == 100
        assert result.output_tokens == 50


# ---------------------------------------------------------------------------
# TestComputeProgress
# ---------------------------------------------------------------------------

class TestComputeProgress:
    def test_index_zero(self):
        assert compute_progress(0) == pytest.approx(0.4)

    def test_index_five(self):
        assert compute_progress(5) == pytest.approx(0.9)

    def test_index_ten_capped(self):
        assert compute_progress(10) == pytest.approx(0.9)

    def test_monotonically_increasing(self):
        values = [compute_progress(i) for i in range(10)]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1]
