"""Main optimization pipeline - orchestrates analysis, strategy selection, optimization, and validation."""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import AsyncIterator

from app.constants import (
    STAGE_ANALYZE,
    STAGE_OPTIMIZE,
    STAGE_STRATEGY,
    STAGE_VALIDATE,
    OptimizationStatus,
    StageConfig,
    Strategy,
    compute_progress,
)
from app.providers import LLMProvider, get_provider
from app.providers.types import TokenUsage
from app.services.analyzer import AnalysisResult, PromptAnalyzer
from app.services.optimizer import OptimizationResult, PromptOptimizer
from app.services.strategy_selector import StrategySelection, StrategySelector
from app.services.validator import PromptValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """Typed sentinel yielded by streaming helpers to pass stage results."""

    value: object


@dataclass
class PipelineComplete:
    """Yielded after the final SSE event for structured pipeline data capture."""

    data: dict


@dataclass
class PipelineResult:
    """Complete result from running the optimization pipeline."""

    # Analysis
    task_type: str
    complexity: str
    weaknesses: list[str]
    strengths: list[str]

    # Optimization
    optimized_prompt: str
    framework_applied: str
    changes_made: list[str]
    optimization_notes: str

    # Validation
    clarity_score: float
    specificity_score: float
    structure_score: float
    faithfulness_score: float
    overall_score: float
    is_improvement: bool
    verdict: str

    # Metadata
    duration_ms: int
    model_used: str
    strategy: str = ""
    strategy_reasoning: str = ""
    strategy_confidence: float = 0.75
    secondary_frameworks: list[str] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None


async def _select_strategy(
    analysis: AnalysisResult,
    strategy_override: str | None,
    raw_prompt: str = "",
    prompt_length: int = 0,
    llm_provider: LLMProvider | None = None,
    secondary_frameworks_override: list[str] | None = None,
) -> tuple[StrategySelection, TokenUsage | None]:
    """Select a strategy — either from an explicit override or the LLM selector."""
    if strategy_override:
        # Validate the override is a known Strategy value.
        try:
            validated = Strategy(strategy_override)
        except ValueError:
            valid = ", ".join(sorted(s.value for s in Strategy))
            raise ValueError(f"Unknown strategy {strategy_override!r}. Valid: {valid}")
        return StrategySelection(
            strategy=validated,
            reasoning=f"User-specified strategy override: {validated}",
            confidence=1.0,
            task_type=analysis.task_type,
            is_override=True,
            secondary_frameworks=secondary_frameworks_override or [],
        ), None
    selector = StrategySelector(llm_provider)
    result = await selector.select(analysis, raw_prompt=raw_prompt, prompt_length=prompt_length)
    return result, selector.last_usage


def _add_usage(a: TokenUsage | None, b: TokenUsage | None) -> TokenUsage | None:
    """Sum two TokenUsage values, treating None as zero."""
    if a is None:
        return b
    if b is None:
        return a
    return TokenUsage(
        input_tokens=(a.input_tokens or 0) + (b.input_tokens or 0),
        output_tokens=(a.output_tokens or 0) + (b.output_tokens or 0),
    )


def _assemble_result(
    analysis: AnalysisResult,
    strategy: StrategySelection,
    optimization: OptimizationResult,
    validation: ValidationResult,
    elapsed_ms: int,
    model: str,
    total_usage: TokenUsage | None = None,
) -> PipelineResult:
    """Build a PipelineResult from the individual stage results."""
    return PipelineResult(
        task_type=analysis.task_type,
        complexity=analysis.complexity,
        weaknesses=analysis.weaknesses,
        strengths=analysis.strengths,
        optimized_prompt=optimization.optimized_prompt,
        framework_applied=optimization.framework_applied,
        changes_made=optimization.changes_made,
        optimization_notes=optimization.optimization_notes,
        clarity_score=validation.clarity_score,
        specificity_score=validation.specificity_score,
        structure_score=validation.structure_score,
        faithfulness_score=validation.faithfulness_score,
        overall_score=validation.overall_score,
        is_improvement=validation.is_improvement,
        verdict=validation.verdict,
        duration_ms=elapsed_ms,
        model_used=model,
        strategy=strategy.strategy,
        strategy_reasoning=strategy.reasoning,
        strategy_confidence=strategy.confidence,
        secondary_frameworks=strategy.secondary_frameworks,
        input_tokens=total_usage.input_tokens if total_usage else None,
        output_tokens=total_usage.output_tokens if total_usage else None,
    )


