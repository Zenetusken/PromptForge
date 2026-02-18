"""Tests for error propagation through the optimization pipeline.

Verifies that exceptions raised by individual services (analyzer, optimizer,
validator) propagate correctly through both the sync and streaming pipelines.

Pipeline LLM call order: 1=analyzer, 2=strategy, 3=optimizer, 4=validator.
Note: strategy errors (call 2) are caught by the heuristic fallback and
do NOT propagate — this is intentional.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.errors import ProviderError, RateLimitError
from app.services.pipeline import run_pipeline, run_pipeline_streaming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_error_provider(
    error_on_call: int = 1,
    error: Exception | None = None,
):
    """Create a mock provider that raises on the Nth complete_json call.

    Calls before and after error_on_call return valid stage responses.
    Pipeline call order: 1=analyzer, 2=strategy, 3=optimizer, 4=validator.
    """
    if error is None:
        error = RuntimeError("LLM failed")

    responses = [
        # Call 1: Analyzer
        {
            "task_type": "coding", "complexity": "medium",
            "weaknesses": [], "strengths": [],
        },
        # Call 2: Strategy
        {
            "strategy": "persona-assignment",
            "reasoning": "Coding benefits from expert role.",
            "confidence": 0.78,
        },
        # Call 3: Optimizer
        {
            "optimized_prompt": "Better prompt",
            "framework_applied": "persona-assignment",
            "changes_made": [], "optimization_notes": "",
        },
        # Call 4: Validator
        {
            "clarity_score": 0.8, "specificity_score": 0.7,
            "structure_score": 0.6, "faithfulness_score": 0.9,
            "overall_score": 0.75, "is_improvement": True, "verdict": "Good",
        },
    ]

    call_count = 0
    provider = MagicMock()
    provider.model_name = "test-model"

    async def _complete_json(request):
        nonlocal call_count
        call_count += 1
        if call_count == error_on_call:
            raise error
        idx = min(call_count - 1, len(responses) - 1)
        completion = MagicMock()
        completion.usage = None
        return responses[idx], completion

    provider.complete_json = AsyncMock(side_effect=_complete_json)
    return provider


# ---------------------------------------------------------------------------
# TestSyncPipelineErrorPropagation
# ---------------------------------------------------------------------------

class TestSyncPipelineErrorPropagation:
    @pytest.mark.asyncio
    async def test_analyzer_error_propagates(self):
        """When the analyzer fails (call 1), run_pipeline raises."""
        provider = _make_error_provider(error_on_call=1)
        with pytest.raises(RuntimeError, match="LLM failed"):
            await run_pipeline("test prompt", llm_provider=provider)

    @pytest.mark.asyncio
    async def test_strategy_error_falls_back_silently(self):
        """When strategy fails (call 2), heuristic fallback kicks in — no error."""
        provider = _make_error_provider(error_on_call=2)
        # Should NOT raise — strategy fallback catches the error
        result = await run_pipeline("test prompt", llm_provider=provider)
        assert result.strategy  # heuristic still selected a strategy

    @pytest.mark.asyncio
    async def test_optimizer_error_propagates(self):
        """When the optimizer fails (call 3), run_pipeline raises."""
        provider = _make_error_provider(error_on_call=3)
        with pytest.raises(RuntimeError, match="LLM failed"):
            await run_pipeline("test prompt", llm_provider=provider)

    @pytest.mark.asyncio
    async def test_validator_error_propagates(self):
        """When the validator fails (call 4), run_pipeline raises."""
        provider = _make_error_provider(error_on_call=4)
        with pytest.raises(RuntimeError, match="LLM failed"):
            await run_pipeline("test prompt", llm_provider=provider)

    @pytest.mark.asyncio
    async def test_rate_limit_error_propagates(self):
        """Provider-specific errors propagate through the pipeline."""
        provider = _make_error_provider(
            error_on_call=1,
            error=RateLimitError("Rate limit exceeded", provider="test"),
        )
        with pytest.raises(RateLimitError):
            await run_pipeline("test prompt", llm_provider=provider)

    @pytest.mark.asyncio
    async def test_provider_error_propagates(self):
        """Generic ProviderError propagates through the pipeline (optimizer)."""
        provider = _make_error_provider(
            error_on_call=3,
            error=ProviderError("Something broke", provider="test"),
        )
        with pytest.raises(ProviderError):
            await run_pipeline("test prompt", llm_provider=provider)


# ---------------------------------------------------------------------------
# TestStreamingPipelineErrorPropagation
# ---------------------------------------------------------------------------

class TestStreamingPipelineErrorPropagation:
    @pytest.mark.asyncio
    async def test_analyzer_error_in_stream(self):
        """Error during analyzer stage propagates from the async generator."""
        provider = _make_error_provider(error_on_call=1)
        with pytest.raises(RuntimeError, match="LLM failed"):
            async for _ in run_pipeline_streaming("test", llm_provider=provider):
                pass

    @pytest.mark.asyncio
    async def test_optimizer_error_in_stream(self):
        """Error during optimizer stage (call 3) propagates from the async generator."""
        provider = _make_error_provider(error_on_call=3)
        with pytest.raises(RuntimeError, match="LLM failed"):
            async for _ in run_pipeline_streaming("test", llm_provider=provider):
                pass
