"""Handler for synthesis_get_optimization MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import Feedback, Optimization, RefinementTurn
from app.schemas.mcp_models import OptimizationDetailOutput

logger = logging.getLogger(__name__)


async def handle_get_optimization(
    optimization_id: str,
) -> OptimizationDetailOutput:
    """Retrieve full details of a specific optimization."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Optimization).where(Optimization.id == optimization_id)
        )
        opt = result.scalar_one_or_none()

        if not opt:
            # Try trace_id fallback
            result = await db.execute(
                select(Optimization).where(Optimization.trace_id == optimization_id)
            )
            opt = result.scalar_one_or_none()

        if not opt:
            raise ValueError(f"Optimization not found: {optimization_id}")

        # Check feedback
        fb_result = await db.execute(
            select(func.count()).select_from(Feedback).where(
                Feedback.optimization_id == opt.id
            )
        )
        has_feedback = (fb_result.scalar() or 0) > 0

        # Count refinement versions
        rv_result = await db.execute(
            select(func.count()).select_from(RefinementTurn).where(
                RefinementTurn.optimization_id == opt.id
            )
        )
        refinement_versions = rv_result.scalar() or 0

        # Build scores dict
        scores: dict[str, float] | None = None
        if opt.score_clarity is not None:
            scores = {
                "clarity": opt.score_clarity,
                "specificity": opt.score_specificity or 0.0,
                "structure": opt.score_structure or 0.0,
                "faithfulness": opt.score_faithfulness or 0.0,
                "conciseness": opt.score_conciseness or 0.0,
            }

        # Original scores and deltas
        original_scores = opt.original_scores if hasattr(opt, "original_scores") else None
        score_deltas = opt.score_deltas if hasattr(opt, "score_deltas") else None

        created_str = opt.created_at.isoformat() if opt.created_at else None

        return OptimizationDetailOutput(
            id=opt.id,
            created_at=created_str,
            raw_prompt=opt.raw_prompt or "",
            optimized_prompt=opt.optimized_prompt,
            task_type=opt.task_type,
            strategy_used=opt.strategy_used,
            changes_summary=opt.changes_summary,
            scores=scores,
            original_scores=original_scores,
            score_deltas=score_deltas,
            overall_score=opt.overall_score,
            status=opt.status or "unknown",
            intent_label=opt.intent_label,
            domain=opt.domain,
            scoring_mode=opt.scoring_mode,
            has_feedback=has_feedback,
            refinement_versions=refinement_versions,
        )