async def run_pipeline(
    raw_prompt: str,
    llm_provider: LLMProvider | None = None,
    strategy_override: str | None = None,
    secondary_frameworks_override: list[str] | None = None,
) -> PipelineResult:
    """Run the full optimization pipeline: analyze, select strategy, optimize, validate."""
    start_time = time.time()
    client = llm_provider or get_provider()
    total_usage: TokenUsage | None = None

    analyzer = PromptAnalyzer(client)
    analysis = await analyzer.analyze(raw_prompt)
    total_usage = _add_usage(total_usage, analyzer.last_usage)
    logger.info(
        "Analysis: task_type=%s complexity=%s weaknesses=%s strengths=%s",
        analysis.task_type, analysis.complexity, analysis.weaknesses, analysis.strengths,
    )

    strategy_selection, strategy_usage = await _select_strategy(
        analysis, strategy_override,
        raw_prompt=raw_prompt, prompt_length=len(raw_prompt), llm_provider=client,
        secondary_frameworks_override=secondary_frameworks_override,
    )
    total_usage = _add_usage(total_usage, strategy_usage)
    logger.info(
        "Strategy: %s confidence=%.2f reasoning=%s",
        strategy_selection.strategy, strategy_selection.confidence, strategy_selection.reasoning,
    )

    optimizer = PromptOptimizer(client)
    optimization = await optimizer.optimize(
        raw_prompt, analysis, strategy_selection.strategy,
        secondary_frameworks=strategy_selection.secondary_frameworks or None,
    )
    total_usage = _add_usage(total_usage, optimizer.last_usage)

    validator = PromptValidator(client)
    validation = await validator.validate(raw_prompt, optimization.optimized_prompt)
    total_usage = _add_usage(total_usage, validator.last_usage)

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Pipeline complete: duration_ms=%d model=%s overall_score=%.2f",
        elapsed_ms, client.model_name, validation.overall_score,
    )
    return _assemble_result(
        analysis, strategy_selection,
        optimization, validation, elapsed_ms, client.model_name,
        total_usage,
    )


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

