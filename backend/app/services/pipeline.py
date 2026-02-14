"""Main optimization pipeline - orchestrates analysis, optimization, and validation."""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from typing import AsyncIterator

from app.constants import (
    STAGE_ANALYZE,
    STAGE_OPTIMIZE,
    STAGE_VALIDATE,
    OptimizationStatus,
    StageConfig,
    compute_progress,
)
from app.services.analyzer import AnalysisResult, PromptAnalyzer
from app.services.claude_client import ClaudeClient
from app.services.optimizer import OptimizationResult, PromptOptimizer
from app.services.strategy_selector import StrategySelector
from app.services.validator import PromptValidator, ValidationResult


@dataclass
class StageResult:
    """Typed sentinel yielded by streaming helpers to pass stage results."""

    value: object


@dataclass
class PipelineComplete:
    """Yielded after the final SSE event so callers can capture pipeline data without re-parsing SSE."""

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
    strategy_reasoning: str


def _assemble_result(
    analysis: AnalysisResult,
    strategy_reasoning: str,
    optimization: OptimizationResult,
    validation: ValidationResult,
    elapsed_ms: int,
    model: str,
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
        strategy_reasoning=strategy_reasoning,
    )


async def run_pipeline(
    raw_prompt: str,
    claude_client: ClaudeClient | None = None,
) -> PipelineResult:
    """Run the full optimization pipeline: analyze, select strategy, optimize, validate."""
    start_time = time.time()
    client = claude_client or ClaudeClient()

    analyzer = PromptAnalyzer(client)
    analysis = await analyzer.analyze(raw_prompt)

    selector = StrategySelector()
    strategy_selection = selector.select(analysis)

    optimizer = PromptOptimizer(client)
    optimization = await optimizer.optimize(raw_prompt, analysis, strategy_selection.strategy)

    validator = PromptValidator(client)
    validation = await validator.validate(raw_prompt, optimization.optimized_prompt)

    elapsed_ms = int((time.time() - start_time) * 1000)
    return _assemble_result(analysis, strategy_selection.reasoning, optimization, validation, elapsed_ms, client.model)


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
            if msg_index < len(messages):
                yield _sse_event("step_progress", {
                    "step": stage.name,
                    "content": messages[msg_index].format_map(fmt or {}),
                    "progress": compute_progress(msg_index),
                })
                msg_index += 1
        except Exception:
            break

    result = await task
    yield StageResult(value=result)


async def _stream_stage(
    coro,
    stage: StageConfig,
    fmt: dict[str, str] | None = None,
) -> AsyncIterator[str | StageResult]:
    """Stream a full pipeline stage: start event, initial progress, run with progress, complete event.

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
    claude_client: ClaudeClient | None = None,
    complete_metadata: dict | None = None,
) -> AsyncIterator[str | PipelineComplete]:
    """Run the pipeline and yield SSE events for each stage.

    Args:
        raw_prompt: The original prompt text to optimize.
        claude_client: Optional ClaudeClient instance.
        complete_metadata: Extra fields to inject into the 'complete' SSE event
                           (e.g. id, title, project, tags).

    Yields:
        SSE-formatted strings for each pipeline stage, then a PipelineComplete
        with the final result data.
    """
    pipeline_start = time.time()
    client = claude_client or ClaudeClient()

    # Stage 1: Analyze
    analyzer = PromptAnalyzer(client)
    analysis = None
    async for event in _stream_stage(analyzer.analyze(raw_prompt), STAGE_ANALYZE):
        if isinstance(event, StageResult):
            analysis = event.value
        else:
            yield event

    # Stage 2: Strategy Selection (sync, no streaming)
    selector = StrategySelector()
    strategy = selector.select(analysis)
    fmt = {"strategy": strategy.strategy}

    # Stage 3: Optimize
    optimizer = PromptOptimizer(client)
    optimization = None
    async for event in _stream_stage(
        optimizer.optimize(raw_prompt, analysis, strategy.strategy),
        STAGE_OPTIMIZE,
        fmt,
    ):
        if isinstance(event, StageResult):
            optimization = event.value
        else:
            yield event

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

    # Complete
    elapsed_ms = int((time.time() - pipeline_start) * 1000)
    complete_data = {
        **asdict(analysis),
        **asdict(optimization),
        **asdict(validation),
        "duration_ms": elapsed_ms,
        "model_used": client.model,
        "strategy_reasoning": strategy.reasoning,
        "status": OptimizationStatus.COMPLETED,
    }
    if complete_metadata:
        complete_data.update(complete_metadata)
    yield _sse_event("complete", complete_data)
    yield PipelineComplete(data=complete_data)
