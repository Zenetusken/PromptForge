"""Tests for the PromptValidator service — score clamping, weighted average,
is_improvement coercion, verdict defaults, full-response parsing, and usage tracking."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.prompts.validator_prompt import VALIDATOR_SYSTEM_PROMPT
from app.providers.types import TokenUsage
from app.services.validator import (
    CLARITY_WEIGHT,
    FAITHFULNESS_WEIGHT,
    SPECIFICITY_WEIGHT,
    STRUCTURE_WEIGHT,
    PromptValidator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(response: dict, usage: TokenUsage | None = None):
    """Return a mock LLM provider that returns *response* from complete_json."""
    provider = MagicMock()
    completion = MagicMock()
    completion.usage = usage

    async def _complete(request):
        return response, completion

    provider.complete_json = AsyncMock(side_effect=_complete)
    return provider


# ---------------------------------------------------------------------------
# TestClampScore — exercises the inner _clamp_score() via validate()
# ---------------------------------------------------------------------------

class TestClampScore:
    """Clamp score extracts a float from the LLM dict, defaulting to 0.5
    and clamping to [0.0, 1.0]."""

    @pytest.mark.asyncio
    async def test_valid_float_passes_through(self):
        provider = _make_provider({"clarity_score": 0.7, "specificity_score": 0.8,
                                   "structure_score": 0.6, "faithfulness_score": 0.9})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.7

    @pytest.mark.asyncio
    async def test_zero_passes_through(self):
        provider = _make_provider({"clarity_score": 0.0, "specificity_score": 0.0,
                                   "structure_score": 0.0, "faithfulness_score": 0.0})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.0

    @pytest.mark.asyncio
    async def test_one_passes_through(self):
        provider = _make_provider({"clarity_score": 1.0, "specificity_score": 1.0,
                                   "structure_score": 1.0, "faithfulness_score": 1.0})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 1.0

    @pytest.mark.asyncio
    async def test_negative_clamped_to_zero(self):
        provider = _make_provider({"clarity_score": -0.5})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.0

    @pytest.mark.asyncio
    async def test_above_one_clamped_to_one(self):
        provider = _make_provider({"clarity_score": 1.5})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 1.0

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_half(self):
        provider = _make_provider({})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.5

    @pytest.mark.asyncio
    async def test_string_number_coerced(self):
        provider = _make_provider({"clarity_score": "0.75"})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.75

    @pytest.mark.asyncio
    async def test_non_numeric_string_defaults_to_half(self):
        provider = _make_provider({"clarity_score": "excellent"})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.5

    @pytest.mark.asyncio
    async def test_none_value_defaults_to_half(self):
        provider = _make_provider({"clarity_score": None})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.5

    @pytest.mark.asyncio
    async def test_int_coercion(self):
        provider = _make_provider({"clarity_score": 1})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 1.0

    @pytest.mark.asyncio
    async def test_bool_true_coerced_to_one(self):
        provider = _make_provider({"clarity_score": True})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 1.0

    @pytest.mark.asyncio
    async def test_bool_false_coerced_to_zero(self):
        provider = _make_provider({"clarity_score": False})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.0


# ---------------------------------------------------------------------------
# TestValidatorScoreComputation
# ---------------------------------------------------------------------------

class TestValidatorScoreComputation:
    """Weighted average = C*0.25 + S*0.25 + St*0.20 + F*0.30, rounded to 4 decimals."""

    @pytest.mark.asyncio
    async def test_weighted_average_formula(self):
        provider = _make_provider({
            "clarity_score": 0.9, "specificity_score": 0.7,
            "structure_score": 0.8, "faithfulness_score": 1.0,
        })
        result = await PromptValidator(provider).validate("a", "b")
        expected = round(
            0.9 * CLARITY_WEIGHT + 0.7 * SPECIFICITY_WEIGHT
            + 0.8 * STRUCTURE_WEIGHT + 1.0 * FAITHFULNESS_WEIGHT, 4
        )
        assert result.overall_score == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_rounding_to_four_decimals(self):
        # 0.33 * 0.25 = 0.0825, 0.67 * 0.25 = 0.1675, 0.41 * 0.20 = 0.082,
        # 0.59 * 0.30 = 0.177  → total 0.509
        provider = _make_provider({
            "clarity_score": 0.33, "specificity_score": 0.67,
            "structure_score": 0.41, "faithfulness_score": 0.59,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score == round(
            0.33 * 0.25 + 0.67 * 0.25 + 0.41 * 0.20 + 0.59 * 0.30, 4
        )

    @pytest.mark.asyncio
    async def test_all_zeros(self):
        provider = _make_provider({
            "clarity_score": 0.0, "specificity_score": 0.0,
            "structure_score": 0.0, "faithfulness_score": 0.0,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score == 0.0

    @pytest.mark.asyncio
    async def test_all_ones(self):
        provider = _make_provider({
            "clarity_score": 1.0, "specificity_score": 1.0,
            "structure_score": 1.0, "faithfulness_score": 1.0,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_all_half(self):
        provider = _make_provider({
            "clarity_score": 0.5, "specificity_score": 0.5,
            "structure_score": 0.5, "faithfulness_score": 0.5,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_clamped_scores_flow_into_average(self):
        """Negative / >1 scores get clamped BEFORE the weighted average."""
        provider = _make_provider({
            "clarity_score": -0.5, "specificity_score": 2.0,
            "structure_score": 0.5, "faithfulness_score": 0.5,
        })
        result = await PromptValidator(provider).validate("a", "b")
        expected = round(
            0.0 * CLARITY_WEIGHT + 1.0 * SPECIFICITY_WEIGHT
            + 0.5 * STRUCTURE_WEIGHT + 0.5 * FAITHFULNESS_WEIGHT, 4
        )
        assert result.overall_score == pytest.approx(expected)


# ---------------------------------------------------------------------------
# TestValidatorIsImprovement
# ---------------------------------------------------------------------------

class TestValidatorIsImprovement:
    """bool(response.get('is_improvement', False)) — documents the bool() trap."""

    @pytest.mark.asyncio
    async def test_true_passes_through(self):
        provider = _make_provider({"is_improvement": True})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is True

    @pytest.mark.asyncio
    async def test_false_passes_through(self):
        provider = _make_provider({"is_improvement": False})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is False

    @pytest.mark.asyncio
    async def test_string_true_coerced(self):
        provider = _make_provider({"is_improvement": "true"})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is True

    @pytest.mark.asyncio
    async def test_string_false_is_truthy_bool_trap(self):
        """bool('false') == True — this is the documented bool() trap."""
        provider = _make_provider({"is_improvement": "false"})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is True  # bool("false") == True

    @pytest.mark.asyncio
    async def test_int_one_truthy(self):
        provider = _make_provider({"is_improvement": 1})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is True

    @pytest.mark.asyncio
    async def test_int_zero_falsy(self):
        provider = _make_provider({"is_improvement": 0})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is False

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_false(self):
        provider = _make_provider({})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is False

    @pytest.mark.asyncio
    async def test_none_value_is_false(self):
        provider = _make_provider({"is_improvement": None})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.is_improvement is False


# ---------------------------------------------------------------------------
# TestValidatorVerdict
# ---------------------------------------------------------------------------

class TestValidatorVerdict:
    @pytest.mark.asyncio
    async def test_string_passes_through(self):
        provider = _make_provider({"verdict": "Great improvement!"})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.verdict == "Great improvement!"

    @pytest.mark.asyncio
    async def test_missing_key_defaults(self):
        provider = _make_provider({})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.verdict == "No verdict available."

    @pytest.mark.asyncio
    async def test_none_value_falls_back_to_default_verdict(self):
        """When LLM returns None for verdict, falls back to default text."""
        provider = _make_provider({"verdict": None})
        result = await PromptValidator(provider).validate("a", "b")
        assert result.verdict == "No verdict available."


# ---------------------------------------------------------------------------
# TestValidatorFullResponse
# ---------------------------------------------------------------------------

class TestValidatorFullResponse:
    @pytest.mark.asyncio
    async def test_happy_path_all_fields(self):
        provider = _make_provider({
            "clarity_score": 0.85, "specificity_score": 0.80,
            "structure_score": 0.75, "faithfulness_score": 0.90,
            "is_improvement": True,
            "verdict": "Solid improvement.",
        })
        result = await PromptValidator(provider).validate("raw", "optimized")
        assert result.clarity_score == 0.85
        assert result.specificity_score == 0.80
        assert result.structure_score == 0.75
        assert result.faithfulness_score == 0.90
        assert result.is_improvement is True
        assert result.verdict == "Solid improvement."

    @pytest.mark.asyncio
    async def test_empty_response_all_defaults(self):
        provider = _make_provider({})
        result = await PromptValidator(provider).validate("raw", "optimized")
        assert result.clarity_score == 0.5
        assert result.specificity_score == 0.5
        assert result.structure_score == 0.5
        assert result.faithfulness_score == 0.5
        assert result.is_improvement is False
        assert result.verdict == "No verdict available."
        assert result.overall_score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_extra_keys_ignored(self):
        provider = _make_provider({
            "clarity_score": 0.7, "extra_field": "ignored",
            "another": 42,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.7
        assert not hasattr(result, "extra_field")

    @pytest.mark.asyncio
    async def test_partial_scores_with_defaults(self):
        provider = _make_provider({
            "clarity_score": 0.9, "faithfulness_score": 0.8,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.clarity_score == 0.9
        assert result.specificity_score == 0.5  # default
        assert result.structure_score == 0.5    # default
        assert result.faithfulness_score == 0.8


# ---------------------------------------------------------------------------
# TestValidatorUsageAndRequest
# ---------------------------------------------------------------------------

class TestValidatorUsageAndRequest:
    @pytest.mark.asyncio
    async def test_last_usage_set(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        provider = _make_provider({}, usage=usage)
        validator = PromptValidator(provider)
        await validator.validate("a", "b")
        assert validator.last_usage is usage

    @pytest.mark.asyncio
    async def test_last_usage_none(self):
        provider = _make_provider({}, usage=None)
        validator = PromptValidator(provider)
        await validator.validate("a", "b")
        assert validator.last_usage is None

    @pytest.mark.asyncio
    async def test_system_prompt_is_validator_prompt(self):
        provider = _make_provider({})
        await PromptValidator(provider).validate("a", "b")
        call_args = provider.complete_json.call_args[0][0]
        assert call_args.system_prompt == VALIDATOR_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_user_message_contains_both_prompts(self):
        provider = _make_provider({})
        await PromptValidator(provider).validate("my raw prompt", "my optimized prompt")
        call_args = provider.complete_json.call_args[0][0]
        parsed = json.loads(call_args.user_message)
        assert parsed["raw_prompt"] == "my raw prompt"
        assert parsed["optimized_prompt"] == "my optimized prompt"


# ---------------------------------------------------------------------------
# TestIsImprovementCrossCheck — server-side override when LLM disagrees (#6)
# ---------------------------------------------------------------------------

class TestIsImprovementCrossCheck:
    """When overall_score strongly contradicts is_improvement, override the LLM."""

    @pytest.mark.asyncio
    async def test_low_score_overrides_llm_true_to_false(self):
        """LLM says improvement=True but overall < 0.4 → forced to False."""
        # All scores at 0.2 → overall = 0.2
        provider = _make_provider({
            "clarity_score": 0.2, "specificity_score": 0.2,
            "structure_score": 0.2, "faithfulness_score": 0.2,
            "is_improvement": True,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score < 0.4
        assert result.is_improvement is False

    @pytest.mark.asyncio
    async def test_high_score_overrides_llm_false_to_true(self):
        """LLM says improvement=False but overall > 0.7 → forced to True."""
        provider = _make_provider({
            "clarity_score": 0.9, "specificity_score": 0.9,
            "structure_score": 0.9, "faithfulness_score": 0.9,
            "is_improvement": False,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score > 0.7
        assert result.is_improvement is True

    @pytest.mark.asyncio
    async def test_neutral_score_trusts_llm_true(self):
        """LLM says improvement=True with neutral score → trust the LLM."""
        provider = _make_provider({
            "clarity_score": 0.5, "specificity_score": 0.5,
            "structure_score": 0.5, "faithfulness_score": 0.5,
            "is_improvement": True,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score == pytest.approx(0.5)
        assert result.is_improvement is True

    @pytest.mark.asyncio
    async def test_neutral_score_trusts_llm_false(self):
        """LLM says improvement=False with neutral score → trust the LLM."""
        provider = _make_provider({
            "clarity_score": 0.5, "specificity_score": 0.5,
            "structure_score": 0.5, "faithfulness_score": 0.5,
            "is_improvement": False,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score == pytest.approx(0.5)
        assert result.is_improvement is False

    @pytest.mark.asyncio
    async def test_boundary_04_not_overridden(self):
        """Score exactly at 0.4 is in neutral zone — LLM value passes through."""
        # Need scores that produce exactly 0.4: e.g. all 0.4
        provider = _make_provider({
            "clarity_score": 0.4, "specificity_score": 0.4,
            "structure_score": 0.4, "faithfulness_score": 0.4,
            "is_improvement": True,
        })
        result = await PromptValidator(provider).validate("a", "b")
        assert result.overall_score == pytest.approx(0.4)
        assert result.is_improvement is True  # 0.4 is NOT < 0.4, so no override
