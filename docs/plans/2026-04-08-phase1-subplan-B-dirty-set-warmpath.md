# Phase 1 Sub-plan B: Dirty-Set Tracking + Warm Path Optimization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `_dirty_set` to TaxonomyEngine so the warm path only processes clusters that changed since the last cycle. Add adaptive scheduler measurement infrastructure (rolling window + p75 target). Reduce warm path wall-clock time from O(all_clusters) to O(dirty_clusters) for phases 1 and 2.

**Architecture:** The hot path marks cluster IDs as dirty when members are added/removed. The warm path snapshots the dirty set at cycle start, clears it, and scopes each phase according to its needs (some phases are dirty-only, others remain full-scan). A rolling window of (dirty_count, duration_ms) tuples provides self-tuning measurement for future round-robin scheduling (Phase 3).

**Tech Stack:** Python 3.12, asyncio, SQLAlchemy async, pytest

**Spec:** `docs/specs/2026-04-08-taxonomy-scaling-design.md` (sections: Warm Path Changes)

---

### Task 1: Add _dirty_set to TaxonomyEngine

**Files:**
- Modify: `backend/app/services/taxonomy/engine.py`
- Test: `backend/tests/taxonomy/test_dirty_set.py` (create)

- [ ] **Step 1: Write the test**

```python
# backend/tests/taxonomy/test_dirty_set.py
"""Tests for TaxonomyEngine dirty-set tracking."""

import pytest
from unittest.mock import AsyncMock, MagicMock


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/taxonomy/test_dirty_set.py -v
```
Expected: FAIL — `mark_dirty`, `snapshot_dirty_set`, `is_first_warm_cycle` not defined

- [ ] **Step 3: Implement on TaxonomyEngine**

In `engine.py`, add to `__init__()` after line 117 (`self._stats_cache_time`):

```python
# ADR-005: Dirty-set tracking for warm path optimization.
# Hot path marks clusters as dirty when members change.
# Warm path snapshots and clears at cycle start.
self._dirty_set: set[str] = set()
```

Add methods after `__init__()`:

```python
def mark_dirty(self, cluster_id: str) -> None:
    """Mark a cluster as needing warm-path processing."""
    self._dirty_set.add(cluster_id)

def snapshot_dirty_set(self) -> set[str]:
    """Snapshot the dirty set and clear it atomically.

    Returns the set of cluster IDs that need processing.
    Safe under asyncio cooperative scheduling (no await between read and clear).
    """
    snapshot = set(self._dirty_set)
    self._dirty_set.clear()
    return snapshot

def is_first_warm_cycle(self) -> bool:
    """True if this is the first warm cycle after server restart.

    The first cycle runs a full scan to catch changes from before restart.
    """
    return self._warm_path_age == 0
```

- [ ] **Step 4: Mark dirty in hot path**

In `engine.py`, in `process_optimization()`, after the cluster assignment (around line 294 where `opt.cluster_id = cluster.id` is set):

```python
self.mark_dirty(cluster.id)
```

Also after old cluster reassignment (around line 288 where old_cluster member_count is decremented):

```python
if old_cluster and old_cluster.id != cluster.id:
    self.mark_dirty(old_cluster.id)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/taxonomy/test_dirty_set.py -v
pytest --tb=short -q  # full suite
```
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/taxonomy/engine.py backend/tests/taxonomy/test_dirty_set.py
git commit -m "feat(taxonomy): add dirty-set tracking to TaxonomyEngine (ADR-005)

