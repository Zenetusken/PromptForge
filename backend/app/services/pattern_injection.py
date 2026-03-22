"""Shared auto-injection logic for cluster meta-patterns.

Used by both the internal pipeline (``pipeline.py``) and the sampling-based
pipeline (``sampling_pipeline.py``) to discover and inject relevant patterns
from the taxonomy embedding index.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def auto_inject_patterns(
    raw_prompt: str,
    taxonomy_engine: Any,
    db: AsyncSession,
    trace_id: str,
) -> tuple[list[str], list[str]]:
    """Auto-inject cluster meta-patterns based on prompt embedding similarity.

    Embeds the raw prompt, searches the taxonomy embedding index for the
    nearest active clusters (cosine >= 0.72), and fetches their associated
    ``MetaPattern`` texts.

    Args:
        raw_prompt: The user's raw prompt text.
        taxonomy_engine: A ``TaxonomyEngine`` instance with an ``embedding_index``.
        db: Active async DB session for querying MetaPattern records.
        trace_id: Pipeline trace ID for log correlation.

    Returns:
        ``(pattern_texts, cluster_ids)`` — both empty lists if no match or error.
    """
    from app.models import MetaPattern
    from app.services.embedding_service import EmbeddingService

    embedding_svc = EmbeddingService()
    embedding_index = taxonomy_engine.embedding_index
    if embedding_index.size == 0:
        return [], []

    prompt_embedding = await embedding_svc.aembed_single(raw_prompt)
    matches = embedding_index.search(prompt_embedding, k=3, threshold=0.72)
    if not matches:
        return [], []

    auto_injected_cluster_ids = [m[0] for m in matches]
    result = await db.execute(
        select(MetaPattern).where(
            MetaPattern.cluster_id.in_(auto_injected_cluster_ids)
        )
    )
    patterns = result.scalars().all()
    if not patterns:
        return [], auto_injected_cluster_ids

    pattern_texts = [p.pattern_text for p in patterns]
    logger.info(
        "Auto-injected %d patterns from %d clusters. trace_id=%s",
        len(pattern_texts),
        len(auto_injected_cluster_ids),
        trace_id,
    )
    return pattern_texts, auto_injected_cluster_ids
