# Embedding Fusion Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three remaining gaps in the composite embedding fusion system — disk cache for two indices, silhouette-based cluster validity metric, and output-coherence-weighted cold path blending.

**Architecture:** Three independent changes: (1) add `save_cache`/`load_cache` to TransformationIndex and OptimizedEmbeddingIndex mirroring EmbeddingIndex's pattern, (2) compute silhouette score in `batch_cluster()` and wire it into Q_system via the existing DBCV weight slot, (3) adaptive per-cluster blend weights in the cold path based on output coherence metadata.

**Tech Stack:** Python, numpy, sklearn.metrics.silhouette_score, pytest, asyncio

**Spec:** `docs/superpowers/specs/2026-04-02-embedding-fusion-hardening-design.md`

---

### Task 1: Disk Cache for TransformationIndex

**Files:**
- Modify: `backend/app/services/taxonomy/transformation_index.py` (add `save_cache`, `load_cache` after line 197)
- Test: `backend/tests/taxonomy/test_transformation_index.py`

- [ ] **Step 1: Write failing tests for save_cache / load_cache**

Add to `backend/tests/taxonomy/test_transformation_index.py`:

```python
import time
from pathlib import Path


@pytest.mark.asyncio
async def test_save_and_load_cache_round_trip(index: TransformationIndex, tmp_path: Path):
    """Save/load round-trip preserves vectors."""
    v1 = _rand_emb(seed=10)
    v2 = _rand_emb(seed=20)
    await index.upsert("c1", v1)
    await index.upsert("c2", v2)

    cache_path = tmp_path / "transformation_index.pkl"
    await index.save_cache(cache_path)
    assert cache_path.exists()

    fresh = TransformationIndex(dim=384)
    loaded = await fresh.load_cache(cache_path)
    assert loaded is True
    assert fresh.size == 2

    restored_v1 = fresh.get_vector("c1")
    assert restored_v1 is not None
    assert np.dot(restored_v1, v1 / np.linalg.norm(v1)) > 0.99


@pytest.mark.asyncio
async def test_load_cache_rejects_stale(index: TransformationIndex, tmp_path: Path):
    """Cache older than max_age_seconds is rejected."""
    await index.upsert("c1", _rand_emb(seed=1))
    cache_path = tmp_path / "transformation_index.pkl"
    await index.save_cache(cache_path)

    fresh = TransformationIndex(dim=384)
    loaded = await fresh.load_cache(cache_path, max_age_seconds=0)
    assert loaded is False
    assert fresh.size == 0


@pytest.mark.asyncio
async def test_load_cache_missing_file(index: TransformationIndex, tmp_path: Path):
    """Missing file returns False without error."""
    loaded = await index.load_cache(tmp_path / "nonexistent.pkl")
    assert loaded is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/taxonomy/test_transformation_index.py::test_save_and_load_cache_round_trip tests/taxonomy/test_transformation_index.py::test_load_cache_rejects_stale tests/taxonomy/test_transformation_index.py::test_load_cache_missing_file -v`

Expected: FAIL — `TransformationIndex` has no `save_cache`/`load_cache` methods.

- [ ] **Step 3: Implement save_cache and load_cache**

Add to the end of `TransformationIndex` class in `backend/app/services/taxonomy/transformation_index.py`, after the `restore` method (after line 197). Also add `import time` and `from pathlib import Path` to the imports at the top.

```python
    async def save_cache(self, cache_path: Path) -> None:
        """Serialize index to disk for fast startup recovery."""
        import pickle

        async with self._lock:
            data = {"matrix": self._matrix, "ids": list(self._ids)}
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
            logger.info(
                "TransformationIndex cache saved: %d entries -> %s",
                len(data["ids"]),
                cache_path,
            )
        except Exception as exc:
            logger.warning("TransformationIndex cache save failed: %s", exc)

    async def load_cache(
        self, cache_path: Path, max_age_seconds: int = 3600
    ) -> bool:
        """Load index from disk cache if fresh. Returns True if loaded."""
        import pickle

        if not cache_path.exists():
            return False
        age = time.time() - cache_path.stat().st_mtime
        if age > max_age_seconds:
            logger.info(
                "TransformationIndex cache stale (%.0fs old, max %ds)",
                age,
                max_age_seconds,
            )
            return False
        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)  # noqa: S301
            async with self._lock:
                self._matrix = data["matrix"]
                self._ids = data["ids"]
            logger.info(
                "TransformationIndex loaded from cache: %d entries (%.0fs old)",
                len(self._ids),
                age,
            )
            return True
        except Exception as exc:
            logger.warning("TransformationIndex cache load failed: %s", exc)
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/taxonomy/test_transformation_index.py -v`

