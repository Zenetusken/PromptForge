"""Main optimization pipeline - orchestrates analysis, optimization, and validation."""

import json
import time
from dataclasses import asdict, dataclass

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


async def run_pipeline_streaming(raw_prompt: str, claude_client: ClaudeClient | None = None):
    """Run the pipeline and yield SSE events for each stage.

    This is an async generator that yields Server-Sent Event formatted strings
    as the pipeline progresses through each stage.

    Args:
        raw_prompt: The original prompt text to optimize.
        claude_client: Optional ClaudeClient instance.

    Yields:
        SSE-formatted strings for each pipeline stage and the final result.
    """
    start_time = time.time()
    client = claude_client or ClaudeClient()

    # Stage 1: Analyze
    yield _sse_event("stage", {"stage": "analyzing", "message": "Analyzing prompt..."})
    analyzer = PromptAnalyzer(client)
    analysis = await analyzer.analyze(raw_prompt)
    yield _sse_event("analysis", asdict(analysis))

    # Stage 2: Strategy Selection
    selector = StrategySelector()
    strategy = selector.select(analysis)
    yield _sse_event("stage", {
        "stage": "optimizing",
        "message": f"Applying {strategy.strategy} strategy...",
    })

    # Stage 3: Optimize
    optimizer = PromptOptimizer(client)
    optimization = await optimizer.optimize(raw_prompt, analysis, strategy.strategy)
    yield _sse_event("optimization", asdict(optimization))

    # Stage 4: Validate
    yield _sse_event("stage", {"stage": "validating", "message": "Validating..."})
    validator = PromptValidator(client)
    validation = await validator.validate(raw_prompt, optimization.optimized_prompt)
    yield _sse_event("validation", asdict(validation))

    # Complete
    elapsed_ms = int((time.time() - start_time) * 1000)
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
