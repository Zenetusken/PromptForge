"""Handler for synthesis_feedback MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging

from app.database import async_session_factory
from app.schemas.mcp_models import FeedbackOutput
from app.services.event_notification import notify_event_bus
from app.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)


async def handle_feedback(
    optimization_id: str,
    rating: str,
    comment: str | None = None,
) -> FeedbackOutput:
    """Submit quality feedback on a completed optimization."""
    async with async_session_factory() as db:
        svc = FeedbackService(db)

        feedback = await svc.create_feedback(
            optimization_id=optimization_id,
            rating=rating,
            comment=comment,
        )

        await db.commit()

    # Strategy affinity is updated synchronously inside create_feedback
    strategy_affinity_updated = True

    # Notify frontend via cross-process event bus
    await notify_event_bus("feedback_submitted", {
        "id": feedback.id,
        "optimization_id": optimization_id,
        "rating": rating,
    })

    logger.info(
        "synthesis_feedback completed: feedback_id=%s optimization_id=%s rating=%s",
        feedback.id, optimization_id, rating,
    )

    return FeedbackOutput(
        feedback_id=feedback.id,
        optimization_id=optimization_id,
        rating=rating,
        strategy_affinity_updated=strategy_affinity_updated,
    )