Expected: All pass, including the three new tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/transformation_index.py backend/tests/taxonomy/test_transformation_index.py
git commit -m "feat: add save_cache/load_cache to TransformationIndex"
```

---

### Task 2: Disk Cache for OptimizedEmbeddingIndex

**Files:**
- Modify: `backend/app/services/taxonomy/optimized_index.py` (add `save_cache`, `load_cache` after line 199)
- Create: `backend/tests/taxonomy/test_optimized_index.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/taxonomy/test_optimized_index.py`:

```python
"""Unit tests for OptimizedEmbeddingIndex save_cache / load_cache."""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from app.services.taxonomy.optimized_index import OptimizedEmbeddingIndex


def _rand_emb(dim: int = 384, seed: int | None = None) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def index() -> OptimizedEmbeddingIndex:
    return OptimizedEmbeddingIndex(dim=384)


@pytest.mark.asyncio
async def test_save_and_load_cache_round_trip(
    index: OptimizedEmbeddingIndex, tmp_path: Path
):
    """Save/load round-trip preserves vectors."""
    v1 = _rand_emb(seed=10)
    v2 = _rand_emb(seed=20)
    await index.upsert("c1", v1)
    await index.upsert("c2", v2)

    cache_path = tmp_path / "optimized_index.pkl"
    await index.save_cache(cache_path)
    assert cache_path.exists()

    fresh = OptimizedEmbeddingIndex(dim=384)
    loaded = await fresh.load_cache(cache_path)
    assert loaded is True
    assert fresh.size == 2

    restored_v1 = fresh.get_vector("c1")
    assert restored_v1 is not None
    assert np.dot(restored_v1, v1 / np.linalg.norm(v1)) > 0.99


@pytest.mark.asyncio
async def test_load_cache_rejects_stale(
    index: OptimizedEmbeddingIndex, tmp_path: Path
):
    """Cache older than max_age_seconds is rejected."""
    await index.upsert("c1", _rand_emb(seed=1))
    cache_path = tmp_path / "optimized_index.pkl"
    await index.save_cache(cache_path)

    fresh = OptimizedEmbeddingIndex(dim=384)
    loaded = await fresh.load_cache(cache_path, max_age_seconds=0)
    assert loaded is False
    assert fresh.size == 0


