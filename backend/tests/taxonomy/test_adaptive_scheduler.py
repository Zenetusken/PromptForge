"""Tests for warm path adaptive scheduler measurement."""

import statistics

from app.services.taxonomy.engine import AdaptiveScheduler


class TestAdaptiveScheduler:
    def test_bootstrap_target(self):
        """First 10 cycles use static fallback target."""
        scheduler = AdaptiveScheduler()
        assert scheduler.target_cycle_ms == 10_000  # bootstrap default

    def test_records_measurement(self):
        scheduler = AdaptiveScheduler()
        scheduler.record(dirty_count=5, duration_ms=3000)
        assert len(scheduler._window) == 1

    def test_target_updates_after_10_cycles(self):
        scheduler = AdaptiveScheduler()
        durations = [2000, 3000, 2500, 4000, 3500, 2000, 3000, 5000, 2500, 3000]
        for i, d in enumerate(durations):
            scheduler.record(dirty_count=10 + i, duration_ms=d)
        expected = int(statistics.quantiles(durations, n=4)[2])  # 75th percentile
        assert scheduler.target_cycle_ms == expected

    def test_window_size_bounded(self):
        scheduler = AdaptiveScheduler()
        for i in range(20):
            scheduler.record(dirty_count=i, duration_ms=1000 + i * 100)
        assert len(scheduler._window) == 10  # max window size

    def test_snapshot_for_logging(self):
        scheduler = AdaptiveScheduler()
        scheduler.record(dirty_count=5, duration_ms=3000)
        snap = scheduler.snapshot()
        assert "target_cycle_ms" in snap
        assert "window_size" in snap
        assert "mode" in snap
        assert snap["mode"] == "all_dirty"  # Phase 1: always all-dirty
