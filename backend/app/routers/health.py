"""Health check endpoint with pipeline metrics."""

import json as _json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app._version import __version__
from app.config import DATA_DIR
from app.database import get_db
from app.services.optimization_service import OptimizationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """Liveness check with provider, version, and pipeline health metrics."""
    provider = getattr(request.app.state, "provider", None)

    # Pipeline metrics
    score_health = None
    avg_duration_ms = None
    recent_errors = {"last_hour": 0, "last_24h": 0}
    phase_durations: dict[str, int] = {}
    try:
        svc = OptimizationService(db)
        stats = await svc.get_score_distribution()
        overall = stats.get("overall_score", {})
        if overall.get("count", 0) > 0:
            clustering_warning = (
                overall["count"] >= 10 and overall["stddev"] < 0.3
            ) or (
                overall["count"] >= 50 and overall["stddev"] < 0.5
            )
            score_health = {
                "last_n_mean": overall["mean"],
                "last_n_stddev": overall["stddev"],
                "count": overall["count"],
                "clustering_warning": clustering_warning,
            }

        # Average duration from recent optimizations
        result = await svc.list_optimizations(limit=50, sort_by="created_at", sort_order="desc")
        durations = [opt.duration_ms for opt in result["items"] if opt.duration_ms]
        if durations:
            avg_duration_ms = round(sum(durations) / len(durations))

        # Recent error counts
        recent_errors = await svc.get_recent_error_counts()

        # Per-phase average durations
        phase_durations = await svc.get_avg_duration_by_phase()
    except Exception:
        logger.debug("Health check metrics collection failed", exc_info=True)

    # MCP session sampling capability (written by mcp_server.py on tool calls
    # and by the ASGI capability-detection middleware on initialize handshake).
    # 30-minute staleness window — clients reconnect infrequently so a recent
    # positive detection should persist for a reasonable period.
    sampling_capable: bool | None = None
    mcp_session_path = DATA_DIR / "mcp_session.json"
    try:
        if mcp_session_path.exists():
            raw = _json.loads(mcp_session_path.read_text(encoding="utf-8"))
            written_at = datetime.fromisoformat(raw["written_at"])
            if datetime.now(timezone.utc) - written_at <= timedelta(minutes=30):
                sampling_capable = bool(raw["sampling_capable"])
    except Exception:
        logger.debug("Could not read mcp_session.json", exc_info=True)

    return {
        "status": "healthy" if provider else "degraded",
        "version": __version__,
        "provider": provider.name if provider else None,
        "score_health": score_health,
        "avg_duration_ms": phase_durations if phase_durations else avg_duration_ms,
        "recent_errors": recent_errors,
        "sampling_capable": sampling_capable,
    }