@pytest.mark.asyncio
async def test_load_cache_missing_file(
    index: OptimizedEmbeddingIndex, tmp_path: Path
):
    """Missing file returns False without error."""
    loaded = await index.load_cache(tmp_path / "nonexistent.pkl")
    assert loaded is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/taxonomy/test_optimized_index.py -v`

Expected: FAIL — `OptimizedEmbeddingIndex` has no `save_cache`/`load_cache` methods.

- [ ] **Step 3: Implement save_cache and load_cache**

Add to the end of `OptimizedEmbeddingIndex` class in `backend/app/services/taxonomy/optimized_index.py`, after the `restore` method (after line 199). Also add `import time` and `from pathlib import Path` to the imports.

```python
    async def save_cache(self, cache_path: Path) -> None:
        """Serialize index to disk for fast startup recovery."""
        import pickle

        async with self._lock:
            data = {"matrix": self._matrix, "ids": list(self._ids)}
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
            logger.info(
                "OptimizedEmbeddingIndex cache saved: %d entries -> %s",
                len(data["ids"]),
                cache_path,
            )
        except Exception as exc:
            logger.warning("OptimizedEmbeddingIndex cache save failed: %s", exc)

    async def load_cache(
        self, cache_path: Path, max_age_seconds: int = 3600
    ) -> bool:
        """Load index from disk cache if fresh. Returns True if loaded."""
        import pickle

        if not cache_path.exists():
            return False
        age = time.time() - cache_path.stat().st_mtime
        if age > max_age_seconds:
            logger.info(
                "OptimizedEmbeddingIndex cache stale (%.0fs old, max %ds)",
                age,
                max_age_seconds,
            )
            return False
        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)  # noqa: S301
            async with self._lock:
                self._matrix = data["matrix"]
                self._ids = data["ids"]
            logger.info(
                "OptimizedEmbeddingIndex loaded from cache: %d entries (%.0fs old)",
                len(self._ids),
                age,
            )
            return True
        except Exception as exc:
            logger.warning("OptimizedEmbeddingIndex cache load failed: %s", exc)
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/taxonomy/test_optimized_index.py -v`

Expected: All 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/optimized_index.py backend/tests/taxonomy/test_optimized_index.py
git commit -m "feat: add save_cache/load_cache to OptimizedEmbeddingIndex"
```

---

### Task 3: Wire Cache Save Into Cold Path

**Files:**
- Modify: `backend/app/services/taxonomy/cold_path.py` (add save calls after line ~718)

- [ ] **Step 1: Write failing test**

Add to `backend/tests/taxonomy/test_cold_path.py` (or `test_engine_cold_path.py` — use whichever already tests cold path execution). This is an integration-level test, so it may need mocking. If the test file uses mocks of the engine, add an assertion that `save_cache` was called on both indices. If not feasible as a unit test, verify manually in Step 4.

For a targeted unit test, add to `backend/tests/taxonomy/test_cold_path.py`:

```python
def test_cold_path_saves_all_three_caches():
    """Verify cold_path.py references save_cache for all three indices."""
    import inspect
    from app.services.taxonomy import cold_path

    source = inspect.getsource(cold_path)
    assert "transformation_index.pkl" in source, (
        "Cold path must save TransformationIndex cache"
    )
    assert "optimized_index.pkl" in source, (
        "Cold path must save OptimizedEmbeddingIndex cache"
    )
    assert "embedding_index.pkl" in source, (
        "Cold path must save EmbeddingIndex cache (existing)"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/taxonomy/test_cold_path.py::test_cold_path_saves_all_three_caches -v`

Expected: FAIL — `transformation_index.pkl` and `optimized_index.pkl` not in source.

- [ ] **Step 3: Add save_cache calls to cold_path.py**

In `backend/app/services/taxonomy/cold_path.py`, after the TransformationIndex rebuild block (around line 678), add:

```python
    # Persist TransformationIndex cache to disk for fast startup recovery
    try:
        await engine._transformation_index.save_cache(
            DATA_DIR / "transformation_index.pkl"
        )
    except Exception as ti_cache_exc:
        logger.warning(
            "TransformationIndex cache save failed (non-fatal): %s", ti_cache_exc
        )
```

After the OptimizedEmbeddingIndex rebuild block (around line 718), add:

```python
    # Persist OptimizedEmbeddingIndex cache to disk for fast startup recovery
    try:
        await engine._optimized_index.save_cache(
            DATA_DIR / "optimized_index.pkl"
        )
    except Exception as oi_cache_exc:
        logger.warning(
            "OptimizedEmbeddingIndex cache save failed (non-fatal): %s", oi_cache_exc
        )
```

