"""SQLAlchemy ORM model for prompt optimizations."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from apps.promptforge.constants import OptimizationStatus


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


class Optimization(Base):
    """Represents a single prompt optimization run."""

    __tablename__ = "optimizations"

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=generate_uuid
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Input
    raw_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Optimized output
    optimized_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Analysis metadata
    task_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    complexity: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string list
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string list
    changes_made: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string list
    framework_applied: Mapped[str | None] = mapped_column(Text, nullable=True)
    optimization_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scores
    clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    specificity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    structure_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    conciseness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    framework_adherence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Validation
    is_improvement: Mapped[bool | None] = mapped_column(nullable=True)
    verdict: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Strategy
    strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    secondary_frameworks: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    detected_patterns: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list

    # Execution metadata
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_creation_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=OptimizationStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Organization
    project: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string list
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Link to originating project prompt (nullable for legacy/home-page optimizations)
    prompt_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True,
    )

    # Comparative evaluation: reference to the optimization this retried
    retry_of: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot of resolved codebase context used for this optimization run (JSON)
    codebase_context_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_optimizations_project", "project"),
        Index("ix_optimizations_task_type", "task_type"),
        Index("ix_optimizations_created_at", "created_at"),
        Index("ix_optimizations_status", "status"),
        Index("ix_optimizations_overall_score", "overall_score"),
        Index("ix_optimizations_status_created_at", "status", "created_at"),
        Index("ix_optimizations_task_type_project", "task_type", "project"),
        Index("ix_optimizations_prompt_id", "prompt_id"),
    )

    def __repr__(self) -> str:
        return f"<Optimization(id={self.id!r}, status={self.status!r}, title={self.title!r})>"
