"""Shared constants for the PromptForge backend."""

from dataclasses import dataclass, field
from enum import StrEnum


class OptimizationStatus(StrEnum):
    """Status values for optimization records."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class Strategy(StrEnum):
    """Optimization strategy names — single source of truth.

    Each value corresponds to a prompt engineering framework.
    """

    CO_STAR = "co-star"
    RISEN = "risen"
    CHAIN_OF_THOUGHT = "chain-of-thought"
    FEW_SHOT_SCAFFOLDING = "few-shot-scaffolding"
    ROLE_TASK_FORMAT = "role-task-format"
    STRUCTURED_OUTPUT = "structured-output"
    STEP_BY_STEP = "step-by-step"
    CONSTRAINT_INJECTION = "constraint-injection"
    CONTEXT_ENRICHMENT = "context-enrichment"
    PERSONA_ASSIGNMENT = "persona-assignment"


# Maps old 5-strategy names to the new 10-framework equivalents.
# Used by schema validation and LLM response normalization.
LEGACY_STRATEGY_ALIASES: dict[str, str] = {
    "few-shot": "few-shot-scaffolding",
    "role-based": "persona-assignment",
    "constraint-focused": "constraint-injection",
    "structured-enhancement": "role-task-format",
}


class ProjectStatus(StrEnum):
    """Status values for project records."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


ALLOWED_SORT_FIELDS: frozenset[str] = frozenset({
    "created_at",
    "overall_score",
    "task_type",
    "complexity",
    "status",
    "duration_ms",
    "title",
    "project",
})

ALLOWED_PROJECT_SORT_FIELDS: frozenset[str] = frozenset({
    "created_at",
    "updated_at",
    "name",
})


# ---------------------------------------------------------------------------
# Pipeline stage configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StageConfig:
    """Configuration for a single pipeline stage."""

    name: str  # step name used in SSE events (e.g. "analyze")
    event_name: str  # SSE event type for stage result (e.g. "analysis")
    stage_label: str  # stage value in the "stage" SSE event (e.g. "analyzing")
    stage_message: str  # human-readable message for the "stage" SSE event
    initial_messages: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    progress_messages: tuple[str, ...] = field(default_factory=tuple)
    progress_interval: float = 1.5


def compute_progress(msg_index: int) -> float:
    """Compute progress fraction for a progress message index."""
    return min(0.4 + 0.1 * msg_index, 0.9)


STAGE_ANALYZE = StageConfig(
    name="analyze",
    event_name="analysis",
    stage_label="analyzing",
    stage_message="Analyzing prompt structure and intent...",
    initial_messages=(
        ("Examining prompt structure...", 0.1),
        ("Identifying task type, complexity, and patterns...", 0.3),
    ),
    progress_messages=(
        "Detecting prompt intent and goal...",
        "Evaluating clarity and specificity...",
        "Analyzing structural patterns...",
        "Identifying strengths and weaknesses...",
        "Compiling analysis results...",
        "Assessing task type confidence...",
        "Reviewing complexity indicators...",
        "Cross-referencing analysis dimensions...",
        "Finalizing prompt classification...",
        "Wrapping up analysis...",
    ),
)

STAGE_STRATEGY = StageConfig(
    name="strategy",
    event_name="strategy",
    stage_label="strategizing",
    stage_message="Selecting optimization strategy...",
    initial_messages=(
        ("Evaluating prompt characteristics...", 0.1),
        ("Matching task type to optimal approach...", 0.3),
    ),
    progress_messages=(
        "Analyzing task type and complexity alignment...",
        "Evaluating strategy-strength redundancy...",
        "Assessing specificity and constraint needs...",
        "Weighing strategy confidence levels...",
        "Finalizing strategy selection...",
    ),
    progress_interval=1.0,
)

STAGE_OPTIMIZE = StageConfig(
    name="optimize",
    event_name="optimization",
    stage_label="optimizing",
    stage_message="Applying {strategy} strategy...",
    initial_messages=(
        ("Applying {strategy} optimization strategy...", 0.1),
        ("Rewriting prompt with {strategy} framework...", 0.3),
    ),
    progress_messages=(
        "Restructuring for maximum clarity...",
        "Adding context and specificity...",
        "Refining language and tone...",
        "Incorporating best practices...",
        "Finalizing optimized prompt...",
        "Polishing structural elements...",
        "Verifying constraint alignment...",
        "Enhancing prompt specificity...",
        "Reviewing optimization quality...",
        "Completing rewrite...",
    ),
)

STAGE_VALIDATE = StageConfig(
    name="validate",
    event_name="validation",
    stage_label="validating",
    stage_message="Validating optimization quality...",
    initial_messages=(
        ("Scoring clarity, specificity, and structure...", 0.1),
        ("Evaluating improvement and generating verdict...", 0.3),
    ),
    progress_messages=(
        "Comparing original and optimized versions...",
        "Measuring clarity improvement...",
        "Assessing specificity and structure...",
        "Checking faithfulness to intent...",
        "Generating final verdict...",
        "Validating score consistency...",
        "Cross-checking improvement indicators...",
        "Computing weighted overall score...",
        "Reviewing verdict rationale...",
        "Completing quality assessment...",
    ),
)
