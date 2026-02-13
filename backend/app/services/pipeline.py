"""Main optimization pipeline - orchestrates analysis, optimization, and validation."""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from typing import AsyncIterator

from app.services.analyzer import AnalysisResult, PromptAnalyzer
from app.services.claude_client import ClaudeClient
from app.services.optimizer import OptimizationResult, PromptOptimizer
from app.services.strategy_selector import StrategySelector
from app.services.validator import PromptValidator, ValidationResult


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


async def run_pipeline(
    raw_prompt: str,
    claude_client: ClaudeClient | None = None,
) -> PipelineResult:
    """Run the full optimization pipeline: analyze, select strategy, optimize, validate.

    Args:
        raw_prompt: The original prompt text to optimize.
        claude_client: Optional ClaudeClient instance. Creates a new one if not provided.

    Returns:
        A PipelineResult containing all analysis, optimization, and validation data.
    """
    start_time = time.time()
    client = claude_client or ClaudeClient()

    # Stage 1: Analyze the prompt
    analyzer = PromptAnalyzer(client)
    analysis: AnalysisResult = await analyzer.analyze(raw_prompt)

    # Stage 2: Select optimization strategy
    selector = StrategySelector()
    strategy_selection = selector.select(analysis)

    # Stage 3: Optimize the prompt
    optimizer = PromptOptimizer(client)
    optimization: OptimizationResult = await optimizer.optimize(
        raw_prompt, analysis, strategy_selection.strategy
    )

    # Stage 4: Validate the optimization
    validator = PromptValidator(client)
    validation: ValidationResult = await validator.validate(
        raw_prompt, optimization.optimized_prompt
    )

    elapsed_ms = int((time.time() - start_time) * 1000)

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
        model_used=client.model,
    )


async def _run_with_progress_stream(
    coro,
    step_name: str,
    progress_messages: list[str],
    interval: float = 1.5,
):
    """Run a coroutine while yielding periodic progress events.

    This is an async generator that yields SSE progress events at regular intervals
    while the main coroutine is running, then yields the final result as a special
    sentinel value.

    Args:
        coro: The async coroutine to run (e.g., analyzer.analyze()).
        step_name: The pipeline step name for progress events.
        progress_messages: List of progress messages to send during execution.
        interval: Seconds between progress messages.

    Yields:
        SSE event strings for progress, then a tuple ('_result', result) at the end.
    """
    task = asyncio.create_task(coro)
    msg_index = 0

    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=interval)
            # Task completed during wait
            break
        except asyncio.TimeoutError:
            # Task still running, send a progress message
            if msg_index < len(progress_messages):
                yield _sse_event("step_progress", {
                    "step": step_name,
                    "content": progress_messages[msg_index],
                    "progress": min(0.4 + 0.1 * msg_index, 0.9),
                })
                msg_index += 1
        except Exception:
            break

    # Get the result (may re-raise exception)
    result = await task
    yield ("_result", result)


