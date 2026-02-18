"""Tests for the LLM-based StrategySelector (with heuristic fallback)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.constants import Strategy
from app.prompts.strategy_prompt import STRATEGY_SYSTEM_PROMPT
from app.services.analyzer import AnalysisResult
from app.services.strategy_selector import (
    StrategySelection,
    StrategySelector,
    _STRATEGY_DESCRIPTIONS,
)


def _make_analysis(
    task_type: str = "coding",
    complexity: str = "medium",
    weaknesses: list[str] | None = None,
    strengths: list[str] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        task_type=task_type,
        complexity=complexity,
        weaknesses=weaknesses or [],
        strengths=strengths or [],
    )


def _make_fake_provider(response: dict, usage=None):
    """Create a mock LLM provider returning a canned JSON response."""
    provider = MagicMock()
    provider.model_name = "mock-model"
    completion = MagicMock()
    completion.usage = usage
    provider.complete_json = AsyncMock(return_value=(response, completion))
    return provider


class TestLLMStrategySelector:
    """Happy-path tests for the LLM-based StrategySelector."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_correct_selection(self):
        """Valid LLM response produces correct StrategySelection."""
        provider = _make_fake_provider({
            "strategy": "chain-of-thought",
            "reasoning": "High complexity math needs step-by-step.",
            "confidence": 0.92,
        })
        selector = StrategySelector(provider)
        result = await selector.select(
            _make_analysis(task_type="math", complexity="high"),
            raw_prompt="Solve this equation",
        )
        assert result.strategy == Strategy.CHAIN_OF_THOUGHT
        assert result.reasoning == "High complexity math needs step-by-step."
        assert result.confidence == 0.92
        assert result.task_type == "math"

    @pytest.mark.asyncio
    async def test_all_five_strategies_accepted(self):
        """LLM can return any of the 5 strategies."""
        for strategy in Strategy:
            provider = _make_fake_provider({
                "strategy": strategy.value,
                "reasoning": f"Selected {strategy.value}.",
                "confidence": 0.80,
            })
            selector = StrategySelector(provider)
            result = await selector.select(_make_analysis(), raw_prompt="Test")
            assert result.strategy == strategy

    @pytest.mark.asyncio
    async def test_task_type_populated_from_analysis(self):
        """result.task_type should come from the analysis, not the LLM."""
        provider = _make_fake_provider({
            "strategy": "few-shot-scaffolding",
            "reasoning": "Good match.",
            "confidence": 0.75,
        })
        selector = StrategySelector(provider)
        result = await selector.select(
            _make_analysis(task_type="extraction"),
            raw_prompt="Extract data",
        )
        assert result.task_type == "extraction"


class TestLLMValidation:
    """Tests for LLM response validation and normalization."""

    @pytest.mark.asyncio
    async def test_unknown_strategy_falls_back_to_structured_enhancement(self):
        """Unknown strategy value defaults to structured-enhancement."""
        provider = _make_fake_provider({
            "strategy": "made-up-strategy",
            "reasoning": "Some reasoning.",
            "confidence": 0.80,
        })
        selector = StrategySelector(provider)
        result = await selector.select(_make_analysis(), raw_prompt="Test")
        assert result.strategy == Strategy.ROLE_TASK_FORMAT

    @pytest.mark.asyncio
    async def test_missing_strategy_key_falls_back(self):
        """Missing strategy key defaults to structured-enhancement."""
        provider = _make_fake_provider({
            "reasoning": "Some reasoning.",
            "confidence": 0.80,
        })
        selector = StrategySelector(provider)
        result = await selector.select(_make_analysis(), raw_prompt="Test")
        assert result.strategy == Strategy.ROLE_TASK_FORMAT

    @pytest.mark.asyncio
    async def test_confidence_clamped_above_one(self):
        """Confidence > 1.0 is clamped to 1.0."""
        provider = _make_fake_provider({
            "strategy": "persona-assignment",
            "reasoning": "Very confident.",
            "confidence": 1.5,
        })
        selector = StrategySelector(provider)
        result = await selector.select(_make_analysis(), raw_prompt="Test")
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_confidence_clamped_below_zero(self):
        """Confidence < 0.0 is clamped to 0.0."""
        provider = _make_fake_provider({
            "strategy": "persona-assignment",
            "reasoning": "Not confident at all.",
            "confidence": -0.5,
        })
        selector = StrategySelector(provider)
        result = await selector.select(_make_analysis(), raw_prompt="Test")
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_non_numeric_confidence_defaults(self):
        """Non-numeric confidence defaults to 0.75."""
        provider = _make_fake_provider({
            "strategy": "persona-assignment",
            "reasoning": "Test.",
            "confidence": "very high",
        })
        selector = StrategySelector(provider)
        result = await selector.select(_make_analysis(), raw_prompt="Test")
        assert result.confidence == 0.75

    @pytest.mark.asyncio
    async def test_empty_reasoning_gets_default(self):
        """Empty reasoning string gets a default."""
        provider = _make_fake_provider({
            "strategy": "few-shot-scaffolding",
            "reasoning": "",
            "confidence": 0.80,
        })
        selector = StrategySelector(provider)
        result = await selector.select(
            _make_analysis(task_type="classification"),
            raw_prompt="Classify this",
        )
        assert result.reasoning  # non-empty
        assert "few-shot-scaffolding" in result.reasoning


