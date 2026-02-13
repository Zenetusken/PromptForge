"""Shared constants for the PromptForge backend."""

from enum import StrEnum


class OptimizationStatus(StrEnum):
    """Status values for optimization records."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


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