async def run_pipeline_streaming(raw_prompt: str, claude_client: ClaudeClient | None = None):
    """Run the pipeline and yield SSE events for each stage.

    This is an async generator that yields Server-Sent Event formatted strings
    as the pipeline progresses through each stage. Progress events are sent
    periodically during long-running LLM calls for real-time streaming.

    Args:
        raw_prompt: The original prompt text to optimize.
        claude_client: Optional ClaudeClient instance.

    Yields:
        SSE-formatted strings for each pipeline stage and the final result.
    """
    pipeline_start = time.time()
    client = claude_client or ClaudeClient()

    # Stage 1: Analyze
    step_start = time.time()
    yield _sse_event("stage", {"stage": "analyzing", "message": "Analyzing prompt structure and intent..."})
    yield _sse_event("step_progress", {
        "step": "analyze",
        "content": "Examining prompt structure...",
        "progress": 0.1,
    })
    analyzer = PromptAnalyzer(client)
    yield _sse_event("step_progress", {
        "step": "analyze",
        "content": "Identifying task type, complexity, and patterns...",
        "progress": 0.3,
    })

    analysis = None
    async for event in _run_with_progress_stream(
        analyzer.analyze(raw_prompt),
        "analyze",
        [
            "Detecting prompt intent and goal...",
            "Evaluating clarity and specificity...",
            "Analyzing structural patterns...",
            "Identifying strengths and weaknesses...",
            "Compiling analysis results...",
        ],
        interval=1.5,
    ):
        if isinstance(event, tuple) and event[0] == "_result":
            analysis = event[1]
        else:
            yield event

    step_duration = int((time.time() - step_start) * 1000)
    analysis_dict = asdict(analysis)
    analysis_dict["step_duration_ms"] = step_duration
    yield _sse_event("analysis", analysis_dict)

    # Stage 2: Strategy Selection
    selector = StrategySelector()
    strategy = selector.select(analysis)

    # Stage 3: Optimize
    step_start = time.time()
    yield _sse_event("stage", {
        "stage": "optimizing",
        "message": f"Applying {strategy.strategy} strategy...",
    })
    yield _sse_event("step_progress", {
        "step": "optimize",
        "content": f"Applying {strategy.strategy} optimization strategy...",
        "progress": 0.1,
    })
    optimizer = PromptOptimizer(client)
    yield _sse_event("step_progress", {
        "step": "optimize",
        "content": f"Rewriting prompt with {strategy.strategy} framework...",
        "progress": 0.3,
    })

    optimization = None
    async for event in _run_with_progress_stream(
        optimizer.optimize(raw_prompt, analysis, strategy.strategy),
        "optimize",
        [
            "Restructuring for maximum clarity...",
            "Adding context and specificity...",
            "Refining language and tone...",
            "Incorporating best practices...",
            "Finalizing optimized prompt...",
        ],
        interval=1.5,
    ):
        if isinstance(event, tuple) and event[0] == "_result":
            optimization = event[1]
        else:
            yield event

    step_duration = int((time.time() - step_start) * 1000)
    optimization_dict = asdict(optimization)
    optimization_dict["step_duration_ms"] = step_duration
    yield _sse_event("optimization", optimization_dict)

    # Stage 4: Validate
    step_start = time.time()
    yield _sse_event("stage", {"stage": "validating", "message": "Validating optimization quality..."})
    yield _sse_event("step_progress", {
        "step": "validate",
        "content": "Scoring clarity, specificity, and structure...",
        "progress": 0.1,
    })
    validator = PromptValidator(client)
    yield _sse_event("step_progress", {
        "step": "validate",
        "content": "Evaluating improvement and generating verdict...",
        "progress": 0.3,
    })

    validation = None
    async for event in _run_with_progress_stream(
        validator.validate(raw_prompt, optimization.optimized_prompt),
        "validate",
        [
            "Comparing original and optimized versions...",
            "Measuring clarity improvement...",
            "Assessing specificity and structure...",
            "Checking faithfulness to intent...",
            "Generating final verdict...",
        ],
        interval=1.5,
    ):
        if isinstance(event, tuple) and event[0] == "_result":
            validation = event[1]
        else:
            yield event

    step_duration = int((time.time() - step_start) * 1000)
    validation_dict = asdict(validation)
    validation_dict["step_duration_ms"] = step_duration
    yield _sse_event("validation", validation_dict)

    # Complete
    elapsed_ms = int((time.time() - pipeline_start) * 1000)
    complete_data = {
        **asdict(analysis),
        **asdict(optimization),
        **asdict(validation),
        "duration_ms": elapsed_ms,
        "model_used": client.model,
        "status": "completed",
    }
    yield _sse_event("complete", complete_data)


def _sse_event(event_type: str, data: dict) -> str:
    """Format data as a Server-Sent Event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
