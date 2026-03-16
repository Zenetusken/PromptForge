"""Tests for score clustering detection via optimization_service."""

import pytest

from app.models import Optimization
from app.services.optimization_service import OptimizationService


@pytest.fixture
async def svc_with_clustered_data(db_session):
    """Insert 15 optimizations with tightly clustered scores."""
    for i in range(15):
        opt = Optimization(
            id=f"cal-{i}", raw_prompt=f"p{i}", optimized_prompt=f"b{i}",
            task_type="coding", strategy_used="auto",
            overall_score=7.8 + (i % 3) * 0.1,  # 7.8, 7.9, 8.0 repeating
            score_clarity=7.8, score_specificity=7.9, score_structure=7.8,
            score_faithfulness=8.0, score_conciseness=7.7,
            status="completed", trace_id=f"ct-{i}", provider="mock",
        )
        db_session.add(opt)
    await db_session.commit()
    return OptimizationService(db_session)


class TestScoreCalibration:
    async def test_clustering_detected_low_stddev(self, svc_with_clustered_data):
        stats = await svc_with_clustered_data.get_score_distribution()
        # Tight cluster (7.8-8.0) → stddev should be very low
        assert stats["overall_score"]["stddev"] < 0.5
        assert stats["overall_score"]["count"] == 15

    async def test_no_clustering_with_spread(self, db_session):
        for i in range(15):
            opt = Optimization(
                id=f"spread-{i}", raw_prompt=f"p{i}", optimized_prompt=f"b{i}",
                task_type="coding", strategy_used="auto",
                overall_score=2.0 + i * 0.5,  # 2.0 to 9.0
                score_clarity=2.0 + i * 0.5,
                status="completed", trace_id=f"st-{i}", provider="mock",
            )
            db_session.add(opt)
        await db_session.commit()
        svc = OptimizationService(db_session)
        stats = await svc.get_score_distribution()
        assert stats["overall_score"]["stddev"] > 1.0
