"""Handler for synthesis_match MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging

from app.database import async_session_factory
from app.schemas.mcp_models import MatchOutput, MetaPatternSummary
from app.tools._shared import get_taxonomy_engine

logger = logging.getLogger(__name__)


async def handle_match(prompt_text: str) -> MatchOutput:
    """Search the knowledge graph for similar clusters and reusable patterns."""
    if len(prompt_text) < 10:
        raise ValueError(
            "Prompt text too short (%d chars). Minimum is 10 characters." % len(prompt_text)
        )

    taxonomy_engine = get_taxonomy_engine()
    if taxonomy_engine is None:
        logger.info("synthesis_match: taxonomy engine not available — returning no match")
        return MatchOutput(
            match_level="none",
            similarity=0.0,
        )

    from app.services.embedding_service import EmbeddingService
    from app.services.taxonomy.matching import match_prompt

    embedding_service = EmbeddingService()

    async with async_session_factory() as db:
        result = await match_prompt(prompt_text, db, embedding_service)

    if result is None or result.match_level == "none":
        return MatchOutput(
            match_level="none",
            similarity=result.similarity if result else 0.0,
        )

    # Convert PatternMatch to MatchOutput
    meta_patterns = []
    for mp in (result.meta_patterns or []):
        meta_patterns.append(MetaPatternSummary(
            id=mp.id,
            pattern_text=mp.pattern_text or "",
            source_count=mp.source_count or 0,
        ))

    cluster = result.cluster
    cluster_id = cluster.id if cluster else None
    cluster_label = cluster.label if cluster else None
    recommended_strategy = cluster.preferred_strategy if cluster else None

    return MatchOutput(
        match_level=result.match_level,
        similarity=round(result.similarity, 4),
        cluster_id=cluster_id,
        cluster_label=cluster_label,
        taxonomy_breadcrumb=result.taxonomy_breadcrumb or [],
        meta_patterns=meta_patterns,
        recommended_strategy=recommended_strategy,
    )