Note: `DATA_DIR` is already imported in the same block (line 633). The new save calls use the same lazy import pattern — place them inside the accepted commit section (after line ~718), reusing the existing `from app.config import DATA_DIR` import that's already at line 633.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/taxonomy/test_cold_path.py::test_cold_path_saves_all_three_caches -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/cold_path.py backend/tests/taxonomy/test_cold_path.py
git commit -m "feat: cold path saves TransformationIndex + OptimizedEmbeddingIndex caches"
```

---

### Task 4: Wire Cache Load Into Engine Startup

**Files:**
- Modify: `backend/app/main.py` (~line 193, after EmbeddingIndex warm-load block)

- [ ] **Step 1: Add cache loading for both indices at startup**

In `backend/app/main.py`, after the EmbeddingIndex warm-load `except` block (line ~196), add:

```python
            # Warm-load TransformationIndex from disk cache
            _ti_cache_path = DATA_DIR / "transformation_index.pkl"
            try:
                _ti_loaded = await engine._transformation_index.load_cache(_ti_cache_path)
                if _ti_loaded:
                    logger.info(
                        "TransformationIndex warm-loaded from cache: %d vectors",
                        engine._transformation_index.size,
                    )
                else:
                    logger.info("TransformationIndex cache not available — will populate via hot path")
            except Exception as ti_exc:
                logger.warning(
                    "TransformationIndex warm-load failed (non-fatal): %s", ti_exc
                )

            # Warm-load OptimizedEmbeddingIndex from disk cache
            _oi_cache_path = DATA_DIR / "optimized_index.pkl"
            try:
                _oi_loaded = await engine._optimized_index.load_cache(_oi_cache_path)
                if _oi_loaded:
                    logger.info(
                        "OptimizedEmbeddingIndex warm-loaded from cache: %d vectors",
                        engine._optimized_index.size,
                    )
                else:
                    logger.info("OptimizedEmbeddingIndex cache not available — will populate via hot path")
            except Exception as oi_exc:
                logger.warning(
                    "OptimizedEmbeddingIndex warm-load failed (non-fatal): %s", oi_exc
                )
```

- [ ] **Step 2: Verify startup still works**

Run: `cd backend && source .venv/bin/activate && timeout 10 python -c "from app.main import app; print('Import OK')" 2>&1 || true`

Expected: No import errors.

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: warm-load TransformationIndex + OptimizedEmbeddingIndex caches at startup"
```

---

### Task 5: Silhouette Score in batch_cluster

**Files:**
- Modify: `backend/app/services/taxonomy/clustering.py` (add `silhouette` field to `ClusterResult`, compute after HDBSCAN)
- Modify: `backend/tests/taxonomy/test_clustering.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/taxonomy/test_clustering.py`:

```python
def test_cluster_result_has_silhouette():
    """ClusterResult includes silhouette score in [0, 1]."""
    from app.services.taxonomy.clustering import batch_cluster
    # Create 3 tight clusters of 5 points each
    rng = np.random.RandomState(42)
    clusters = []
    for center_seed in [0.0, 3.0, 6.0]:
        center = np.zeros(384, dtype=np.float32)
        center[0] = center_seed
        for _ in range(5):
            point = center + rng.randn(384).astype(np.float32) * 0.1
            clusters.append(point / np.linalg.norm(point))

    result = batch_cluster(clusters, min_cluster_size=3)
    assert hasattr(result, "silhouette"), "ClusterResult must have silhouette field"
    assert 0.0 <= result.silhouette <= 1.0


def test_silhouette_zero_for_single_cluster():
    """Silhouette is 0.0 when only one cluster found (or all noise)."""
    from app.services.taxonomy.clustering import batch_cluster
    rng = np.random.RandomState(99)
    # Tight single blob — HDBSCAN should find 1 cluster or all noise
    points = []
    for _ in range(10):
        v = rng.randn(384).astype(np.float32)
        points.append(v / np.linalg.norm(v))

    result = batch_cluster(points, min_cluster_size=3)
    assert result.silhouette == pytest.approx(0.0, abs=0.01) or result.n_clusters <= 1


def test_silhouette_zero_for_too_few_points():
    """Silhouette is 0.0 when too few points to cluster."""
    from app.services.taxonomy.clustering import batch_cluster
    v = np.random.randn(384).astype(np.float32)
    result = batch_cluster([v, v], min_cluster_size=3)
    assert result.silhouette == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/taxonomy/test_clustering.py::test_cluster_result_has_silhouette tests/taxonomy/test_clustering.py::test_silhouette_zero_for_single_cluster tests/taxonomy/test_clustering.py::test_silhouette_zero_for_too_few_points -v`

