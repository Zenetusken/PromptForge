"""Tests for the PromptAnalyzer service — _ensure_string_list, task-type
validation, complexity validation, response parsing defaults, and usage tracking."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.prompts.analyzer_prompt import ANALYZER_SYSTEM_PROMPT
from app.providers.types import TokenUsage
from app.services.analyzer import (
    _VALID_COMPLEXITIES,
    _VALID_TASK_TYPES,
    PromptAnalyzer,
    _ensure_string_list,
)

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


# ---------------------------------------------------------------------------
# TestEnsureStringList
# ---------------------------------------------------------------------------

class TestEnsureStringList:
    def test_none_returns_empty_list(self):
        assert _ensure_string_list(None) == []

    def test_empty_list_returns_empty_list(self):
        assert _ensure_string_list([]) == []

    def test_strings_pass_through(self):
        assert _ensure_string_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_int_float_coerced_to_strings(self):
        assert _ensure_string_list([1, 2.5]) == ["1", "2.5"]

    def test_none_items_filtered(self):
        assert _ensure_string_list(["a", None, "b"]) == ["a", "b"]

    def test_empty_strings_filtered(self):
        assert _ensure_string_list(["a", "", "  ", "b"]) == ["a", "b"]

    def test_mixed_types(self):
        result = _ensure_string_list(["valid", 42, None, "", 3.14, "  ", "ok"])
        assert result == ["valid", "42", "3.14", "ok"]

    def test_bool_items_coerced(self):
        result = _ensure_string_list([True, False])
        assert result == ["True", "False"]


# ---------------------------------------------------------------------------
# TestAnalyzerTaskTypeValidation
# ---------------------------------------------------------------------------

class TestAnalyzerTaskTypeValidation:
    @pytest.mark.asyncio
    async def test_valid_task_type_passes_through(self):
        provider = _make_provider({"task_type": "coding"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "coding"

    @pytest.mark.asyncio
    async def test_unknown_defaults_to_general(self):
        provider = _make_provider({"task_type": "alien_language"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "general"

    @pytest.mark.asyncio
    async def test_uppercase_lowered(self):
        provider = _make_provider({"task_type": "CODING"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "coding"

    @pytest.mark.asyncio
    async def test_whitespace_stripped(self):
        provider = _make_provider({"task_type": "  coding  "})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "coding"

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_general(self):
        provider = _make_provider({})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "general"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("task_type", sorted(_VALID_TASK_TYPES))
    async def test_all_valid_task_types_accepted(self, task_type):
        provider = _make_provider({"task_type": task_type})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == task_type


# ---------------------------------------------------------------------------
# TestAnalyzerComplexityValidation
# ---------------------------------------------------------------------------

class TestAnalyzerComplexityValidation:
    @pytest.mark.asyncio
    async def test_valid_complexity_passes_through(self):
        provider = _make_provider({"complexity": "high"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.complexity == "high"

    @pytest.mark.asyncio
    async def test_unknown_defaults_to_medium(self):
        provider = _make_provider({"complexity": "extreme"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.complexity == "medium"

    @pytest.mark.asyncio
    async def test_uppercase_lowered(self):
        provider = _make_provider({"complexity": "HIGH"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.complexity == "high"

    @pytest.mark.asyncio
    async def test_whitespace_stripped(self):
        provider = _make_provider({"complexity": "  low  "})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.complexity == "low"

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_medium(self):
        provider = _make_provider({})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.complexity == "medium"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("complexity", sorted(_VALID_COMPLEXITIES))
    async def test_all_valid_complexities_accepted(self, complexity):
        provider = _make_provider({"complexity": complexity})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.complexity == complexity


# ---------------------------------------------------------------------------
# TestAnalyzerResponseParsing
# ---------------------------------------------------------------------------

class TestAnalyzerResponseParsing:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        provider = _make_provider({
            "task_type": "coding",
            "complexity": "high",
            "weaknesses": ["vague", "no examples"],
            "strengths": ["clear intent"],
        })
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "coding"
        assert result.complexity == "high"
        assert result.weaknesses == ["vague", "no examples"]
        assert result.strengths == ["clear intent"]

    @pytest.mark.asyncio
    async def test_missing_weaknesses_defaults_to_empty(self):
        provider = _make_provider({"task_type": "coding"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.weaknesses == []

    @pytest.mark.asyncio
    async def test_missing_strengths_defaults_to_empty(self):
        provider = _make_provider({"task_type": "coding"})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.strengths == []

    @pytest.mark.asyncio
    async def test_empty_response_all_defaults(self):
        provider = _make_provider({})
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "general"
        assert result.complexity == "medium"
        assert result.weaknesses == []
        assert result.strengths == []

    @pytest.mark.asyncio
    async def test_extra_keys_ignored(self):
        provider = _make_provider({
            "task_type": "coding", "bonus": True, "extra": [1, 2, 3],
        })
        result = await PromptAnalyzer(provider).analyze("test")
        assert result.task_type == "coding"
        assert not hasattr(result, "bonus")


# ---------------------------------------------------------------------------
# TestAnalyzerUsageAndRequest
# ---------------------------------------------------------------------------

class TestAnalyzerUsageAndRequest:
    @pytest.mark.asyncio
    async def test_last_usage_set(self):
        usage = TokenUsage(input_tokens=200, output_tokens=100)
        provider = _make_provider({}, usage=usage)
        analyzer = PromptAnalyzer(provider)
        await analyzer.analyze("test")
        assert analyzer.last_usage is usage

    @pytest.mark.asyncio
    async def test_last_usage_none(self):
        provider = _make_provider({}, usage=None)
        analyzer = PromptAnalyzer(provider)
        await analyzer.analyze("test")
        assert analyzer.last_usage is None

    @pytest.mark.asyncio
    async def test_system_prompt_is_analyzer_prompt(self):
        provider = _make_provider({})
        await PromptAnalyzer(provider).analyze("test")
        call_args = provider.complete_json.call_args[0][0]
        assert call_args.system_prompt == ANALYZER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_user_message_contains_raw_prompt(self):
        provider = _make_provider({})
        await PromptAnalyzer(provider).analyze("my special prompt")
        call_args = provider.complete_json.call_args[0][0]
        assert "my special prompt" in call_args.user_message