class TestLLMFallback:
    """Tests for fallback to HeuristicStrategySelector on errors."""

    @pytest.mark.asyncio
    async def test_llm_error_falls_back_to_heuristic(self):
        """When the LLM call raises, fallback to the heuristic."""
        provider = MagicMock()
        provider.model_name = "mock-model"
        provider.complete_json = AsyncMock(side_effect=RuntimeError("LLM failed"))

        selector = StrategySelector(provider)
        result = await selector.select(
            _make_analysis(task_type="coding", weaknesses=["Instructions are vague"]),
            raw_prompt="Write code",
        )
        # Heuristic for coding + vague = constraint-focused (P2)
        assert result.strategy == Strategy.CONSTRAINT_INJECTION
        assert result.task_type == "coding"

    @pytest.mark.asyncio
    async def test_fallback_preserves_task_type(self):
        """Fallback result still has task_type populated."""
        provider = MagicMock()
        provider.model_name = "mock-model"
        provider.complete_json = AsyncMock(side_effect=Exception("timeout"))

        selector = StrategySelector(provider)
        result = await selector.select(
            _make_analysis(task_type="math", complexity="high"),
            raw_prompt="Solve this",
        )
        assert result.task_type == "math"


class TestLLMUsageTracking:
    """Tests for token usage tracking."""

    @pytest.mark.asyncio
    async def test_usage_tracked_on_last_usage(self):
        """selector.last_usage should reflect the LLM completion usage."""
        from app.providers.types import TokenUsage

        usage = TokenUsage(input_tokens=100, output_tokens=50)
        provider = _make_fake_provider(
            {"strategy": "persona-assignment", "reasoning": "Test.", "confidence": 0.80},
            usage=usage,
        )
        selector = StrategySelector(provider)
        await selector.select(_make_analysis(), raw_prompt="Test")
        assert selector.last_usage is not None
        assert selector.last_usage.input_tokens == 100
        assert selector.last_usage.output_tokens == 50

    @pytest.mark.asyncio
    async def test_usage_none_when_no_usage(self):
        """selector.last_usage is None when completion has no usage."""
        provider = _make_fake_provider(
            {"strategy": "persona-assignment", "reasoning": "Test.", "confidence": 0.80},
            usage=None,
        )
        selector = StrategySelector(provider)
        await selector.select(_make_analysis(), raw_prompt="Test")
        assert selector.last_usage is None


class TestLLMRequestContent:
    """Tests verifying the content sent to the LLM."""

    @pytest.mark.asyncio
    async def test_system_prompt_is_strategy_prompt(self):
        """The request should use STRATEGY_SYSTEM_PROMPT."""
        provider = _make_fake_provider({
            "strategy": "persona-assignment",
            "reasoning": "Test.",
            "confidence": 0.80,
        })
        selector = StrategySelector(provider)
        await selector.select(_make_analysis(), raw_prompt="Test prompt")

        provider.complete_json.assert_called_once()
        request = provider.complete_json.call_args[0][0]
        assert request.system_prompt == STRATEGY_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_user_message_contains_raw_prompt(self):
        """The user message should contain the raw prompt."""
        provider = _make_fake_provider({
            "strategy": "persona-assignment",
            "reasoning": "Test.",
            "confidence": 0.80,
        })
        selector = StrategySelector(provider)
        await selector.select(_make_analysis(), raw_prompt="Write a REST API")

        request = provider.complete_json.call_args[0][0]
        payload = json.loads(request.user_message)
        assert payload["raw_prompt"] == "Write a REST API"

    @pytest.mark.asyncio
    async def test_user_message_contains_analysis(self):
        """The user message should contain the analysis result."""
        provider = _make_fake_provider({
            "strategy": "persona-assignment",
            "reasoning": "Test.",
            "confidence": 0.80,
        })
        analysis = _make_analysis(
            task_type="coding",
            complexity="high",
            weaknesses=["Vague"],
            strengths=["Clear intent"],
        )
        selector = StrategySelector(provider)
        await selector.select(analysis, raw_prompt="Test")

        request = provider.complete_json.call_args[0][0]
        payload = json.loads(request.user_message)
        assert payload["analysis"]["task_type"] == "coding"
        assert payload["analysis"]["complexity"] == "high"
        assert payload["analysis"]["weaknesses"] == ["Vague"]
        assert payload["analysis"]["strengths"] == ["Clear intent"]

    @pytest.mark.asyncio
    async def test_user_message_contains_available_strategies(self):
        """The user message should list all available strategies."""
        provider = _make_fake_provider({
            "strategy": "persona-assignment",
            "reasoning": "Test.",
            "confidence": 0.80,
        })
        selector = StrategySelector(provider)
        await selector.select(_make_analysis(), raw_prompt="Test")

        request = provider.complete_json.call_args[0][0]
        payload = json.loads(request.user_message)
        strategies = payload["available_strategies"]
        assert set(strategies.keys()) == {s.value for s in Strategy}


class TestStrategyDescriptions:
    """Tests for the _STRATEGY_DESCRIPTIONS constant."""

    def test_all_strategies_have_descriptions(self):
        """Every Strategy enum value should have a description."""
        assert set(_STRATEGY_DESCRIPTIONS.keys()) == set(Strategy)

    def test_descriptions_are_nonempty_strings(self):
        """Each description should be a non-empty string."""
        for strategy, desc in _STRATEGY_DESCRIPTIONS.items():
            assert isinstance(desc, str), f"{strategy} description is not a string"
            assert len(desc) > 0, f"{strategy} description is empty"
