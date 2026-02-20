"""Tests for the PromptOptimizer service — response parsing, fallback
behavior, usage tracking, and strategy propagation."""

import json
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.constants import Strategy
from app.prompts.optimizer_prompts import OPTIMIZER_SYSTEM_PROMPT
from app.providers.types import TokenUsage
from app.services.analyzer import AnalysisResult
from app.services.optimizer import PromptOptimizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(response: dict, usage: TokenUsage | None = None):
    provider = MagicMock()
    completion = MagicMock()
    completion.usage = usage

    async def _complete(request):
        return response, completion

    provider.complete_json = AsyncMock(side_effect=_complete)
    return provider


def _default_analysis():
    return AnalysisResult(
        task_type="coding",
        complexity="medium",
        weaknesses=["vague"],
        strengths=["clear intent"],
    )


# ---------------------------------------------------------------------------
# TestOptimizerResponseParsing
# ---------------------------------------------------------------------------

class TestOptimizerResponseParsing:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        provider = _make_provider({
            "optimized_prompt": "Better prompt",
            "framework_applied": "persona-assignment",
            "changes_made": ["added role", "added constraints"],
            "optimization_notes": "Applied role-based strategy.",
        })
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.optimized_prompt == "Better prompt"
        assert result.framework_applied == "persona-assignment"
        assert result.changes_made == ["added role", "added constraints"]
        assert result.optimization_notes == "Applied role-based strategy."

    @pytest.mark.asyncio
    async def test_missing_optimized_prompt_falls_back_to_raw(self):
        provider = _make_provider({})
        result = await PromptOptimizer(provider).optimize("my raw prompt", _default_analysis())
        assert result.optimized_prompt == "my raw prompt"

    @pytest.mark.asyncio
    async def test_missing_framework_applied_falls_back_to_strategy(self):
        provider = _make_provider({})
        result = await PromptOptimizer(provider).optimize(
            "raw", _default_analysis(), strategy="few-shot-scaffolding",
        )
        assert result.framework_applied == "few-shot-scaffolding"

    @pytest.mark.asyncio
    async def test_missing_changes_made_defaults_to_empty_list(self):
        provider = _make_provider({})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.changes_made == []

    @pytest.mark.asyncio
    async def test_missing_optimization_notes_defaults_to_empty_string(self):
        provider = _make_provider({})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.optimization_notes == ""

    @pytest.mark.asyncio
    async def test_empty_response(self):
        provider = _make_provider({})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.optimized_prompt == "raw"
        assert result.framework_applied == Strategy.ROLE_TASK_FORMAT
        assert result.changes_made == []
        assert result.optimization_notes == ""

    @pytest.mark.asyncio
    async def test_extra_keys_ignored(self):
        provider = _make_provider({
            "optimized_prompt": "ok", "extra_key": "ignored",
        })
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.optimized_prompt == "ok"
        assert not hasattr(result, "extra_key")

    @pytest.mark.asyncio
    async def test_explicit_none_value_for_optimized_prompt(self):
        """When LLM returns None for optimized_prompt, falls back to raw prompt."""
        provider = _make_provider({"optimized_prompt": None})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        # Fallback: falsy optimized_prompt triggers raw prompt passthrough
        assert result.optimized_prompt == "raw"


# ---------------------------------------------------------------------------
# TestOptimizerUsageAndRequest
# ---------------------------------------------------------------------------

class TestOptimizerUsageAndRequest:
    @pytest.mark.asyncio
    async def test_last_usage_set(self):
        usage = TokenUsage(input_tokens=300, output_tokens=200)
        provider = _make_provider({}, usage=usage)
        optimizer = PromptOptimizer(provider)
        await optimizer.optimize("raw", _default_analysis())
        assert optimizer.last_usage is usage

    @pytest.mark.asyncio
    async def test_last_usage_none(self):
        provider = _make_provider({}, usage=None)
        optimizer = PromptOptimizer(provider)
        await optimizer.optimize("raw", _default_analysis())
        assert optimizer.last_usage is None

    @pytest.mark.asyncio
    async def test_system_prompt_is_optimizer_prompt(self):
        provider = _make_provider({})
        await PromptOptimizer(provider).optimize("raw", _default_analysis())
        call_args = provider.complete_json.call_args[0][0]
        assert call_args.system_prompt == OPTIMIZER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_user_message_contains_raw_prompt_analysis_strategy(self):
        provider = _make_provider({})
        analysis = _default_analysis()
        await PromptOptimizer(provider).optimize("my prompt", analysis, "few-shot-scaffolding")
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert parsed["raw_prompt"] == "my prompt"
        assert parsed["strategy"] == "few-shot-scaffolding"
        assert parsed["analysis"] == asdict(analysis)

    @pytest.mark.asyncio
    async def test_default_strategy_is_structured_enhancement(self):
        provider = _make_provider({})
        await PromptOptimizer(provider).optimize("raw", _default_analysis())
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert parsed["strategy"] == Strategy.ROLE_TASK_FORMAT


