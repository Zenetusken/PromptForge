"""Health check endpoint with pipeline metrics."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app._version import __version__
from app.database import get_db
from app.services.optimization_service import OptimizationService

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """Liveness check with provider, version, and pipeline health metrics."""
    provider = getattr(request.app.state, "provider", None)

    # Pipeline metrics
    score_health = None
    avg_duration_ms = None
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
    except Exception:
        pass  # Non-fatal — health endpoint should always respond

    return {
        "status": "healthy" if provider else "degraded",
        "version": __version__,
        "provider": provider.name if provider else None,
        "score_health": score_health,
        "avg_duration_ms": avg_duration_ms,
    }