def _sse_event(event_type: str, data: dict) -> str:
    """Format data as a Server-Sent Event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _run_with_progress_stream(
    coro,
    stage: StageConfig,
    fmt: dict[str, str] | None = None,
) -> AsyncIterator[str | StageResult]:
    """Run a coroutine while yielding periodic progress events.

    Yields SSE progress event strings, then a StageResult sentinel.
    """
    task = asyncio.create_task(coro)
    msg_index = 0
    interval = stage.progress_interval
    messages = stage.progress_messages

    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=interval)
            break
        except asyncio.TimeoutError:
            if messages:
                # Cycle back to the start of the message list after exhausting
                # all messages, so long LLM calls never go silent.
                cycled_index = msg_index % len(messages)
                yield _sse_event("step_progress", {
                    "step": stage.name,
                    "content": messages[cycled_index].format_map(fmt or {}),
                    "progress": compute_progress(msg_index),
                })
                msg_index += 1
        except asyncio.CancelledError:
            break

    result = await task
    yield StageResult(value=result)


async def _stream_stage(
    coro,
    stage: StageConfig,
    fmt: dict[str, str] | None = None,
) -> AsyncIterator[str | StageResult]:
    """Stream a full pipeline stage: start, progress, run with progress, complete.

    Yields SSE strings for the stage lifecycle, then a StageResult sentinel
    so the caller can capture the stage result.
    """
    step_start = time.time()

    # Stage-start event
    yield _sse_event("stage", {
        "stage": stage.stage_label,
        "message": stage.stage_message.format_map(fmt or {}),
    })

    # Initial progress messages (emitted before the LLM call starts)
    for content, progress in stage.initial_messages:
        yield _sse_event("step_progress", {
            "step": stage.name,
            "content": content.format_map(fmt or {}),
            "progress": progress,
        })

    # Run the coroutine with periodic progress
    result = None
    async for event in _run_with_progress_stream(coro, stage, fmt):
        if isinstance(event, StageResult):
            result = event.value
        else:
            yield event

    # Stage-complete event
    step_duration = int((time.time() - step_start) * 1000)
    result_dict = asdict(result)
    result_dict["step_duration_ms"] = step_duration
    yield _sse_event(stage.event_name, result_dict)

    yield StageResult(value=result)


# ---------------------------------------------------------------------------
# Main streaming entry point
# ---------------------------------------------------------------------------

async def run_pipeline_streaming(
    raw_prompt: str,
    llm_provider: LLMProvider | None = None,
    complete_metadata: dict | None = None,
    strategy_override: str | None = None,
    secondary_frameworks_override: list[str] | None = None,
) -> AsyncIterator[str | PipelineComplete]:
    """Run the pipeline and yield SSE events for each stage.

    Args:
        raw_prompt: The original prompt text to optimize.
        llm_provider: Optional LLMProvider instance.
        complete_metadata: Extra fields to inject into the 'complete' SSE event
                           (e.g. id, title, project, tags).
        strategy_override: When set, skip StrategySelector and use this strategy.
        secondary_frameworks_override: When set with strategy_override, these
            secondary frameworks are passed to the optimizer.

    Yields:
        SSE-formatted strings for each pipeline stage, then a PipelineComplete
        with the final result data.
    """
    pipeline_start = time.time()
    client = llm_provider or get_provider()
    total_usage: TokenUsage | None = None

    # Stage 1: Analyze
    analyzer = PromptAnalyzer(client)
    analysis = None
    async for event in _stream_stage(analyzer.analyze(raw_prompt), STAGE_ANALYZE):
        if isinstance(event, StageResult):
            analysis = event.value
        else:
            yield event
    if analysis is None:
        raise RuntimeError("Analyze stage completed without returning a result")
    total_usage = _add_usage(total_usage, analyzer.last_usage)
    logger.info(
        "Analysis: task_type=%s complexity=%s weaknesses=%s strengths=%s",
        analysis.task_type, analysis.complexity, analysis.weaknesses, analysis.strengths,
    )

    # Stage 2: Strategy Selection
    strategy = None
    if strategy_override:
        # Override path: instant, no streaming needed
        strategy_selection, _ = await _select_strategy(
            analysis, strategy_override,
            raw_prompt=raw_prompt, prompt_length=len(raw_prompt), llm_provider=client,
            secondary_frameworks_override=secondary_frameworks_override,
        )
        strategy = strategy_selection
        yield _sse_event("strategy", asdict(strategy))
    else:
        # LLM path: stream with progress like other stages
        selector = StrategySelector(client)
        async for event in _stream_stage(
            selector.select(analysis, raw_prompt=raw_prompt, prompt_length=len(raw_prompt)),
            STAGE_STRATEGY,
        ):
            if isinstance(event, StageResult):
                strategy = event.value
            else:
                yield event
        if strategy is None:
            raise RuntimeError("Strategy stage completed without returning a result")
        total_usage = _add_usage(total_usage, selector.last_usage)

    logger.info(
        "Strategy: %s confidence=%.2f reasoning=%s",
        strategy.strategy, strategy.confidence, strategy.reasoning,
    )
    fmt = {"strategy": strategy.strategy}

    # Stage 3: Optimize
    optimizer = PromptOptimizer(client)
    optimization = None
    async for event in _stream_stage(
        optimizer.optimize(
            raw_prompt, analysis, strategy.strategy,
            secondary_frameworks=strategy.secondary_frameworks or None,
        ),
        STAGE_OPTIMIZE,
        fmt,
    ):
        if isinstance(event, StageResult):
            optimization = event.value
        else:
            yield event
    if optimization is None:
        raise RuntimeError("Optimize stage completed without returning a result")
    total_usage = _add_usage(total_usage, optimizer.last_usage)

    # Stage 4: Validate
    validator = PromptValidator(client)
    validation = None
    async for event in _stream_stage(
        validator.validate(raw_prompt, optimization.optimized_prompt),
        STAGE_VALIDATE,
    ):
        if isinstance(event, StageResult):
            validation = event.value
        else:
            yield event
    if validation is None:
        raise RuntimeError("Validate stage completed without returning a result")
    total_usage = _add_usage(total_usage, validator.last_usage)

    # Complete
    elapsed_ms = int((time.time() - pipeline_start) * 1000)
    logger.info(
        "Pipeline complete: duration_ms=%d model=%s overall_score=%.2f",
        elapsed_ms, client.model_name, validation.overall_score,
    )
    complete_data: dict[str, object] = {
        # Analysis fields
        "task_type": analysis.task_type,
        "complexity": analysis.complexity,
        "weaknesses": analysis.weaknesses,
        "strengths": analysis.strengths,
        # Optimization fields
        "optimized_prompt": optimization.optimized_prompt,
        "framework_applied": optimization.framework_applied,
        "changes_made": optimization.changes_made,
        "optimization_notes": optimization.optimization_notes,
        # Validation fields
        "clarity_score": validation.clarity_score,
        "specificity_score": validation.specificity_score,
        "structure_score": validation.structure_score,
        "faithfulness_score": validation.faithfulness_score,
        "overall_score": validation.overall_score,
        "is_improvement": validation.is_improvement,
        "verdict": validation.verdict,
        # Metadata
        "duration_ms": elapsed_ms,
        "model_used": client.model_name,
        "strategy": strategy.strategy,
        "strategy_reasoning": strategy.reasoning,
        "strategy_confidence": strategy.confidence,
        "secondary_frameworks": strategy.secondary_frameworks,
        "status": OptimizationStatus.COMPLETED,
    }
    if total_usage:
        complete_data["input_tokens"] = total_usage.input_tokens
        complete_data["output_tokens"] = total_usage.output_tokens
    if complete_metadata:
        complete_data.update(complete_metadata)
    yield _sse_event("complete", complete_data)
    yield PipelineComplete(data=complete_data)