# ---------------------------------------------------------------------------
# TestOptimizerStrategies
# ---------------------------------------------------------------------------

class TestOptimizerStrategies:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("strategy", [s.value for s in Strategy])
    async def test_strategy_name_appears_in_user_message(self, strategy):
        provider = _make_provider({})
        await PromptOptimizer(provider).optimize("raw", _default_analysis(), strategy)
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert parsed["strategy"] == strategy

    @pytest.mark.asyncio
    async def test_analysis_serialized_as_dict(self):
        provider = _make_provider({})
        analysis = AnalysisResult("math", "high", ["complex"], ["structured"])
        await PromptOptimizer(provider).optimize("raw", analysis)
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert parsed["analysis"]["task_type"] == "math"
        assert parsed["analysis"]["complexity"] == "high"
        assert parsed["analysis"]["weaknesses"] == ["complex"]
        assert parsed["analysis"]["strengths"] == ["structured"]


# ---------------------------------------------------------------------------
# TestOptimizerChangesMadeValidation — ensure_string_list on changes_made (#2)
# ---------------------------------------------------------------------------

class TestOptimizerChangesMadeValidation:
    """changes_made is validated through _ensure_string_list to coerce non-string items."""

    @pytest.mark.asyncio
    async def test_string_list_passes_through(self):
        provider = _make_provider({"changes_made": ["added role", "added constraints"]})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.changes_made == ["added role", "added constraints"]

    @pytest.mark.asyncio
    async def test_int_items_coerced_to_strings(self):
        provider = _make_provider({"changes_made": [1, 2, 3]})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.changes_made == ["1", "2", "3"]

    @pytest.mark.asyncio
    async def test_none_items_filtered_out(self):
        provider = _make_provider({"changes_made": ["change 1", None, "change 2"]})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.changes_made == ["change 1", "change 2"]

    @pytest.mark.asyncio
    async def test_dict_items_coerced_to_strings(self):
        provider = _make_provider({"changes_made": [{"detail": "something"}, "ok"]})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert len(result.changes_made) == 2
        assert all(isinstance(c, str) for c in result.changes_made)

    @pytest.mark.asyncio
    async def test_empty_string_items_filtered_out(self):
        provider = _make_provider({"changes_made": ["change 1", "", "  ", "change 2"]})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.changes_made == ["change 1", "change 2"]

    @pytest.mark.asyncio
    async def test_none_changes_made_returns_empty_list(self):
        provider = _make_provider({"changes_made": None})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.changes_made == []

    @pytest.mark.asyncio
    async def test_missing_changes_made_returns_empty_list(self):
        provider = _make_provider({})
        result = await PromptOptimizer(provider).optimize("raw", _default_analysis())
        assert result.changes_made == []


# ---------------------------------------------------------------------------
# TestOptimizerCodebaseContext
# ---------------------------------------------------------------------------

class TestOptimizerCodebaseContext:
    """Verify codebase_context is injected into the user message when provided."""

    @pytest.mark.asyncio
    async def test_context_included_in_user_message(self):
        from app.schemas.context import CodebaseContext

        provider = _make_provider({})
        ctx = CodebaseContext(language="Python 3.14", framework="FastAPI")
        await PromptOptimizer(provider).optimize(
            "raw", _default_analysis(), codebase_context=ctx,
        )
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert "codebase_context" in parsed
        assert "Python 3.14" in parsed["codebase_context"]
        assert "FastAPI" in parsed["codebase_context"]

    @pytest.mark.asyncio
    async def test_no_context_means_no_field(self):
        provider = _make_provider({})
        await PromptOptimizer(provider).optimize("raw", _default_analysis())
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert "codebase_context" not in parsed

    @pytest.mark.asyncio
    async def test_empty_context_means_no_field(self):
        from app.schemas.context import CodebaseContext

        provider = _make_provider({})
        ctx = CodebaseContext()  # all defaults — render() returns None
        await PromptOptimizer(provider).optimize(
            "raw", _default_analysis(), codebase_context=ctx,
        )
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert "codebase_context" not in parsed