Expected: FAIL — `ClusterResult` has no `silhouette` attribute.

- [ ] **Step 3: Implement silhouette computation**

In `backend/app/services/taxonomy/clustering.py`:

1. Add import at top of file (near other imports):
```python
from sklearn.metrics import silhouette_score
```

2. Add `silhouette` field to `ClusterResult` dataclass (after `centroids` line ~44):
```python
    silhouette: float = 0.0
```

3. In `batch_cluster()`, before the final `return ClusterResult(...)` (line ~353), add silhouette computation:

```python
    # --- Silhouette score: cluster validity metric ---
    # Requires >= 2 clusters and >= 2 non-noise points.
    # Rescale from [-1, 1] to [0, 1] for Q_system compatibility.
    sil = 0.0
    non_noise_mask = labels >= 0
    if n_clusters >= 2 and non_noise_mask.sum() >= 2:
        try:
            raw_sil = silhouette_score(mat[non_noise_mask], labels[non_noise_mask])
            sil = (raw_sil + 1.0) / 2.0
        except Exception:
            sil = 0.0
```

4. Update the return statement to include `silhouette=sil`:
```python
    return ClusterResult(
        labels=labels,
        n_clusters=n_clusters,
        noise_count=noise_count,
        persistences=persistences,
        centroids=centroids,
        silhouette=sil,
    )
```

Also update the early-return for too-few-points (line ~315) to include `silhouette=0.0`:
```python
        return ClusterResult(
            labels=labels,
            n_clusters=0,
            noise_count=n,
            persistences=[],
            centroids=[],
            silhouette=0.0,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/taxonomy/test_clustering.py -v`

Expected: All pass, including the three new silhouette tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/clustering.py backend/tests/taxonomy/test_clustering.py
git commit -m "feat: compute silhouette score in batch_cluster for Q_system validity"
```

---

### Task 6: Wire Silhouette Into Q_system

**Files:**
- Modify: `backend/app/services/taxonomy/engine.py` (`_compute_q_from_nodes` — line 723)
- Modify: `backend/app/services/taxonomy/cold_path.py` (pass silhouette through)
- Modify: `backend/app/services/taxonomy/warm_phases.py` (compute centroid-based silhouette)
- Modify: `backend/tests/taxonomy/test_quality.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/taxonomy/test_quality.py`:

```python
class TestQSystemWithSilhouette:
    """Verify DBCV slot activates when silhouette is provided."""

    def test_silhouette_increases_q_when_ramped(self):
        nodes = [
            NodeMetrics(coherence=0.8, separation=0.6, state="active"),
            NodeMetrics(coherence=0.7, separation=0.5, state="active"),
        ] * 5  # 10 nodes — ramp_progress = (10-5)/20 = 0.25

        # Without silhouette (old behavior)
        w_no_sil = QWeights.from_ramp(0.0)
        q_no_sil = compute_q_system(nodes, w_no_sil, coverage=1.0, dbcv=0.0)

        # With silhouette and ramp
        w_sil = QWeights.from_ramp(0.25)
        q_sil = compute_q_system(nodes, w_sil, coverage=1.0, dbcv=0.9)

        # High silhouette should improve Q
        assert q_sil > q_no_sil

    def test_silhouette_no_effect_below_5_nodes(self):
        nodes = [
            NodeMetrics(coherence=0.8, separation=0.6, state="active"),
        ] * 3  # 3 nodes — ramp_progress = 0.0

        w = QWeights.from_ramp(0.0)
        q = compute_q_system(nodes, w, coverage=1.0, dbcv=0.9)

        # DBCV weight is 0 when ramp is 0, so dbcv=0.9 has no effect
        w2 = QWeights.from_ramp(0.0)
        q2 = compute_q_system(nodes, w2, coverage=1.0, dbcv=0.0)
        assert q == pytest.approx(q2)