Hot path marks cluster IDs dirty on member add/remove. Warm path
will snapshot and clear at cycle start to scope processing."
```

---

### Task 2: Wire dirty-set into warm path orchestration

**Files:**
- Modify: `backend/app/services/taxonomy/warm_path.py`
- Test: `backend/tests/taxonomy/test_warm_path_dirty.py` (create)

- [ ] **Step 1: Write the test**

```python
# backend/tests/taxonomy/test_warm_path_dirty.py
"""Tests for warm path dirty-set integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_warm_path_passes_dirty_set_to_phases():
    """Warm path should snapshot dirty set and pass to phase functions."""
    # This is an integration test that verifies the plumbing.
    # Mock the engine and verify snapshot_dirty_set is called.
    from app.services.taxonomy.engine import TaxonomyEngine

    mock_embedding = MagicMock()
    mock_provider = MagicMock()
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)

    engine.mark_dirty("cluster-1")
    engine.mark_dirty("cluster-2")

    # Snapshot should return the dirty IDs
    snapshot = engine.snapshot_dirty_set()
    assert snapshot == {"cluster-1", "cluster-2"}
    assert len(engine._dirty_set) == 0

    # After snapshot, marking new IDs starts a fresh set
    engine.mark_dirty("cluster-3")
    assert engine._dirty_set == {"cluster-3"}


@pytest.mark.asyncio
async def test_first_cycle_returns_none_dirty_set():
    """First warm cycle (age=0) should signal full-scan via None dirty set."""
    from app.services.taxonomy.engine import TaxonomyEngine

    mock_embedding = MagicMock()
    mock_provider = MagicMock()
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)

    assert engine.is_first_warm_cycle()
    # On first cycle, caller should treat dirty_set as None (= process all)
```

- [ ] **Step 2: Modify warm_path.py to pass dirty_set**

In `warm_path.py`, in the `run_warm_path_inner()` or equivalent orchestration function, at the beginning of the cycle:

```python
# ADR-005: Snapshot dirty set — first cycle does full scan
if engine.is_first_warm_cycle():
    dirty_ids = None  # None = process all clusters (restart recovery)
else:
    dirty_ids = engine.snapshot_dirty_set()
    if not dirty_ids:
        dirty_ids = None  # empty dirty set = nothing changed, but phases that need full scan still run
```

Pass `dirty_ids` to each phase function. Phases that support dirty scoping use it to filter; phases that need full scan ignore it.

Pass `dirty_ids` to each phase function. The warm path orchestration function is `execute_warm_path()` in `warm_path.py` (NOT `run_warm_path_inner()` — that function does not exist). The phase function signatures gain an optional `dirty_ids: set[str] | None = None` parameter:
- `phase_split_emerge(db, engine, active_nodes, dirty_ids=None)` — filters candidates
- `phase_merge(db, engine, active_nodes, dirty_ids=None)` — filters merge candidates + neighbors
- Other phases (reconcile, retire, refresh, discover, audit) — ignore dirty_ids (full scan)

**NOTE:** Sub-plan A modifies `_load_active_nodes()` in `warm_path.py` to use `EXCLUDED_STRUCTURAL_STATES`. If Sub-plan A runs first (recommended), the code you're modifying will use `list(EXCLUDED_STRUCTURAL_STATES)` instead of `["domain", "archived"]`. Adapt accordingly.

- [ ] **Step 3: Run tests**

```bash
pytest tests/taxonomy/test_warm_path_dirty.py -v
pytest --tb=short -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/taxonomy/warm_path.py backend/tests/taxonomy/test_warm_path_dirty.py
git commit -m "feat(taxonomy): wire dirty-set into warm path orchestration (ADR-005)

First cycle after restart does full scan. Subsequent cycles snapshot
dirty set and pass to phase functions. Phases that support dirty
scoping filter by dirty IDs; others do full scan."
```

---

### Task 3: Implement phase-specific dirty scoping in warm_phases.py

**Files:**
- Modify: `backend/app/services/taxonomy/warm_phases.py`

- [ ] **Step 1: Add dirty_ids parameter to phase_split_emerge**

The split/emerge phase currently iterates all active nodes to find split candidates. With dirty scoping, only evaluate clusters whose IDs are in `dirty_ids`:

```python
async def phase_split_emerge(
    db, engine, active_nodes, split_protected_ids, operations_log,
    dirty_ids=None,  # ADR-005: None = process all, set = process only these
):
    # ... existing code ...
    for node in active_nodes:
        # ADR-005: Skip clean clusters in dirty-only mode
        if dirty_ids is not None and node.id not in dirty_ids:
            continue
        # ... existing split candidacy checks ...
```

- [ ] **Step 2: Add dirty_ids parameter to phase_merge**

Merge needs to consider dirty clusters AND their potential merge partners (neighbors). A dirty cluster might now be mergeable with a clean neighbor. The merge phase has three sub-sections (global best-pair, same-domain label merge, same-domain embedding merge). Each builds a pairwise candidate list. With dirty scoping, filter the candidate list so that at least one member of each pair is dirty:

```python
async def phase_merge(
    db, engine, active_nodes, split_protected_ids, operations_log,
    dirty_ids=None,  # ADR-005
):
    # ... existing setup code (load active nodes, opt/trans indices) ...

    # --- Global best-pair merge ---
    # Build valid_nodes and blended_centroids as before (from ALL active nodes)
    # ... existing centroid loading code ...

    if len(valid_nodes) >= 2:
        # ... existing pairwise similarity computation ...

        # ADR-005: In dirty-only mode, skip pairs where neither node is dirty
        if dirty_ids is not None:
            if valid_nodes[winner_idx].id not in dirty_ids and valid_nodes[loser_idx].id not in dirty_ids:
                pass  # skip this pair — neither changed
            else:
                # ... existing merge execution code ...
                pass

    # --- Same-domain label merge ---
    # ... existing domain grouping code ...
    for domain_label, domain_nodes in domain_groups.items():
        # ADR-005: filter candidates — at least one must be dirty
        if dirty_ids is not None:
            has_dirty = any(n.id in dirty_ids for n in domain_nodes)
            if not has_dirty:
                continue  # no dirty nodes in this domain group — skip

        # ... existing same-domain merge logic ...

    # --- Same-domain embedding merge ---
    # Same dirty filter as above
    for domain_label, remaining in domain_groups.items():
        if dirty_ids is not None:
            has_dirty = any(n.id in dirty_ids for n in remaining)
            if not has_dirty:
                continue

        # ... existing embedding merge logic ...
```

Key: the merge partner can be ANY active node (not just dirty ones). The filter only gates whether we EVALUATE a pair — it must contain at least one dirty member. This ensures that a dirty cluster that grew past the merge threshold gets matched even if its nearest neighbor hasn't changed.

- [ ] **Step 3: Leave full-scan phases unchanged**

Phases 0 (reconcile), 3 (retire), 4 (refresh), 5 (discover), 6 (audit) remain full-scan. Add a comment at each:

```python
# ADR-005: Full scan — reconciliation needs complete cluster state
```

- [ ] **Step 4: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: All pass (dirty_ids=None preserves existing behavior)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/warm_phases.py
git commit -m "feat(taxonomy): phase-specific dirty scoping in warm path (ADR-005)

Phase 1 (split/emerge): dirty clusters only
Phase 2 (merge): dirty clusters + all merge partners
Phases 0, 3, 4, 5, 6: full scan (unchanged, need complete state)"
```

---

### Task 4: Add adaptive scheduler measurement

**Files:**
- Modify: `backend/app/services/taxonomy/engine.py`
- Modify: `backend/app/services/taxonomy/warm_path.py`
- Test: `backend/tests/taxonomy/test_adaptive_scheduler.py` (create)

- [ ] **Step 1: Write the test**

```python
# backend/tests/taxonomy/test_adaptive_scheduler.py
"""Tests for warm path adaptive scheduler measurement."""

import statistics

import pytest

from app.services.taxonomy.engine import WarmCycleMeasurement, AdaptiveScheduler


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
        # Simulate 10 cycles with varying durations
        durations = [2000, 3000, 2500, 4000, 3500, 2000, 3000, 5000, 2500, 3000]
        for i, d in enumerate(durations):
            scheduler.record(dirty_count=10 + i, duration_ms=d)
        # p75 of durations
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
```

- [ ] **Step 2: Implement AdaptiveScheduler**

In `engine.py`, add the dataclass and class:

```python
from dataclasses import dataclass, field


@dataclass
class WarmCycleMeasurement:
    """Single warm cycle measurement for adaptive scheduling."""
    dirty_count: int
    duration_ms: int


class AdaptiveScheduler:
    """Self-tuning warm path scheduler (ADR-005).

    Phase 1: measurement only (always all-dirty mode).
    Phase 3: adds round-robin branching when data shows need.
    """

    _WINDOW_SIZE = 10
    _BOOTSTRAP_TARGET_MS = 10_000  # 10s default until enough data

    def __init__(self) -> None:
        self._window: list[WarmCycleMeasurement] = []
        self._target_cycle_ms: int = self._BOOTSTRAP_TARGET_MS

    @property
    def target_cycle_ms(self) -> int:
        return self._target_cycle_ms

    def record(self, dirty_count: int, duration_ms: int) -> None:
        """Record a warm cycle measurement and update target."""
        self._window.append(WarmCycleMeasurement(dirty_count, duration_ms))
        if len(self._window) > self._WINDOW_SIZE:
            self._window = self._window[-self._WINDOW_SIZE:]

        # Update target after bootstrap period
        if len(self._window) >= self._WINDOW_SIZE:
            durations = [m.duration_ms for m in self._window]
            # p75 = the "comfortable" cycle duration
            quantiles = statistics.quantiles(durations, n=4)
            self._target_cycle_ms = int(quantiles[2])  # 75th percentile

    def snapshot(self) -> dict:
        """Return scheduler state for logging/observability."""
        return {
            "target_cycle_ms": self._target_cycle_ms,
            "window_size": len(self._window),
            "mode": "all_dirty",  # Phase 1: always all-dirty
            "bootstrapping": len(self._window) < self._WINDOW_SIZE,
        }
```

Add `import statistics` at the top of engine.py.

Add `self._scheduler = AdaptiveScheduler()` to `TaxonomyEngine.__init__()`.

- [ ] **Step 3: Wire scheduler into warm path**

In `warm_path.py`, at the end of each warm cycle (after all phases complete):

```python
import time

cycle_start = time.monotonic()
# ... run phases ...
cycle_duration_ms = int((time.monotonic() - cycle_start) * 1000)

dirty_count = len(dirty_ids) if dirty_ids else total_active_count
engine._scheduler.record(dirty_count=dirty_count, duration_ms=cycle_duration_ms)
```

In the audit event (`q_computed`), add scheduler state:

```python
context={
    # ... existing fields ...
    "scheduler": engine._scheduler.snapshot(),
}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/taxonomy/test_adaptive_scheduler.py -v
pytest --tb=short -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/engine.py backend/app/services/taxonomy/warm_path.py backend/tests/taxonomy/test_adaptive_scheduler.py
git commit -m "feat(taxonomy): adaptive scheduler measurement infrastructure (ADR-005)

Rolling window of last 10 warm cycles. Self-tuning p75 target duration.
Phase 1: all-dirty mode only. Phase 3 will add round-robin branching."
```

---

### Task 5: E2E validation — restart and verify dirty-set optimization

- [ ] **Step 1: Restart server**

```bash
./init.sh restart
```

- [ ] **Step 2: Trigger a warm path cycle**

```bash
curl -s -X POST http://127.0.0.1:8000/api/events/_publish \
  -H "Content-Type: application/json" \
  -d '{"event_type": "taxonomy_changed", "data": {"trigger": "test"}}'
```

- [ ] **Step 3: Check logs for scheduler state**

```bash
sleep 35 && grep "scheduler" data/backend.log | tail -5
```
Expected: q_computed event should include scheduler snapshot with `mode=all_dirty`

- [ ] **Step 4: Verify first cycle is full-scan**

```bash
grep "Phase 0\|warm_path_age" data/backend.log | head -5
```
Expected: First cycle processes all clusters (warm_path_age=0 → full scan)

- [ ] **Step 5: Run full test suite**

```bash
cd backend && source .venv/bin/activate && pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix: ADR-005 warm path dirty-set E2E adjustments"
```
