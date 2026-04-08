"""Tests for TaxonomyEngine dirty-set tracking."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def engine():
    """Create a TaxonomyEngine with mocked dependencies."""
    from app.services.taxonomy.engine import TaxonomyEngine
    mock_embedding = MagicMock()
    mock_provider = MagicMock()
    eng = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    return eng


class TestDirtySet:
    def test_initial_dirty_set_empty(self, engine):
        assert len(engine._dirty_set) == 0

    def test_mark_dirty(self, engine):
        engine.mark_dirty("cluster-1")
        assert "cluster-1" in engine._dirty_set

    def test_mark_dirty_multiple(self, engine):
        engine.mark_dirty("cluster-1")
        engine.mark_dirty("cluster-2")
        assert len(engine._dirty_set) == 2

    def test_mark_dirty_idempotent(self, engine):
        engine.mark_dirty("cluster-1")
        engine.mark_dirty("cluster-1")
        assert len(engine._dirty_set) == 1

    def test_snapshot_and_clear(self, engine):
        engine.mark_dirty("cluster-1")
        engine.mark_dirty("cluster-2")
        snapshot = engine.snapshot_dirty_set()
        assert snapshot == {"cluster-1", "cluster-2"}
        assert len(engine._dirty_set) == 0  # cleared

    def test_snapshot_empty(self, engine):
        snapshot = engine.snapshot_dirty_set()
        assert snapshot == set()

    def test_is_first_cycle(self, engine):
        """First cycle (age=0) should signal full-scan needed."""
        assert engine._warm_path_age == 0
        assert engine.is_first_warm_cycle()

    def test_not_first_cycle_after_increment(self, engine):
        engine._warm_path_age = 1
        assert not engine.is_first_warm_cycle()