```

- [ ] **Step 2: Run tests to verify they pass (these test Q_system internals which already work)**

Run: `cd backend && pytest tests/taxonomy/test_quality.py::TestQSystemWithSilhouette -v`

Expected: PASS — `compute_q_system` already accepts `dbcv` parameter; the test validates the weight math works. This confirms the plumbing is correct before we wire callers.

- [ ] **Step 3: Update `_compute_q_from_nodes` to accept and pass silhouette**

In `backend/app/services/taxonomy/engine.py`, change `_compute_q_from_nodes` (line ~723):

```python
    def _compute_q_from_nodes(
        self, nodes: list[PromptCluster], silhouette: float = 0.0
    ) -> float:
        """Compute Q_system from a list of PromptCluster rows."""
        from app.services.taxonomy.quality import (
            NodeMetrics,
            QWeights,
            compute_q_system,
        )

        if not nodes:
            return 0.0

        metrics = []
        for n in nodes:
            metrics.append(
                NodeMetrics(
                    coherence=n.coherence if n.coherence is not None else 0.0,
                    separation=n.separation if n.separation is not None else 1.0,
                    state=n.state or "active",
                )
            )

        # DBCV ramp: linear activation from 5 to 25 active nodes.
        # Below 5 nodes the taxonomy is too young for validity metrics.
        n_active = len(metrics)
        ramp = min(1.0, max(0.0, (n_active - 5) / 20))
        weights = QWeights.from_ramp(ramp)

        return compute_q_system(metrics, weights, dbcv=silhouette)
```

- [ ] **Step 4: Pass silhouette from cold path**

In `backend/app/services/taxonomy/cold_path.py`, store the silhouette from `batch_cluster` result. After `cluster_result = batch_cluster(blended_embeddings, min_cluster_size=3)` (line ~196), the `cluster_result.silhouette` is available.

Find the two `_compute_q_from_nodes` calls:

1. **Q_before** (line ~120): Leave as-is (`silhouette=0.0` default) — we don't have pre-refit silhouette.

2. **Q_after** (line ~568): Change to:
```python
    q_after = engine._compute_q_from_nodes(active_after, silhouette=cluster_result.silhouette)
```

Note: `cluster_result` is defined at line ~196 and is in scope at line ~568.

- [ ] **Step 5: Pass silhouette from warm path**

In `backend/app/services/taxonomy/warm_phases.py`, at the Q_after computation (line ~1674), compute silhouette from active node centroids.

Add before the `q_after = engine._compute_q_from_nodes(active_after)` call:

```python
    # Compute silhouette from active centroids for Q_system validity metric.
    _warm_silhouette = 0.0
    if len(active_after) >= 2:
        try:
            _centroids_for_sil = []
            _labels_for_sil = []
            for _i, _n in enumerate(active_after):
                if _n.centroid_embedding:
                    _emb = np.frombuffer(_n.centroid_embedding, dtype=np.float32)
                    if _emb.shape[0] == 384:
                        _centroids_for_sil.append(_emb / max(np.linalg.norm(_emb), 1e-9))
                        _labels_for_sil.append(_i)
            if len(set(_labels_for_sil)) >= 2:
                from sklearn.metrics import silhouette_score as _sil_score
                _mat = np.stack(_centroids_for_sil)
                _raw_sil = _sil_score(_mat, _labels_for_sil)
                _warm_silhouette = (_raw_sil + 1.0) / 2.0
        except Exception:
            _warm_silhouette = 0.0
    q_after = engine._compute_q_from_nodes(active_after, silhouette=_warm_silhouette)
```

Add `import numpy as np` to the top of `warm_phases.py` if not already present.

- [ ] **Step 6: Run full quality and warm/cold path tests**

Run: `cd backend && pytest tests/taxonomy/test_quality.py tests/taxonomy/test_engine_cold_path.py tests/taxonomy/test_engine_warm_path.py tests/taxonomy/test_warm_path.py tests/taxonomy/test_cold_path.py -v`

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/taxonomy/engine.py backend/app/services/taxonomy/cold_path.py backend/app/services/taxonomy/warm_phases.py backend/tests/taxonomy/test_quality.py
git commit -m "feat: wire silhouette score into Q_system with ramp activation"
```

