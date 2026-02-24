"""Pydantic v2 schemas for prompt optimization requests and responses."""

from datetime import datetime

import re

from pydantic import BaseModel, Field, field_validator

from app.utils.datetime import UTCDatetime

from app.constants import LEGACY_STRATEGY_ALIASES, Strategy


class OptimizeRequest(BaseModel):
    """Request body for the optimize endpoint."""

    prompt: str = Field(
        ..., min_length=1, max_length=100_000, description="The raw prompt to optimize",
    )
    project: str | None = Field(
        None, max_length=100, description="Optional project name",
    )
    tags: list[str] | None = Field(None, description="Optional tags")
    title: str | None = Field(
        None, max_length=200, description="Optional title",
    )
    provider: str | None = Field(
        None, max_length=50,
        description="Provider name (e.g. 'openai'). Auto-detected if omitted.",
    )
    strategy: str | None = Field(
        None,
        description="Override strategy selection (e.g. 'chain-of-thought'). "
        "When provided, skips the automatic StrategySelector.",
    )
    secondary_frameworks: list[str] | None = Field(
        None,
        description="Optional secondary frameworks (0-2) to combine with primary strategy.",
    )
    version: str | None = Field(
        None, max_length=20, description="Optional version label (e.g. 'v1', 'v2')",
    )
    prompt_id: str | None = Field(
        None, description="Optional originating prompt ID (from a project)",
    )
    codebase_context: dict | None = Field(
        None,
        description=(
            "Optional codebase context for grounding the optimization in a real project. "
            "Accepted keys: language, framework, description, conventions, patterns, "
            "code_snippets, documentation, test_framework, test_patterns."
        ),
    )

    @field_validator("version")
    @classmethod
    def version_format(cls, v: str | None) -> str | None:
        """Validate version matches v<number> pattern when non-empty."""
        if v is not None and v.strip():
            if not re.match(r"^v\d+$", v.strip(), re.IGNORECASE):
                raise ValueError("Version must be in 'v<number>' format (e.g. 'v1', 'v2')")
        return v

    @field_validator("strategy")
    @classmethod
    def strategy_must_be_valid(cls, v: str | None) -> str | None:
        """Validate that the strategy is a known Strategy value or legacy alias."""
        if v is not None:
            # Accept legacy aliases and map to new names
            if v in LEGACY_STRATEGY_ALIASES:
                return LEGACY_STRATEGY_ALIASES[v]
            valid = {s.value for s in Strategy}
            if v not in valid:
                raise ValueError(f"Unknown strategy {v!r}. Valid: {', '.join(sorted(valid))}")
        return v

    @field_validator("secondary_frameworks")
    @classmethod
    def secondary_frameworks_must_be_valid(cls, v: list[str] | None) -> list[str] | None:
        """Validate secondary frameworks are known Strategy values (max 2)."""
        if v is None:
            return v
        if len(v) > 2:
            raise ValueError("At most 2 secondary frameworks allowed")
        valid = {s.value for s in Strategy}
        result = []
        for fw in v:
            mapped = LEGACY_STRATEGY_ALIASES.get(fw, fw)
            if mapped not in valid:
                raise ValueError(f"Unknown secondary framework {fw!r}. Valid: {', '.join(sorted(valid))}")
            result.append(mapped)
        return result

    @field_validator("tags")
    @classmethod
    def tag_items_max_length(cls, v: list[str] | None) -> list[str] | None:
        """Validate that each tag is no longer than 50 characters."""
        if v is not None:
            for tag in v:
                if len(tag) > 50:
                    raise ValueError(f"Tag must be 50 characters or fewer, got {len(tag)}")
        return v

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, v: str) -> str:
        """Validate that the prompt is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Prompt must not be empty or whitespace-only")
        return v


class OptimizationResponse(BaseModel):
    """Full optimization result returned from the API."""

    id: str
    created_at: UTCDatetime
    raw_prompt: str
    optimized_prompt: str | None = None
    task_type: str | None = None
    complexity: str | None = None
    weaknesses: list[str] | None = None
    strengths: list[str] | None = None
    changes_made: list[str] | None = None
    framework_applied: str | None = None
    optimization_notes: str | None = None
    strategy: str | None = None
    strategy_reasoning: str | None = None
    strategy_confidence: float | None = None
    secondary_frameworks: list[str] | None = None
    clarity_score: float | None = None
    specificity_score: float | None = None
    structure_score: float | None = None
    faithfulness_score: float | None = None
    overall_score: float | None = None
    is_improvement: bool | None = None
    verdict: str | None = None
    duration_ms: int | None = None
    model_used: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    status: str = "pending"
    error_message: str | None = None
    project: str | None = None
    tags: list[str] | None = None
    title: str | None = None
    version: str | None = None
    prompt_id: str | None = None
    project_id: str | None = None
    project_status: str | None = None
    codebase_context_snapshot: dict | None = None

    model_config = {"from_attributes": True}


class HistorySummaryResponse(BaseModel):
    """Lightweight summary for history list views (omits large text fields)."""

    id: str
    created_at: UTCDatetime
    raw_prompt: str
    title: str | None = None
    version: str | None = None
    task_type: str | None = None
    complexity: str | None = None
    project: str | None = None
    tags: list[str] | None = None
    overall_score: float | None = None
    strategy: str | None = None
    secondary_frameworks: list[str] | None = None
    framework_applied: str | None = None
    model_used: str | None = None
    status: str = "pending"
    error_message: str | None = None
    prompt_id: str | None = None
    project_id: str | None = None
    project_status: str | None = None

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    """Paginated response for optimization history."""

    items: list[HistorySummaryResponse]
    total: int
    page: int
    per_page: int


class StatsResponse(BaseModel):
    """Aggregated statistics for the optimization history."""

    total_optimizations: int = 0
    average_overall_score: float | None = None
    average_clarity_score: float | None = None
    average_specificity_score: float | None = None
    average_structure_score: float | None = None
    average_faithfulness_score: float | None = None
    improvement_rate: float | None = None
    total_projects: int = 0
    most_common_task_type: str | None = None
    optimizations_today: int = 0
    strategy_distribution: dict[str, int] | None = None
    score_by_strategy: dict[str, float] | None = None
    task_types_by_strategy: dict[str, dict[str, int]] | None = None
    secondary_strategy_distribution: dict[str, int] | None = None
    tags_by_strategy: dict[str, dict[str, int]] | None = None
    # --- Extended analytics (all nullable for backward compatibility) ---
    score_matrix: dict[str, dict[str, dict[str, float | int]]] | None = None
    score_variance: dict[str, dict[str, float | int]] | None = None
    confidence_by_strategy: dict[str, float] | None = None
    combo_effectiveness: dict[str, dict[str, dict[str, float | int]]] | None = None
    complexity_performance: dict[str, dict[str, dict[str, float | int]]] | None = None
    improvement_by_strategy: dict[str, dict[str, float | int | None]] | None = None
    error_rates: dict[str, dict[str, float | int]] | None = None
    trend_7d: dict[str, float | int | None] | None = None
    trend_30d: dict[str, float | int | None] | None = None
    token_economics: dict[str, dict[str, int | None]] | None = None
    win_rates: dict[str, dict[str, str | float | int]] | None = None


class BulkDeleteRequest(BaseModel):
    """Request body for bulk-deleting optimization records."""

    ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of optimization record IDs to delete (1-100).",
    )


class BulkDeleteResponse(BaseModel):
    """Response for a bulk-delete operation."""

    deleted_count: int = Field(description="Number of records successfully deleted.")
    deleted_ids: list[str] = Field(description="IDs of records that were deleted.")
    not_found_ids: list[str] = Field(description="IDs that did not match any existing record.")
