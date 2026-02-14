"""Pydantic v2 schemas for prompt optimization requests and responses."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class OptimizeRequest(BaseModel):
    """Request body for the optimize endpoint."""

    prompt: str = Field(..., min_length=1, description="The raw prompt to optimize")
    project: str | None = Field(
        None, max_length=100, description="Optional project name",
    )
    tags: list[str] | None = Field(None, description="Optional tags")
    title: str | None = Field(
        None, max_length=200, description="Optional title",
    )

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
    created_at: datetime
    raw_prompt: str
    optimized_prompt: str | None = None
    task_type: str | None = None
    complexity: str | None = None
    weaknesses: list[str] | None = None
    strengths: list[str] | None = None
    changes_made: list[str] | None = None
    framework_applied: str | None = None
    optimization_notes: str | None = None
    strategy_reasoning: str | None = None
    clarity_score: float | None = None
    specificity_score: float | None = None
    structure_score: float | None = None
    faithfulness_score: float | None = None
    overall_score: float | None = None
    is_improvement: bool | None = None
    verdict: str | None = None
    duration_ms: int | None = None
    model_used: str | None = None
    status: str = "pending"
    error_message: str | None = None
    project: str | None = None
    tags: list[str] | None = None
    title: str | None = None

    model_config = {"from_attributes": True}


class HistorySummaryResponse(BaseModel):
    """Lightweight summary for history list views (omits large text fields)."""

    id: str
    created_at: datetime
    raw_prompt: str
    title: str | None = None
    task_type: str | None = None
    project: str | None = None
    tags: list[str] | None = None
    overall_score: float | None = None
    status: str = "pending"
    error_message: str | None = None

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
