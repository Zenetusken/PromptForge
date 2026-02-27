"""Integration test for the full pipeline data flow with mocked LLM.

Exercises: Analyzer → StrategySelector → Optimizer → Validator
as a single pipeline run, verifying that data flows correctly
between stages and the final result is consistent.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.constants import Strategy
from app.services.pipeline import PipelineComplete, run_pipeline, run_pipeline_streaming


def _make_mock_provider(
    analysis_response: dict | None = None,
    strategy_response: dict | None = None,
    optimization_response: dict | None = None,
    validation_response: dict | None = None,
    *,
    skip_strategy: bool = False,
):
    """Create a mock LLM provider with canned responses for each stage.

    When skip_strategy=True: 3-call mode (analyzer, optimizer, validator)
    for use with strategy_override which bypasses the LLM strategy call.
    """
    provider = MagicMock()
    provider.model_name = "mock-model"

    default_analysis = {
        "task_type": "coding",
        "complexity": "medium",
        "weaknesses": ["Lacks specific details"],
        "strengths": ["Clear intent"],
    }
    default_strategy = {
        "strategy": "constraint-injection",
        "reasoning": "Addressing specificity weaknesses with explicit constraints.",
        "confidence": 0.85,
    }
    default_optimization = {
        "optimized_prompt": "You are an expert Python developer. Write a function...",
        "framework_applied": "constraint-injection",
        "changes_made": ["Added role definition", "Added constraints"],
        "optimization_notes": "Applied constraint-focused optimization.",
    }
    default_validation = {
        "clarity_score": 0.85,
        "specificity_score": 0.80,
        "structure_score": 0.75,
        "faithfulness_score": 0.90,
        "is_improvement": True,
        "verdict": "Significant improvement in specificity and structure.",
    }

    analysis = analysis_response or default_analysis
    strategy = strategy_response or default_strategy
    optimization = optimization_response or default_optimization
    validation = validation_response or default_validation

    call_count = 0
    if skip_strategy:
        responses = [analysis, optimization, validation]
    else:
        responses = [analysis, strategy, optimization, validation]

    async def mock_complete_json(request):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        response = responses[idx]
        call_count += 1
        completion = MagicMock()
        completion.usage = None
        return response, completion

    provider.complete_json = AsyncMock(side_effect=mock_complete_json)
    return provider


def _make_capturing_provider(
    analysis_response: dict,
    strategy_response: dict | None = None,
    optimization_response: dict | None = None,
    validation_response: dict | None = None,
    *,
    skip_strategy: bool = False,
):
    """Create a mock provider that captures each request for inspection.

    Returns (provider, captured_requests) where captured_requests is a list
    that will be populated with (stage_name, request) tuples as calls happen.

    When skip_strategy=False (default): 4 LLM calls expected
        (analyzer, strategy, optimizer, validator).
    When skip_strategy=True: 3 LLM calls expected
        (analyzer, optimizer, validator) — used with strategy_override.
    """
    provider = MagicMock()
    provider.model_name = "mock-model"
    captured: list[tuple[str, object]] = []

    strat = strategy_response or {
        "strategy": "constraint-injection",
        "reasoning": "Addressing specificity weaknesses.",
        "confidence": 0.85,
    }
    opt = optimization_response or {
        "optimized_prompt": "Optimized.",
        "framework_applied": "test",
        "changes_made": [],
        "optimization_notes": "",
    }
    val = validation_response or {
        "clarity_score": 0.8,
        "specificity_score": 0.8,
        "structure_score": 0.8,
        "faithfulness_score": 0.8,
        "is_improvement": True,
        "verdict": "Good.",
    }

    if skip_strategy:
        stage_names = ["analyzer", "optimizer", "validator"]
        responses = [analysis_response, opt, val]
    else:
        stage_names = ["analyzer", "strategy", "optimizer", "validator"]
        responses = [analysis_response, strat, opt, val]
    call_count = 0

    async def mock_complete_json(request):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        captured.append((stage_names[idx], request))
        response = responses[idx]
        call_count += 1
        completion = MagicMock()
        completion.usage = None
        return response, completion

    provider.complete_json = AsyncMock(side_effect=mock_complete_json)
    return provider, captured


class TestPipelineIntegration:
    """Test full pipeline data flow with mocked LLM."""

    @pytest.mark.asyncio
    async def test_full_pipeline_returns_complete_result(self):
        """run_pipeline should return a PipelineResult with all fields populated."""
        provider = _make_mock_provider()
        result = await run_pipeline("Write a Python function", llm_provider=provider)

        # Analysis fields flow through
        assert result.task_type == "coding"
        assert result.complexity == "medium"
        assert result.weaknesses == ["Lacks specific details"]
        assert result.strengths == ["Clear intent"]

        # Optimization fields flow through
        assert "expert Python developer" in result.optimized_prompt
        assert result.framework_applied == "constraint-injection"
        assert len(result.changes_made) == 2

        # Validation fields flow through
        assert result.clarity_score == 0.85
        assert result.specificity_score == 0.80
        assert result.is_improvement is True

        # Metadata
        assert result.model_used == "mock-model"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_strategy_selection_for_coding_with_weakness(self):
        """Coding task with specificity weakness should select constraint-focused."""
        provider = _make_mock_provider()
        result = await run_pipeline("Write a function", llm_provider=provider)

        # Strategy comes from mock LLM response (default: constraint-focused)
        assert result.strategy == "constraint-injection"

    @pytest.mark.asyncio
    async def test_strategy_override_bypasses_selector(self):
        """Explicit strategy override should bypass the StrategySelector."""
        provider = _make_mock_provider(skip_strategy=True)
        result = await run_pipeline(
            "Write a function",
            llm_provider=provider,
            strategy_override="chain-of-thought",
        )

        assert result.strategy == "chain-of-thought"
        assert result.strategy_confidence == 1.0

    @pytest.mark.asyncio
    async def test_overall_score_is_weighted_average(self):
        """Overall score should be the server-computed weighted average.

        The default mock validation response provides clarity=0.85, specificity=0.80,
        structure=0.75, faithfulness=0.90. conciseness defaults to 0.5 when omitted.
        """
        from app.services.validator import (
            CLARITY_WEIGHT, CONCISENESS_WEIGHT, FAITHFULNESS_WEIGHT,
            SPECIFICITY_WEIGHT, STRUCTURE_WEIGHT,
        )
        provider = _make_mock_provider()
        result = await run_pipeline("Test prompt", llm_provider=provider)

        expected = round(
            0.85 * CLARITY_WEIGHT + 0.80 * SPECIFICITY_WEIGHT
            + 0.75 * STRUCTURE_WEIGHT + 0.90 * FAITHFULNESS_WEIGHT
            + 0.5 * CONCISENESS_WEIGHT, 4
        )
        assert result.overall_score == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_math_task_with_weakness_keeps_chain_of_thought(self):
        """Math task with vague weakness should keep chain-of-thought (Issue 2.1)."""
        provider = _make_mock_provider(
            analysis_response={
                "task_type": "math",
                "complexity": "medium",
                "weaknesses": ["Parameters are vague"],
                "strengths": ["Clear mathematical intent"],
            },
            strategy_response={
                "strategy": "chain-of-thought",
                "reasoning": "Math task benefits from step-by-step reasoning.",
                "confidence": 0.90,
            },
        )
        result = await run_pipeline("Solve this math problem", llm_provider=provider)

        assert result.strategy == "chain-of-thought"

    @pytest.mark.asyncio
    async def test_strategy_confidence_in_result(self):
        """PipelineResult should include strategy_confidence."""
        provider = _make_mock_provider()
        result = await run_pipeline("Test prompt", llm_provider=provider)

        assert hasattr(result, "strategy_confidence")
        assert 0.0 <= result.strategy_confidence <= 1.0


class TestPipelineStreamingIntegration:
    """Test the streaming pipeline variant yields correct SSE events."""

    @pytest.mark.asyncio
    async def test_streaming_yields_strategy_event(self):
        """Streaming pipeline should yield a strategy SSE event."""
        provider = _make_mock_provider()
        events = []
        async for event in run_pipeline_streaming("Test prompt", llm_provider=provider):
            if isinstance(event, str):
                events.append(event)

        # Find the strategy event
        strategy_events = [e for e in events if "event: strategy" in e]
        assert len(strategy_events) == 1
        assert '"confidence"' in strategy_events[0]

    @pytest.mark.asyncio
    async def test_streaming_yields_complete_event_with_confidence(self):
        """Complete SSE event should include strategy_confidence."""
        provider = _make_mock_provider()
        complete_data = None
        async for event in run_pipeline_streaming("Test prompt", llm_provider=provider):
            if isinstance(event, PipelineComplete):
                complete_data = event.data

        assert complete_data is not None
        assert "strategy_confidence" in complete_data
        assert "strategy_reasoning" in complete_data

    @pytest.mark.asyncio
    async def test_streaming_with_strategy_override_skips_strategy_stage(self):
        """Strategy override should emit strategy event without a stage start for strategy."""
        provider = _make_mock_provider(skip_strategy=True)
        events = []
        async for event in run_pipeline_streaming(
            "Test prompt",
            llm_provider=provider,
            strategy_override="chain-of-thought",
        ):
            if isinstance(event, str):
                events.append(event)

        event_text = "".join(events)

        # Strategy event should still be emitted (instant, not streamed)
        strategy_events = [e for e in events if "event: strategy" in e]
        assert len(strategy_events) == 1
        assert '"chain-of-thought"' in strategy_events[0]
        assert '"confidence": 1.0' in strategy_events[0]
        assert '"is_override": true' in strategy_events[0]

        # Should NOT have a strategy stage start (the "strategizing" label)
        stage_events = [e for e in events if "event: stage" in e]
        stage_labels = [e for e in stage_events if '"strategizing"' in e]
        assert len(stage_labels) == 0, "Override should skip the strategy stage start"

        # But should still have analyze, optimize, validate stage starts
        assert any('"analyzing"' in e for e in stage_events)
        assert any('"optimizing"' in e for e in stage_events)
        assert any('"validating"' in e for e in stage_events)

        # Complete event should still be present
        assert "event: complete" in event_text

    @pytest.mark.asyncio
    async def test_streaming_override_with_secondary_frameworks(self):
        """Strategy override with secondary frameworks should include them in complete event."""
        provider = _make_mock_provider(skip_strategy=True)
        complete_data = None
        async for event in run_pipeline_streaming(
            "Test prompt",
            llm_provider=provider,
            strategy_override="risen",
            secondary_frameworks_override=["constraint-injection", "step-by-step"],
        ):
            if isinstance(event, PipelineComplete):
                complete_data = event.data

        assert complete_data is not None
        assert complete_data["strategy"] == "risen"
        assert complete_data["strategy_confidence"] == 1.0
        assert complete_data["secondary_frameworks"] == ["constraint-injection", "step-by-step"]

    @pytest.mark.asyncio
    async def test_streaming_emits_all_stage_events(self):
        """Streaming pipeline should emit stage events for all 4 stages."""
        provider = _make_mock_provider()
        events = []
        async for event in run_pipeline_streaming("Test prompt", llm_provider=provider):
            if isinstance(event, str):
                events.append(event)

        event_text = "".join(events)
        assert "event: stage" in event_text
        assert '"strategizing"' in event_text  # strategy stage label
        assert "event: analysis" in event_text
        assert "event: strategy" in event_text
        assert "event: optimization" in event_text
        assert "event: validation" in event_text
        assert "event: complete" in event_text


# ---------------------------------------------------------------------------
# Strategy propagation — verify the selector's output actually reaches
# the optimizer's LLM request (the wiring, not the LLM behavior).
#
# Pipeline call order: complete_json call 0 = analyzer, 1 = strategy,
# 2 = optimizer, 3 = validator (or 0/1/2 when skip_strategy=True).
# We inspect the "optimizer" capture to confirm it received the expected strategy.
# ---------------------------------------------------------------------------

def _get_optimizer_strategy(captured: list[tuple[str, object]]) -> str:
    """Extract the strategy field from the captured optimizer request."""
    optimizer_calls = [(name, req) for name, req in captured if name == "optimizer"]
    assert len(optimizer_calls) == 1, f"Expected 1 optimizer call, got {len(optimizer_calls)}"
    _, request = optimizer_calls[0]
    parsed = json.loads(request.user_message)
    return parsed["strategy"]


class TestStrategyPropagation:
    """Verify the strategy selected by StrategySelector actually reaches
    the optimizer's LLM request — not just the result metadata."""

    # --- P2: Specificity weakness → constraint-focused reaches optimizer ---

    @pytest.mark.asyncio
    async def test_coding_with_specificity_weakness_sends_constraint_focused(self):
        """coding + specificity weakness → LLM picks constraint-focused → optimizer gets it."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": ["Lacks specific details"], "strengths": ["Clear intent"]},
            strategy_response={"strategy": "constraint-injection",
                               "reasoning": "Addressing specificity.", "confidence": 0.85},
        )
        await run_pipeline("Write a function", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.CONSTRAINT_INJECTION

    @pytest.mark.asyncio
    async def test_vague_weakness_sends_constraint_focused(self):
        """general + vague weakness → constraint-focused in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "general", "complexity": "medium",
             "weaknesses": ["Instructions are vague"], "strengths": []},
            strategy_response={"strategy": "constraint-injection",
                               "reasoning": "Vague needs constraints.", "confidence": 0.80},
        )
        await run_pipeline("Do something", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.CONSTRAINT_INJECTION

    # --- High complexity + CoT-natural → chain-of-thought reaches optimizer ---

    @pytest.mark.asyncio
    async def test_high_complexity_math_sends_chain_of_thought(self):
        """math + high complexity → chain-of-thought in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "math", "complexity": "high",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "chain-of-thought",
                               "reasoning": "Complex math needs steps.", "confidence": 0.95},
        )
        await run_pipeline("Solve this equation", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.CHAIN_OF_THOUGHT

    @pytest.mark.asyncio
    async def test_high_complexity_reasoning_sends_chain_of_thought(self):
        """reasoning + high complexity → chain-of-thought in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "reasoning", "complexity": "high",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "chain-of-thought",
                               "reasoning": "Reasoning needs steps.", "confidence": 0.95},
        )
        await run_pipeline("Reason about this", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.CHAIN_OF_THOUGHT

    @pytest.mark.asyncio
    async def test_high_complexity_analysis_sends_chain_of_thought(self):
        """analysis + high complexity → chain-of-thought in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "analysis", "complexity": "high",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "chain-of-thought",
                               "reasoning": "Analysis needs steps.", "confidence": 0.95},
        )
        await run_pipeline("Analyze this data", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.CHAIN_OF_THOUGHT

    # --- CoT-natural with weakness stays CoT ---

    @pytest.mark.asyncio
    async def test_high_complexity_math_with_weakness_still_sends_cot(self):
        """math + high + vague → chain-of-thought, not constraint-focused."""
        provider, captured = _make_capturing_provider(
            {"task_type": "math", "complexity": "high",
             "weaknesses": ["Parameters are vague"], "strengths": []},
            strategy_response={"strategy": "chain-of-thought",
                               "reasoning": "Math + CoT natural.", "confidence": 0.92},
        )
        await run_pipeline("Solve equation", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.CHAIN_OF_THOUGHT

    # --- CoT-natural at medium complexity + weakness stays CoT ---

    @pytest.mark.asyncio
    async def test_math_with_weakness_exempt_from_constraint_focused(self):
        """math + vague weakness → chain-of-thought, not constraint-focused."""
        provider, captured = _make_capturing_provider(
            {"task_type": "math", "complexity": "medium",
             "weaknesses": ["Lacks specific details"], "strengths": []},
            strategy_response={"strategy": "chain-of-thought",
                               "reasoning": "Math naturally uses CoT.", "confidence": 0.85},
        )
        await run_pipeline("Math problem", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.CHAIN_OF_THOUGHT

    # --- Task-type defaults reach optimizer ---

    @pytest.mark.asyncio
    async def test_classification_sends_few_shot(self):
        """classification → few-shot in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "classification", "complexity": "medium",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "few-shot-scaffolding",
                               "reasoning": "Classification needs examples.", "confidence": 0.80},
        )
        await run_pipeline("Classify this text", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.FEW_SHOT_SCAFFOLDING

    @pytest.mark.asyncio
    async def test_coding_without_weakness_sends_role_based(self):
        """coding + no specificity weakness → role-based in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": ["Could be more concise"], "strengths": []},
            strategy_response={"strategy": "persona-assignment",
                               "reasoning": "Coding benefits from expert role.",
                               "confidence": 0.78},
        )
        await run_pipeline("Write code", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.PERSONA_ASSIGNMENT

    @pytest.mark.asyncio
    async def test_general_task_sends_structured_enhancement(self):
        """general → structured-enhancement in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "general", "complexity": "medium",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "role-task-format",
                               "reasoning": "General task, structural improvements.",
                               "confidence": 0.75},
        )
        await run_pipeline("Help me", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.ROLE_TASK_FORMAT

    @pytest.mark.asyncio
    async def test_writing_sends_role_based(self):
        """writing → role-based in optimizer request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "writing", "complexity": "low",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "persona-assignment",
                               "reasoning": "Writing benefits from persona.", "confidence": 0.78},
        )
        await run_pipeline("Write an essay", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.PERSONA_ASSIGNMENT

    # --- Redundancy: strength matches strategy → structured-enhancement ---

    @pytest.mark.asyncio
    async def test_redundancy_redirects_few_shot_to_structured_enhancement(self):
        """classification + 'has examples' → structured-enhancement."""
        provider, captured = _make_capturing_provider(
            {"task_type": "classification", "complexity": "medium",
             "weaknesses": [], "strengths": ["Includes examples of each category"]},
            strategy_response={"strategy": "role-task-format",
                               "reasoning": "Prompt already has examples.", "confidence": 0.70},
        )
        await run_pipeline("Classify items", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.ROLE_TASK_FORMAT

    @pytest.mark.asyncio
    async def test_redundancy_redirects_role_based_to_structured_enhancement(self):
        """coding + 'clear role definition' → structured-enhancement."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": ["Clear role definition as a senior developer"]},
            strategy_response={"strategy": "role-task-format",
                               "reasoning": "Prompt already defines role.", "confidence": 0.70},
        )
        await run_pipeline("Write a module", llm_provider=provider)
        assert _get_optimizer_strategy(captured) == Strategy.ROLE_TASK_FORMAT

    # --- Strategy override reaches optimizer, bypassing selector ---

    @pytest.mark.asyncio
    async def test_override_chain_of_thought_for_coding_task(self):
        """Override: coding task (normally role-based) gets chain-of-thought in optimizer."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": []},
            skip_strategy=True,
        )
        await run_pipeline(
            "Write code", llm_provider=provider,
            strategy_override="chain-of-thought",
        )
        assert _get_optimizer_strategy(captured) == Strategy.CHAIN_OF_THOUGHT

    @pytest.mark.asyncio
    async def test_override_few_shot_for_general_task(self):
        """Override: general task (normally structured-enhancement) gets few-shot."""
        provider, captured = _make_capturing_provider(
            {"task_type": "general", "complexity": "low",
             "weaknesses": [], "strengths": []},
            skip_strategy=True,
        )
        await run_pipeline(
            "Help me", llm_provider=provider,
            strategy_override="few-shot-scaffolding",
        )
        assert _get_optimizer_strategy(captured) == Strategy.FEW_SHOT_SCAFFOLDING

    @pytest.mark.asyncio
    async def test_override_trumps_specificity_weakness(self):
        """Override: coding + vague weakness (normally constraint-focused) gets role-based."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": ["Instructions are vague"], "strengths": []},
            skip_strategy=True,
        )
        await run_pipeline(
            "Write code", llm_provider=provider,
            strategy_override="persona-assignment",
        )
        assert _get_optimizer_strategy(captured) == Strategy.PERSONA_ASSIGNMENT

    @pytest.mark.asyncio
    async def test_override_trumps_high_complexity_p1(self):
        """Override: math + high (normally P1 chain-of-thought) gets few-shot."""
        provider, captured = _make_capturing_provider(
            {"task_type": "math", "complexity": "high",
             "weaknesses": [], "strengths": []},
            skip_strategy=True,
        )
        await run_pipeline(
            "Solve equation", llm_provider=provider,
            strategy_override="few-shot-scaffolding",
        )
        assert _get_optimizer_strategy(captured) == Strategy.FEW_SHOT_SCAFFOLDING

    # --- Verify optimizer also receives correct analysis data ---

    @pytest.mark.asyncio
    async def test_optimizer_receives_analysis_from_analyzer(self):
        """The optimizer's request should contain the analysis the analyzer produced."""
        provider, captured = _make_capturing_provider(
            {"task_type": "extraction", "complexity": "low",
             "weaknesses": ["Too broad"], "strengths": ["Good format"]},
            strategy_response={"strategy": "few-shot-scaffolding",
                               "reasoning": "Extraction needs examples.", "confidence": 0.80},
        )
        await run_pipeline("Extract data", llm_provider=provider)

        optimizer_calls = [(n, r) for n, r in captured if n == "optimizer"]
        assert len(optimizer_calls) == 1
        parsed = json.loads(optimizer_calls[0][1].user_message)
        assert parsed["analysis"]["task_type"] == "extraction"
        assert parsed["analysis"]["complexity"] == "low"
        assert parsed["analysis"]["weaknesses"] == ["Too broad"]
        assert parsed["analysis"]["strengths"] == ["Good format"]

    # --- Verify strategy in result metadata matches what optimizer received ---

    @pytest.mark.asyncio
    async def test_result_strategy_matches_optimizer_input(self):
        """The strategy in PipelineResult.strategy must match
        what the optimizer actually received in its request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "classification", "complexity": "medium",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "few-shot-scaffolding",
                               "reasoning": "Classification needs examples.", "confidence": 0.80},
        )
        result = await run_pipeline("Classify items", llm_provider=provider)
        optimizer_strategy = _get_optimizer_strategy(captured)
        assert result.strategy == optimizer_strategy


# ---------------------------------------------------------------------------
# Strategy passed to validator — verify validator receives the strategy name
# ---------------------------------------------------------------------------

class TestStrategyPassedToValidator:
    """Verify the selected strategy is forwarded to the validator for
    framework_adherence_score evaluation."""

    @pytest.mark.asyncio
    async def test_validator_receives_strategy_in_payload(self):
        """Validator's LLM request should contain strategy from selector."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": []},
            strategy_response={"strategy": "co-star",
                               "reasoning": "Testing.", "confidence": 0.80},
        )
        await run_pipeline("Write a function", llm_provider=provider)

        validator_calls = [(n, r) for n, r in captured if n == "validator"]
        assert len(validator_calls) == 1
        parsed = json.loads(validator_calls[0][1].user_message)
        assert parsed["strategy"] == "co-star"

    @pytest.mark.asyncio
    async def test_override_strategy_reaches_validator(self):
        """Strategy override also passes through to the validator."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": []},
            skip_strategy=True,
        )
        await run_pipeline(
            "Write a function", llm_provider=provider,
            strategy_override="risen",
        )

        validator_calls = [(n, r) for n, r in captured if n == "validator"]
        assert len(validator_calls) == 1
        parsed = json.loads(validator_calls[0][1].user_message)
        assert parsed["strategy"] == "risen"

    @pytest.mark.asyncio
    async def test_framework_adherence_in_pipeline_result(self):
        """PipelineResult includes framework_adherence_score from validator."""
        provider = _make_mock_provider(
            validation_response={
                "clarity_score": 0.85, "specificity_score": 0.80,
                "structure_score": 0.75, "faithfulness_score": 0.90,
                "framework_adherence_score": 0.82,
                "is_improvement": True,
                "verdict": "Good.",
            },
        )
        result = await run_pipeline("Test prompt", llm_provider=provider)
        assert result.framework_adherence_score == 0.82

    @pytest.mark.asyncio
    async def test_streaming_complete_includes_framework_adherence(self):
        """Streaming complete event includes framework_adherence_score."""
        provider = _make_mock_provider(
            validation_response={
                "clarity_score": 0.85, "specificity_score": 0.80,
                "structure_score": 0.75, "faithfulness_score": 0.90,
                "framework_adherence_score": 0.65,
                "is_improvement": True,
                "verdict": "Good.",
            },
        )
        complete_data = None
        async for event in run_pipeline_streaming("Test prompt", llm_provider=provider):
            if isinstance(event, PipelineComplete):
                complete_data = event.data
        assert complete_data is not None
        assert complete_data["framework_adherence_score"] == 0.65


# ---------------------------------------------------------------------------
# Codebase context threading — verify context reaches all pipeline stages
# ---------------------------------------------------------------------------

class TestCodebaseContextThreading:
    """Verify codebase_context is threaded through all 4 pipeline stages."""

    @pytest.mark.asyncio
    async def test_context_reaches_all_stages_via_run_pipeline(self):
        """When codebase_context is provided, all 4 stages should see it in their request."""
        from app.schemas.context import CodebaseContext

        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": []},
        )
        ctx = CodebaseContext(language="Python 3.14", framework="FastAPI")
        await run_pipeline(
            "Write a function",
            llm_provider=provider,
            codebase_context=ctx,
        )

        # All 4 stages should have received the context
        assert len(captured) == 4
        for stage_name, request in captured:
            msg = request.user_message
            # Analyzer uses plain text injection; others use JSON payload
            if stage_name == "analyzer":
                assert "Python 3.14" in msg, f"{stage_name} missing context"
            else:
                parsed = json.loads(msg)
                assert "codebase_context" in parsed, f"{stage_name} missing context field"
                assert "Python 3.14" in parsed["codebase_context"]

    @pytest.mark.asyncio
    async def test_no_context_means_no_injection(self):
        """Without codebase_context, no stage should have context in the request."""
        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": []},
        )
        await run_pipeline("Write a function", llm_provider=provider)

        assert len(captured) == 4
        for stage_name, request in captured:
            msg = request.user_message
            if stage_name == "analyzer":
                assert "codebase environment" not in msg
            else:
                parsed = json.loads(msg)
                assert "codebase_context" not in parsed

    @pytest.mark.asyncio
    async def test_context_reaches_stages_via_streaming_pipeline(self):
        """Streaming pipeline should also thread context through all stages."""
        from app.schemas.context import CodebaseContext

        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": []},
        )
        ctx = CodebaseContext(language="Rust", framework="Axum")

        events = []
        async for event in run_pipeline_streaming(
            "Write a handler",
            llm_provider=provider,
            codebase_context=ctx,
        ):
            if isinstance(event, str):
                events.append(event)

        # All 4 stages should have received the context
        assert len(captured) == 4
        for stage_name, request in captured:
            msg = request.user_message
            if stage_name == "analyzer":
                assert "Rust" in msg, f"streaming {stage_name} missing context"
            else:
                parsed = json.loads(msg)
                assert "codebase_context" in parsed, f"streaming {stage_name} missing context"

    @pytest.mark.asyncio
    async def test_context_with_strategy_override(self):
        """Context should thread through even when strategy_override bypasses the selector."""
        from app.schemas.context import CodebaseContext

        provider, captured = _make_capturing_provider(
            {"task_type": "coding", "complexity": "medium",
             "weaknesses": [], "strengths": []},
            skip_strategy=True,
        )
        ctx = CodebaseContext(language="Go", patterns=["clean architecture"])
        await run_pipeline(
            "Write a handler",
            llm_provider=provider,
            strategy_override="chain-of-thought",
            codebase_context=ctx,
        )

        # 3 stages (strategy skipped): analyzer, optimizer, validator
        assert len(captured) == 3
        for stage_name, request in captured:
            msg = request.user_message
            if stage_name == "analyzer":
                assert "Go" in msg
            else:
                parsed = json.loads(msg)
                assert "codebase_context" in parsed
