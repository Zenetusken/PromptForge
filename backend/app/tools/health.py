"""Handler for synthesis_health MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging

from app.config import PROMPTS_DIR
from app.database import async_session_factory
from app.schemas.mcp_models import HealthOutput
from app.services.strategy_loader import StrategyLoader
from app.tools._shared import get_routing

logger = logging.getLogger(__name__)


async def handle_health() -> HealthOutput:
    """Check system capabilities and health."""
    routing = get_routing()

    # Get provider info from routing state
    state = routing.state
    provider_name = state.provider_name if state.provider_name else None
    status = "healthy" if provider_name else "degraded"

    # Determine available tiers
    available_tiers = list(routing.available_tiers)

    # Get strategy list
    try:
        strategy_loader = StrategyLoader(PROMPTS_DIR / "strategies")
        strategies = strategy_loader.list_strategies()
    except Exception as exc:
        logger.warning("Could not load strategies for health check: %s", exc)
        strategies = []

    # Get optimization stats from DB
    total_optimizations = 0
    avg_score: float | None = None
    recent_error_rate: float | None = None

    try:
        from app.services.optimization_service import OptimizationService

        async with async_session_factory() as db:
            opt_svc = OptimizationService(db)
            # Total count
            result = await opt_svc.list_optimizations(limit=1, offset=0)
            total_optimizations = result["total"]

            # Average score
            if total_optimizations > 0:
                from sqlalchemy import func, select
                from app.models import Optimization

                score_result = await db.execute(
                    select(func.avg(Optimization.overall_score)).where(
                        Optimization.status == "completed",
                        Optimization.overall_score.isnot(None),
                    )
                )
                avg_val = score_result.scalar()
                if avg_val is not None:
                    avg_score = round(float(avg_val), 2)

            # Recent error rate
            error_counts = await opt_svc.get_recent_error_counts()
            total_recent = error_counts.get("total", 0)
            failed_recent = error_counts.get("failed", 0)
            if total_recent > 0:
                recent_error_rate = round(failed_recent / total_recent, 3)
    except Exception as exc:
        logger.warning("Could not fetch optimization stats for health: %s", exc)

    return HealthOutput(
        status=status,
        provider=provider_name,
        available_tiers=available_tiers,
        sampling_capable=state.sampling_capable,
        total_optimizations=total_optimizations,
        avg_score=avg_score,
        recent_error_rate=recent_error_rate,
        available_strategies=strategies,
    )