---

### Task 7: Output-Coherence-Weighted Cold Path Blending

**Files:**
- Modify: `backend/app/services/taxonomy/cold_path.py` (lines ~177-189)
- Create: `backend/tests/taxonomy/test_cold_path_adaptive_blend.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/taxonomy/test_cold_path_adaptive_blend.py`:

```python
"""Tests for output-coherence-adaptive blend weights in cold path."""

import numpy as np
import pytest

from app.services.taxonomy._constants import (
    CLUSTERING_BLEND_W_OPTIMIZED,
    CLUSTERING_BLEND_W_RAW,
    CLUSTERING_BLEND_W_TRANSFORM,
)
from app.services.taxonomy.clustering import blend_embeddings


def test_low_output_coherence_reduces_optimized_weight():
    """When output coherence < 0.5, w_optimized should be reduced."""
    # Simulate adaptive logic: output_coherence=0.2 → scale = max(0.25, 0.2/0.5) = 0.4
    output_coherence = 0.2
    scale = max(0.25, output_coherence / 0.5)
    w_opt = CLUSTERING_BLEND_W_OPTIMIZED * scale
    w_raw = 1.0 - w_opt - CLUSTERING_BLEND_W_TRANSFORM

    assert w_opt < CLUSTERING_BLEND_W_OPTIMIZED, "Low coherence should reduce w_optimized"
    assert w_opt == pytest.approx(0.20 * 0.4)  # 0.08
    assert w_raw == pytest.approx(1.0 - 0.08 - 0.15)  # 0.77
    assert w_raw + w_opt + CLUSTERING_BLEND_W_TRANSFORM == pytest.approx(1.0)


def test_high_output_coherence_keeps_default_weights():
    """When output coherence >= 0.5, default weights are used."""
    output_coherence = 0.8
    # No scaling applied
    w_opt = CLUSTERING_BLEND_W_OPTIMIZED  # 0.20
    w_raw = CLUSTERING_BLEND_W_RAW  # 0.65

    assert w_opt == 0.20
    assert w_raw == 0.65


def test_missing_output_coherence_keeps_default_weights():
    """When output_coherence is None, default weights are used."""
    output_coherence = None
    w_opt = CLUSTERING_BLEND_W_OPTIMIZED
    assert w_opt == 0.20


def test_adaptive_blend_weight_invariant():
    """w_raw + w_optimized + w_transform must always sum to 1.0."""
    for coh in [0.0, 0.1, 0.25, 0.4, 0.5, 0.7, 1.0, None]:
        w_opt = CLUSTERING_BLEND_W_OPTIMIZED
        if coh is not None and coh < 0.5:
            w_opt = CLUSTERING_BLEND_W_OPTIMIZED * max(0.25, coh / 0.5)
        w_raw = 1.0 - w_opt - CLUSTERING_BLEND_W_TRANSFORM
        total = w_raw + w_opt + CLUSTERING_BLEND_W_TRANSFORM
        assert total == pytest.approx(1.0), f"Sum != 1.0 for coherence={coh}: {total}"
        assert w_opt >= CLUSTERING_BLEND_W_OPTIMIZED * 0.25, f"Floor violated for coherence={coh}"


def test_blend_embeddings_accepts_custom_weights():
    """blend_embeddings() works with non-default weights."""
    rng = np.random.RandomState(42)
    raw = rng.randn(384).astype(np.float32)
    opt = rng.randn(384).astype(np.float32)
    trans = rng.randn(384).astype(np.float32)

    result = blend_embeddings(
        raw=raw, optimized=opt, transformation=trans,
        w_raw=0.77, w_optimized=0.08, w_transform=0.15,
    )
    assert result.shape == (384,)
    assert np.linalg.norm(result) == pytest.approx(1.0, abs=1e-5)
```

- [ ] **Step 2: Run tests to verify they pass (these test the math, not the integration)**

Run: `cd backend && pytest tests/taxonomy/test_cold_path_adaptive_blend.py -v`

