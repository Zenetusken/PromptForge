"""Tests for GlobalPattern promotion (Phase 2B)."""

import pytest

from app.models import OptimizationPattern


def test_global_pattern_constants():
    """All Phase 2B constants exist."""
    from app.services.taxonomy._constants import (
        GLOBAL_PATTERN_CAP,
        GLOBAL_PATTERN_CYCLE_INTERVAL,
        GLOBAL_PATTERN_DEDUP_COSINE,
        GLOBAL_PATTERN_DEMOTION_SCORE,
        GLOBAL_PATTERN_MIN_WALL_CLOCK_MINUTES,
        GLOBAL_PATTERN_PROMOTION_MIN_CLUSTERS,
        GLOBAL_PATTERN_PROMOTION_MIN_PROJECTS,
        GLOBAL_PATTERN_PROMOTION_MIN_SCORE,
        GLOBAL_PATTERN_RELEVANCE_BOOST,
    )
    assert GLOBAL_PATTERN_RELEVANCE_BOOST == 1.3
    assert GLOBAL_PATTERN_CAP == 500
    assert GLOBAL_PATTERN_PROMOTION_MIN_CLUSTERS == 5
    assert GLOBAL_PATTERN_PROMOTION_MIN_PROJECTS == 2
    assert GLOBAL_PATTERN_PROMOTION_MIN_SCORE == 6.0
    assert GLOBAL_PATTERN_DEMOTION_SCORE == 5.0
    assert GLOBAL_PATTERN_DEDUP_COSINE == 0.90
    assert GLOBAL_PATTERN_CYCLE_INTERVAL == 10
    assert GLOBAL_PATTERN_MIN_WALL_CLOCK_MINUTES == 30


def test_optimization_pattern_has_global_pattern_id():
    """OptimizationPattern has global_pattern_id column."""
    assert hasattr(OptimizationPattern, "global_pattern_id")


def test_engine_has_last_global_pattern_check():
    """TaxonomyEngine has _last_global_pattern_check attribute."""
    from unittest.mock import MagicMock

    from app.services.taxonomy.engine import TaxonomyEngine
    engine = TaxonomyEngine(embedding_service=MagicMock(), provider=MagicMock())
    assert hasattr(engine, "_last_global_pattern_check")
    assert engine._last_global_pattern_check == 0.0
