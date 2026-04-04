"""In-memory batch optimization pipeline.

Runs N prompts through analyze → optimize → score → embed in parallel
with zero DB writes. Results accumulate as PendingOptimization objects.
Bulk persist writes everything in a single transaction.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.config import settings
from app.providers.base import LLMProvider
from app.services.embedding_service import EmbeddingService
from app.services.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


@dataclass
class PendingOptimization:
    """In-memory optimization result awaiting bulk persist."""

    id: str
    trace_id: str
    raw_prompt: str
    batch_id: str = ""  # Lineage: which batch produced this row
    optimized_prompt: str | None = None
    task_type: str | None = None
    strategy_used: str | None = None
    changes_summary: str | None = None
    score_clarity: float | None = None
    score_specificity: float | None = None
    score_structure: float | None = None
    score_faithfulness: float | None = None
    score_conciseness: float | None = None
    overall_score: float | None = None
    improvement_score: float | None = None
    scoring_mode: str | None = None
    intent_label: str | None = None
    domain: str | None = None
    domain_raw: str | None = None
    embedding: bytes | None = None
    optimized_embedding: bytes | None = None
    transformation_embedding: bytes | None = None
    models_by_phase: dict | None = None
    original_scores: dict | None = None
    score_deltas: dict | None = None
    duration_ms: int | None = None
    status: str = "completed"
    provider: str | None = None
    model_used: str | None = None
    routing_tier: str | None = None
    heuristic_flags: list | None = None
    suggestions: list | None = None
    context_sources: dict | None = None
    error: str | None = None  # Non-None if this prompt failed