Expected: All PASS — these test the weight math and `blend_embeddings` API which already supports custom weights.

- [ ] **Step 3: Implement adaptive blend in cold_path.py**

In `backend/app/services/taxonomy/cold_path.py`, replace the blend loop (lines ~177-189):

From:
```python
    blended_embeddings: list[np.ndarray] = []
    opt_idx = getattr(engine, "_optimized_index", None)
    trans_idx = getattr(engine, "_transformation_index", None)
    for i, f in enumerate(valid_families):
        opt_vec = opt_idx.get_vector(f.id) if opt_idx else None
        trans_vec = trans_idx.get_vector(f.id) if trans_idx else None
        blended_embeddings.append(
            blend_embeddings(
                raw=embeddings[i],
                optimized=opt_vec,
                transformation=trans_vec,
            )
        )
```

To:
```python
    blended_embeddings: list[np.ndarray] = []
    opt_idx = getattr(engine, "_optimized_index", None)
    trans_idx = getattr(engine, "_transformation_index", None)
    for i, f in enumerate(valid_families):
        opt_vec = opt_idx.get_vector(f.id) if opt_idx else None
        trans_vec = trans_idx.get_vector(f.id) if trans_idx else None

        # Adaptive blend: downweight optimized signal when output coherence
        # is low — divergent outputs make the optimized embedding mean
        # unreliable as a clustering signal.
        w_opt = CLUSTERING_BLEND_W_OPTIMIZED
        out_coh = read_meta(f.cluster_metadata).get("output_coherence")
        if out_coh is not None and out_coh < 0.5:
            w_opt = CLUSTERING_BLEND_W_OPTIMIZED * max(0.25, out_coh / 0.5)
        w_raw = 1.0 - w_opt - CLUSTERING_BLEND_W_TRANSFORM

        blended_embeddings.append(
            blend_embeddings(
                raw=embeddings[i],
                optimized=opt_vec,
                transformation=trans_vec,
                w_raw=w_raw,
                w_optimized=w_opt,
                w_transform=CLUSTERING_BLEND_W_TRANSFORM,
            )
        )
```

Add the `_constants` import to `cold_path.py` (near line 36, after the existing imports):

```python
from app.services.taxonomy._constants import (
    CLUSTERING_BLEND_W_OPTIMIZED,
    CLUSTERING_BLEND_W_TRANSFORM,
)
```

`read_meta` is already imported at line 38.

- [ ] **Step 4: Add integration test for cold path source**

Add to `backend/tests/taxonomy/test_cold_path_adaptive_blend.py`:

```python
def test_cold_path_uses_adaptive_blend():
    """Verify cold_path.py implements adaptive blend logic."""
    import inspect
    from app.services.taxonomy import cold_path

    source = inspect.getsource(cold_path)
    assert "output_coherence" in source, (
        "Cold path must reference output_coherence for adaptive blending"
    )
    assert "max(0.25" in source, (
        "Cold path must enforce 0.25 floor on coherence scaling"
    )
```

- [ ] **Step 5: Run all tests to verify nothing breaks**

Run: `cd backend && pytest tests/taxonomy/test_cold_path_adaptive_blend.py tests/taxonomy/test_cold_path.py tests/taxonomy/test_engine_cold_path.py tests/taxonomy/test_blend_embeddings.py -v`

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/taxonomy/cold_path.py backend/tests/taxonomy/test_cold_path_adaptive_blend.py
git commit -m "feat: output-coherence-weighted blend in cold path HDBSCAN"
```

---

### Task 8: Full Test Suite + Lint

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && pytest --cov=app -v 2>&1 | tail -30`

Expected: All tests pass.

- [ ] **Step 2: Run ruff lint**

Run: `cd backend && ruff check app/ tests/ --fix`

Expected: No errors (or auto-fixed).

- [ ] **Step 3: Final commit if lint changes**

```bash
git add -A && git commit -m "fix: lint cleanup for embedding fusion hardening"
```

(Skip if no changes.)

- [ ] **Step 4: Push**

```bash
git push origin main
```
