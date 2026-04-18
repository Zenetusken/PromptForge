"""Pydantic schemas for the template API.

See docs/superpowers/specs/2026-04-18-template-architecture-design.md §API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TemplateRead(BaseModel):
    """A frozen template artifact forked from a graduated cluster."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_cluster_id: str | None
    source_optimization_id: str | None
    project_id: str | None
    label: str
    prompt: str
    strategy: str | None
    score: float
    pattern_ids: list[str]
    domain_label: str
    promoted_at: datetime
    retired_at: datetime | None
    retired_reason: str | None
    usage_count: int
    last_used_at: datetime | None


class TemplateListResponse(BaseModel):
    """Paginated list envelope — matches the project-wide pagination invariant."""

    total: int
    count: int
    offset: int
    items: list[TemplateRead]
    has_more: bool
    next_offset: int | None


class RetireRequest(BaseModel):
    """Manual retirement payload. Auto retirements only fire via the warm path."""

    reason: Literal["manual"] = "manual"
