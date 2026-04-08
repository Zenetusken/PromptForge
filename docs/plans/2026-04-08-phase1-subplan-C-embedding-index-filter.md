# Phase 1 Sub-plan C: Embedding Index Project Filter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `project_filter` parameter to `EmbeddingIndex.search()` with a `_project_ids` parallel array for per-project vector filtering. This enables Phase 2's project-scoped hot-path assignment without changing the search algorithm.

**Architecture:** Each vector in the index is tagged with a `project_id`. When `project_filter` is set, the search masks the matrix to only include vectors with matching project_id before cosine computation. When `project_filter` is None (default), all vectors are searched — preserving backward compatibility.

**Tech Stack:** Python 3.12, numpy, asyncio, pickle (cache), pytest

**Spec:** `docs/specs/2026-04-08-taxonomy-scaling-design.md` (section: Embedding Index Changes)

**Scope note:** This sub-plan updates `EmbeddingIndex` only. `TransformationIndex` and `OptimizedEmbeddingIndex` do NOT need project filtering in Phase 1 (they're used for warm-path blending, not hot-path assignment). `pairwise_similarities()` also skipped — Phase 2 consideration. Must run AFTER Sub-plan A (shared `main.py` modifications).

---

### Task 1: Add project_id tracking to EmbeddingIndex

**Files:**
- Modify: `backend/app/services/taxonomy/embedding_index.py`
- Test: `backend/tests/taxonomy/test_embedding_index_project.py` (create)

- [ ] **Step 1: Write the test**

```python
# backend/tests/taxonomy/test_embedding_index_project.py
"""Tests for EmbeddingIndex project_id filtering (ADR-005)."""

import numpy as np
import pytest

from app.services.taxonomy.embedding_index import EmbeddingIndex


@pytest.fixture
def index():
    return EmbeddingIndex(dim=4)  # small dim for testing


def _random_emb(dim=4):
    v = np.random.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


class TestProjectIdTracking:
    @pytest.mark.asyncio
    async def test_upsert_with_project_id(self, index):
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        assert index.size == 1
        assert index._project_ids == ["proj-A"]

    @pytest.mark.asyncio
    async def test_upsert_without_project_id_defaults_to_none(self, index):
        await index.upsert("c1", _random_emb())
        assert index._project_ids == [None]

    @pytest.mark.asyncio
    async def test_upsert_update_preserves_project_id(self, index):
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        assert index.size == 1
        assert index._project_ids == ["proj-A"]

    @pytest.mark.asyncio
    async def test_remove_removes_project_id(self, index):
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        await index.upsert("c2", _random_emb(), project_id="proj-B")
        await index.remove("c1")
        assert index.size == 1
        assert index._project_ids == ["proj-B"]

    @pytest.mark.asyncio
    async def test_rebuild_with_project_ids(self, index):
        centroids = {"c1": _random_emb(), "c2": _random_emb()}
        project_ids = {"c1": "proj-A", "c2": "proj-B"}
        await index.rebuild(centroids, project_ids=project_ids)
        assert index._project_ids == ["proj-A", "proj-B"]

    @pytest.mark.asyncio
    async def test_rebuild_without_project_ids_defaults_to_none(self, index):
        centroids = {"c1": _random_emb(), "c2": _random_emb()}
        await index.rebuild(centroids)
        assert index._project_ids == [None, None]


class TestProjectFilteredSearch:
    @pytest.mark.asyncio
    async def test_search_without_filter_returns_all(self, index):
        """No filter = search all vectors (backward compatible)."""
        emb_a = np.array([1, 0, 0, 0], dtype=np.float32)
        emb_b = np.array([0, 1, 0, 0], dtype=np.float32)
        query = np.array([0.9, 0.1, 0, 0], dtype=np.float32)

        await index.upsert("c1", emb_a, project_id="proj-A")
        await index.upsert("c2", emb_b, project_id="proj-B")

        results = index.search(query, k=5, threshold=0.0)
        assert len(results) == 2
        assert results[0][0] == "c1"  # closest to query

    @pytest.mark.asyncio
    async def test_search_with_project_filter(self, index):
        """Filter restricts search to matching project."""
        emb_a = np.array([1, 0, 0, 0], dtype=np.float32)
        emb_b = np.array([0.95, 0.05, 0, 0], dtype=np.float32)  # very similar to a
        query = np.array([0.9, 0.1, 0, 0], dtype=np.float32)

        await index.upsert("c1", emb_a, project_id="proj-A")
        await index.upsert("c2", emb_b, project_id="proj-B")

        # Filter to proj-B only — should only return c2
        results = index.search(query, k=5, threshold=0.0, project_filter="proj-B")
        assert len(results) == 1
        assert results[0][0] == "c2"

    @pytest.mark.asyncio
    async def test_search_with_filter_no_matches(self, index):
        """Filter to nonexistent project returns empty."""
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        results = index.search(_random_emb(), k=5, threshold=0.0, project_filter="proj-X")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_filter_none_entries_excluded(self, index):
        """Vectors with project_id=None are excluded when filter is set."""
        await index.upsert("c1", np.array([1, 0, 0, 0], dtype=np.float32), project_id=None)
        await index.upsert("c2", np.array([0.9, 0.1, 0, 0], dtype=np.float32), project_id="proj-A")
        query = np.array([1, 0, 0, 0], dtype=np.float32)

        results = index.search(query, k=5, threshold=0.0, project_filter="proj-A")
        assert len(results) == 1
        assert results[0][0] == "c2"


class TestCacheWithProjectIds:
    @pytest.mark.asyncio
    async def test_save_and_load_preserves_project_ids(self, index, tmp_path):
        """Cache round-trip preserves project_id data."""
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        await index.upsert("c2", _random_emb(), project_id="proj-B")

        cache_path = tmp_path / "test_index.pkl"
        await index.save_cache(cache_path)

        # Load into fresh index
        new_index = EmbeddingIndex(dim=4)
        loaded = await new_index.load_cache(cache_path)
        assert loaded
        assert new_index.size == 2
        assert new_index._project_ids == ["proj-A", "proj-B"]

    @pytest.mark.asyncio
    async def test_load_legacy_cache_without_project_ids(self, index, tmp_path):
        """Loading a cache from before ADR-005 (no project_ids) should work."""
        import pickle

        # Simulate legacy cache format (no project_ids key)
        legacy_data = {
            "matrix": np.random.randn(2, 4).astype(np.float32),
            "ids": ["c1", "c2"],
        }
        cache_path = tmp_path / "legacy.pkl"
        with open(cache_path, "wb") as f:
            pickle.dump(legacy_data, f)

        loaded = await index.load_cache(cache_path, max_age_seconds=9999)
        assert loaded
        assert index.size == 2
        assert index._project_ids == [None, None]  # default to None


class TestSnapshotRestore:
    @pytest.mark.asyncio
    async def test_snapshot_includes_project_ids(self, index):
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        snap = await index.snapshot()
        assert hasattr(snap, "project_ids")
        assert snap.project_ids == ["proj-A"]

    @pytest.mark.asyncio
    async def test_restore_restores_project_ids(self, index):
        await index.upsert("c1", _random_emb(), project_id="proj-A")
        snap = await index.snapshot()

        # Mutate
        await index.upsert("c2", _random_emb(), project_id="proj-B")
        assert index.size == 2

        # Restore
        await index.restore(snap)
        assert index.size == 1
        assert index._project_ids == ["proj-A"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/taxonomy/test_embedding_index_project.py -v
```
Expected: FAIL — `project_id` parameter not accepted, `_project_ids` not defined

- [ ] **Step 3: Update IndexSnapshot dataclass**

```python
@dataclass
class IndexSnapshot:
    matrix: np.ndarray
    ids: list[str]
    project_ids: list[str | None] = field(default_factory=list)  # ADR-005
```

- [ ] **Step 4: Update __init__**

```python
def __init__(self, dim: int = 384):
    self._dim = dim
    self._lock = asyncio.Lock()
    self._matrix: np.ndarray = np.empty((0, dim), dtype=np.float32)
    self._ids: list[str] = []
    self._project_ids: list[str | None] = []  # ADR-005: parallel array
```

- [ ] **Step 5: Update search() with project_filter**

```python
def search(
    self, embedding: np.ndarray, k: int = 5, threshold: float = 0.72,
    project_filter: str | None = None,  # ADR-005
) -> list[tuple[str, float]]:
    matrix = self._matrix
    ids = self._ids
    project_ids = self._project_ids  # ADR-005

    if len(ids) == 0:
        return []

    query = embedding.astype(np.float32).ravel()
    norm = np.linalg.norm(query)
    if norm < 1e-9:
        return []
    query = query / norm

    scores = matrix @ query

    # ADR-005: project filter mask
    if project_filter is not None and project_ids:
        project_mask = np.array(
            [pid == project_filter for pid in project_ids],
            dtype=bool,
        )
        scores = np.where(project_mask, scores, -1.0)  # mask out non-matching

    # ... rest of existing threshold + top-k logic unchanged ...
```

- [ ] **Step 6: Update upsert() with project_id**

```python
async def upsert(
    self, cluster_id: str, embedding: np.ndarray,
    project_id: str | None = None,  # ADR-005
) -> None:
    emb = embedding.astype(np.float32).ravel()
    norm = np.linalg.norm(emb)
    if norm < 1e-9:
        return
    emb = emb / norm

    async with self._lock:
        ids = list(self._ids)
        project_ids = list(self._project_ids)  # ADR-005

        if cluster_id in ids:
            idx = ids.index(cluster_id)
            matrix = self._matrix.copy()
            matrix[idx] = emb
            project_ids[idx] = project_id  # ADR-005: update project
        else:
            ids.append(cluster_id)
            project_ids.append(project_id)  # ADR-005
            if self._matrix.shape[0] == 0:
                matrix = emb.reshape(1, -1)
            else:
                matrix = np.vstack([self._matrix, emb.reshape(1, -1)])

        self._matrix = matrix
        self._ids = ids
        self._project_ids = project_ids  # ADR-005
```

- [ ] **Step 7: Update remove()**

```python
async def remove(self, cluster_id: str) -> None:
    async with self._lock:
        if cluster_id not in self._ids:
            return
        ids = list(self._ids)
        project_ids = list(self._project_ids)  # ADR-005
        idx = ids.index(cluster_id)
        ids.pop(idx)
        project_ids.pop(idx)  # ADR-005
        matrix = np.delete(self._matrix, idx, axis=0)

        self._matrix = matrix
        self._ids = ids
        self._project_ids = project_ids  # ADR-005
```

- [ ] **Step 8: Update rebuild()**

```python
async def rebuild(
    self, centroids: dict[str, np.ndarray],
    project_ids: dict[str, str | None] | None = None,  # ADR-005
) -> None:
    if not centroids:
        async with self._lock:
            self._matrix = np.empty((0, self._dim), dtype=np.float32)
            self._ids = []
            self._project_ids = []  # ADR-005
        return

    ids = list(centroids.keys())
    p_ids = [project_ids.get(cid) if project_ids else None for cid in ids]  # ADR-005
    rows = []
    for cid in ids:
        emb = centroids[cid].astype(np.float32).ravel()
        norm = np.linalg.norm(emb)
        if norm > 1e-9:
            rows.append(emb / norm)
        else:
            rows.append(np.zeros(self._dim, dtype=np.float32))

    matrix = np.vstack(rows)

    async with self._lock:
        self._matrix = matrix
        self._ids = ids
        self._project_ids = p_ids  # ADR-005

    logger.info("EmbeddingIndex rebuilt: %d centroids", len(ids))
```

- [ ] **Step 9: Update snapshot() and restore()**

```python
async def snapshot(self) -> IndexSnapshot:
    async with self._lock:
        return IndexSnapshot(
            matrix=self._matrix.copy(),
            ids=list(self._ids),
            project_ids=list(self._project_ids),  # ADR-005
        )

async def restore(self, snapshot: IndexSnapshot) -> None:
    async with self._lock:
        self._matrix = snapshot.matrix.copy()
        self._ids = list(snapshot.ids)
        self._project_ids = list(snapshot.project_ids) if snapshot.project_ids else [None] * len(snapshot.ids)  # ADR-005
```

- [ ] **Step 10: Update save_cache() and load_cache()**

```python
async def save_cache(self, cache_path: Path) -> None:
    import pickle
    async with self._lock:
        data = {
            "matrix": self._matrix,
            "ids": list(self._ids),
            "project_ids": list(self._project_ids),  # ADR-005
        }
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
        logger.info("EmbeddingIndex cache saved: %d entries → %s", len(data["ids"]), cache_path)
    except Exception as exc:
        logger.warning("EmbeddingIndex cache save failed: %s", exc)

async def load_cache(self, cache_path: Path, max_age_seconds: int = 3600) -> bool:
    import pickle
    if not cache_path.exists():
        return False
    age = time.time() - cache_path.stat().st_mtime
    if age > max_age_seconds:
        logger.info("EmbeddingIndex cache stale (%.0fs old, max %ds)", age, max_age_seconds)
        return False
    try:
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        async with self._lock:
            self._matrix = data["matrix"]
            self._ids = data["ids"]
            # ADR-005: backward compat with legacy cache (no project_ids key)
            self._project_ids = data.get("project_ids", [None] * len(self._ids))
        logger.info("EmbeddingIndex loaded from cache: %d entries (%.0fs old)", len(self._ids), age)
        return True
    except Exception as exc:
        logger.warning("EmbeddingIndex cache load failed: %s", exc)
        return False
```

- [ ] **Step 11: Run all tests**

```bash
pytest tests/taxonomy/test_embedding_index_project.py -v
pytest --tb=short -q  # full suite
```
Expected: All pass

- [ ] **Step 12: Run ruff**

```bash
ruff check app/services/taxonomy/embedding_index.py
```

- [ ] **Step 13: Commit**

```bash
git add backend/app/services/taxonomy/embedding_index.py backend/tests/taxonomy/test_embedding_index_project.py
git commit -m "feat(taxonomy): add project_filter to EmbeddingIndex (ADR-005)

Vectors tagged with project_id via parallel _project_ids array.
search() gains project_filter parameter — masks matrix before cosine.
All methods updated: upsert, remove, rebuild, snapshot, restore, cache.
Backward compatible: legacy caches load with project_id=None defaults."
```

---

### Task 2: Update callers to pass project_id on upsert/rebuild

**Files:**
- Modify: `backend/app/services/taxonomy/engine.py` (upsert calls)
- Modify: `backend/app/services/taxonomy/cold_path.py` (rebuild call)
- Modify: `backend/app/main.py` (startup rebuild)

- [ ] **Step 1: Update engine.py upsert calls**

In `process_optimization()`, where `await self._embedding_index.upsert(cluster.id, embedding)` is called, add `project_id`:

```python
# Determine project_id from cluster ancestry
_cluster_project_id = None  # TODO Phase 2: resolve from tree
await self._embedding_index.upsert(cluster.id, embedding, project_id=_cluster_project_id)
```

For now, pass `None` — project resolution comes in Phase 2. The infrastructure is ready.

- [ ] **Step 2: Update cold_path.py rebuild call**

In `execute_cold_path()` and `execute_umap_projection()`, the embedding index rebuild passes centroids. Add project_ids:

```python
# For now, all existing clusters get project_id=None (Phase 2 will populate)
await engine._embedding_index.rebuild(_centroids, project_ids=None)
```

- [ ] **Step 3: Update main.py startup rebuild**

In the lifespan where the embedding index is rebuilt from DB:

```python
await engine.embedding_index.rebuild(_centroids)  # existing
# No change needed — rebuild() defaults project_ids to None
```

- [ ] **Step 4: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/engine.py backend/app/services/taxonomy/cold_path.py backend/app/main.py
git commit -m "feat(taxonomy): wire project_id=None into embedding index callers (ADR-005)

All upsert/rebuild calls now pass project_id (None for Phase 1).
Phase 2 will populate with actual project IDs from tree ancestry."
```

---

### Task 3: E2E validation — restart and verify cache compatibility

- [ ] **Step 1: Delete old cache to force rebuild**

```bash
rm -f data/embedding_index.pkl
```

- [ ] **Step 2: Restart server**

```bash
./init.sh restart
```

- [ ] **Step 3: Verify rebuild includes project_ids**

```bash
grep "EmbeddingIndex" data/backend.log | head -5
```
Expected: "EmbeddingIndex rebuilt: N centroids" (rebuilt from DB, not cache)

- [ ] **Step 4: Verify cache saves with project_ids**

```bash
python3 -c "
import pickle
with open('data/embedding_index.pkl', 'rb') as f:
    data = pickle.load(f)
print(f'Entries: {len(data[\"ids\"])}')
print(f'Has project_ids: {\"project_ids\" in data}')
print(f'Project IDs sample: {data.get(\"project_ids\", [])[:3]}')
"
```
Expected: `Has project_ids: True`, all None (Phase 1)

- [ ] **Step 5: Run full test suite**

```bash
cd backend && source .venv/bin/activate && pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix: ADR-005 embedding index E2E validation adjustments"
```
