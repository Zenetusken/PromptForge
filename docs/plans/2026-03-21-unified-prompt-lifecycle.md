# Unified Prompt Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge PatternFamily + TaxonomyNode into a unified PromptCluster model with in-memory embedding search, auto-lifecycle management, and coherent frontend navigation across 6 phases.

**Architecture:** Evolutionary convergence — evolve the existing taxonomy engine (10 modules, ~3,900 LOC) by extracting focused sub-modules from engine.py (2,098 LOC), introducing a numpy-based embedding index, and layering a prompt lifecycle service on top. Frontend unifies three navigation surfaces (History, ClusterNavigator, Topology) on a single entity type.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async + aiosqlite (SQLite), Alembic, numpy, sentence-transformers (all-MiniLM-L6-v2 384-dim), SvelteKit 2 (Svelte 5 runes), TailwindCSS 4, Three.js

**Spec:** `docs/specs/2026-03-21-unified-prompt-lifecycle-design.md`

---

## File Structure

### New files

| File | Responsibility | Phase |
|------|---------------|-------|
| `backend/alembic/versions/xxxx_unified_prompt_cluster.py` | Alembic migration: create prompt_cluster, copy data, drop old tables | P1 |
| `backend/app/services/taxonomy/embedding_index.py` (~200 LOC) | In-memory numpy cosine search index | P2 |
| `backend/app/services/taxonomy/family_ops.py` (~400 LOC) | Family assignment, meta-pattern extraction/merge | P2 |
| `backend/app/services/taxonomy/matching.py` (~350 LOC) | match_prompt cascade, domain mapping, thresholds | P2 |
| `backend/app/services/prompt_lifecycle.py` (~400 LOC) | Auto-curation, state promotion, template registry | P3 |
| `backend/app/routers/clusters.py` (~250 LOC) | Unified cluster router (replaces taxonomy.py + patterns.py) | P1 |
| `backend/app/schemas/clusters.py` (~100 LOC) | Pydantic response models for cluster endpoints | P1 |
| `backend/tests/test_embedding_index.py` | Unit tests for numpy search index | P2 |
| `backend/tests/test_prompt_lifecycle.py` | Unit tests for lifecycle service | P3 |
| `backend/tests/test_clusters_router.py` | Router integration tests | P1 |
| `frontend/src/lib/stores/clusters.svelte.ts` | Unified cluster store (replaces patterns.svelte.ts) | P4 |
| `frontend/src/lib/api/clusters.ts` | Unified cluster API client (replaces patterns.ts + taxonomy.ts) | P4 |

### Modified files

| File | Changes | Phase |
|------|---------|-------|
| `backend/app/models.py:93-204` | Replace PatternFamily + TaxonomyNode + TaxonomySnapshot with PromptCluster | P1 |
| `backend/app/services/taxonomy/engine.py` | Slim to ~500 LOC orchestrator, delegate to family_ops/matching | P2 |
| `backend/app/services/taxonomy/__init__.py` | Export embedding_index singleton | P2 |
| `backend/app/main.py:20-150` | Update lifespan for new model, add lifecycle hooks | P3 |
| `backend/app/services/pipeline.py:310-340` | Add auto-injection pre-phase | P5 |
| `frontend/src/lib/components/layout/PatternNavigator.svelte` | Rename to ClusterNavigator, add state tabs + templates | P4 |
| `frontend/src/lib/components/layout/Inspector.svelte` | State badges, cluster detail, promote/unarchive | P4 |
| `frontend/src/lib/components/taxonomy/SemanticTopology.svelte` | Use selectCluster(), state encoding via opacity/size/color | P4 |
| `frontend/src/lib/components/taxonomy/TopologyData.ts` | State-based node properties | P4 |
| `frontend/src/lib/components/layout/StatusBar.svelte` | Update to cluster terminology | P4 |
| `frontend/src/lib/components/layout/Navigator.svelte` | Update family_id → cluster_id references | P4 |
| `frontend/src/routes/app/+page.svelte` | Update store imports, SSE handler | P4 |

### Deleted files (after migration verified)

| File | Replaced by | Phase |
|------|------------|-------|
| `backend/app/routers/taxonomy.py` | `clusters.py` + 301 redirects | P1 |
| `backend/app/routers/patterns.py` | `clusters.py` + 301 redirects | P1 |
| `backend/app/schemas/taxonomy.py` | `schemas/clusters.py` | P1 |
| `frontend/src/lib/stores/patterns.svelte.ts` | `clusters.svelte.ts` | P4 |
| `frontend/src/lib/api/patterns.ts` | `clusters.ts` | P4 |
| `frontend/src/lib/api/taxonomy.ts` | `clusters.ts` | P4 |

---

## Phase 1: Data Migration + PromptCluster Model + API Rename

### Task 1.1: PromptCluster SQLAlchemy Model

**Files:**
- Modify: `backend/app/models.py:93-204`
- Test: `backend/tests/taxonomy/test_models.py`

- [ ] **Step 1: Write failing test for PromptCluster model**

```python
# backend/tests/taxonomy/test_models.py — add at end

def test_prompt_cluster_schema(tmp_engine):
    """PromptCluster table has all required columns."""
    from sqlalchemy import inspect
    insp = inspect(tmp_engine)
    columns = {c["name"] for c in insp.get_columns("prompt_cluster")}
    required = {
        "id", "parent_id", "label", "state", "domain", "task_type",
        "centroid_embedding", "member_count", "usage_count", "avg_score",
        "coherence", "separation", "stability", "persistence",
        "umap_x", "umap_y", "umap_z", "color_hex",
        "preferred_strategy", "prune_flag_count", "last_used_at",
        "promoted_at", "archived_at", "created_at", "updated_at",
    }
    assert required.issubset(columns)


def test_prompt_cluster_state_values():
    """State column accepts all lifecycle states."""
    from backend.app.models import PromptCluster
    valid = {"candidate", "active", "mature", "template", "archived"}
    for state in valid:
        c = PromptCluster(label="test", state=state, domain="general", task_type="general")
        assert c.state == state
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/taxonomy/test_models.py::test_prompt_cluster_schema -v`
Expected: FAIL — `PromptCluster` not defined or table not found

- [ ] **Step 3: Implement PromptCluster model**

Replace `PatternFamily` (lines 93-107) and `TaxonomyNode` (lines 138-179) in `backend/app/models.py` with:

```python
class PromptCluster(Base):
    """Unified prompt cluster — replaces PatternFamily + TaxonomyNode."""
    __tablename__ = "prompt_cluster"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    parent_id = Column(String, ForeignKey("prompt_cluster.id"), nullable=True, index=True)
    label = Column(String, nullable=False, default="")
    state = Column(String(20), nullable=False, default="active")  # candidate|active|mature|template|archived
    domain = Column(String(50), nullable=False, default="general")
    task_type = Column(String(50), nullable=False, default="general")

    centroid_embedding = Column(LargeBinary, nullable=True)
    member_count = Column(Integer, nullable=False, default=0)
    usage_count = Column(Integer, nullable=False, default=0)
    avg_score = Column(Float, nullable=True)

    coherence = Column(Float, nullable=True)
    separation = Column(Float, nullable=True)
    stability = Column(Float, nullable=True, default=0.0)
    persistence = Column(Float, nullable=True, default=0.5)

    umap_x = Column(Float, nullable=True)
    umap_y = Column(Float, nullable=True)
    umap_z = Column(Float, nullable=True)
    color_hex = Column(String(7), nullable=True)

    preferred_strategy = Column(String(50), nullable=True)
    prune_flag_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime, nullable=True)
    promoted_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    children = relationship("PromptCluster", backref=backref("parent", remote_side=[id]), lazy="select")
    meta_patterns = relationship("MetaPattern", back_populates="cluster", lazy="select")

    __table_args__ = (
        Index("ix_prompt_cluster_state", "state"),
        Index("ix_prompt_cluster_domain_state", "domain", "state"),
        Index("ix_prompt_cluster_persistence", "persistence"),
        Index("ix_prompt_cluster_created_at", created_at.desc()),
    )
```

Update `MetaPattern` (lines 110-119) — change `family_id` FK:
```python
class MetaPattern(Base):
    __tablename__ = "meta_pattern"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    cluster_id = Column(String, ForeignKey("prompt_cluster.id"), nullable=False, index=True)
    pattern_text = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=True)
    source_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=func.now())
    cluster = relationship("PromptCluster", back_populates="meta_patterns")
```

Update `OptimizationPattern` (lines 122-133) — rename `family_id` FK to `cluster_id`, keep `id` PK and all existing columns:
```python
class OptimizationPattern(Base):
    __tablename__ = "optimization_pattern"
    id = Column(Integer, primary_key=True, autoincrement=True)
    optimization_id = Column(String, ForeignKey("optimizations.id"), nullable=False)
    cluster_id = Column(String, ForeignKey("prompt_cluster.id"), nullable=False)
    meta_pattern_id = Column(String, ForeignKey("meta_pattern.id"), nullable=True)
    relationship = Column(String(20), nullable=False, default="source")
    similarity = Column(Float, nullable=True)
    __table_args__ = (
        Index("ix_optimization_pattern_opt_rel", "optimization_id", "relationship"),
        Index("ix_optimization_pattern_cluster", "cluster_id"),
    )
```

**Important:** Keep the autoincrement `id` PK — the existing code writes both "source" and "applied" relationships for the same (optimization_id, cluster_id) pair. A composite PK would break this. Keep `meta_pattern_id` — it is actively used by `pipeline.py` and `sampling_pipeline.py` to record which meta-pattern was applied.

Update `Optimization` (line 67) — rename FK:
```python
    cluster_id = Column(String, ForeignKey("prompt_cluster.id"), nullable=True)
```

Update `TaxonomySnapshot` (lines 182-204) — add legacy flag:
```python
    legacy = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: Sweep all renamed field references across backend**

The model changes rename `family_id` → `cluster_id` and `taxonomy_node_id` → `cluster_id`. Run a sweep across `backend/app/` to update all references. Key files that need updates:

| File | What to change |
|------|---------------|
| `services/pipeline.py` | `taxonomy_node_id` → `cluster_id`, `family_id` → `cluster_id` (5+ refs) |
| `services/sampling_pipeline.py` | `taxonomy_node_id` → `cluster_id`, `family_id` → `cluster_id` |
| `routers/optimize.py` | `family_id` → `cluster_id` in query filters |
| `routers/history.py` | `family_id` → `cluster_id`, `taxonomy_node_id` → `cluster_id` |
| `mcp_server.py` | `taxonomy_node_id` → `cluster_id` (4 refs) |
| `services/taxonomy/engine.py` | `PatternFamily` → `PromptCluster`, `family_id` → `cluster_id` throughout |
| `services/pattern_extractor.py` | `PatternFamily` → `PromptCluster`, `family_id` → `cluster_id` |
| `services/pattern_matcher.py` | `PatternFamily` → `PromptCluster`, `family_id` → `cluster_id` |
| `services/knowledge_graph.py` | `PatternFamily` → `PromptCluster`, `family_id` → `cluster_id` |

Run after sweep:
```bash
cd backend && grep -rn "family_id\|taxonomy_node_id\|PatternFamily" app/ --include="*.py" | grep -v __pycache__
```
Expected: No results (all references updated).

- [ ] **Step 5: Run full backend test suite to verify rename sweep**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: PASS — all references updated correctly. Fix any remaining import/attribute errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ backend/tests/
git commit -m "feat(models): add PromptCluster model, replace PatternFamily + TaxonomyNode"
```

---

### Task 1.2: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_unified_prompt_cluster.py`

- [ ] **Step 1: Generate migration stub**

Run: `cd backend && alembic revision --autogenerate -m "unified_prompt_cluster"`

- [ ] **Step 2: Edit migration to use create-copy-swap pattern**

The autogenerated migration will need manual editing. The upgrade function should:

1. Create `prompt_cluster` table with full schema
2. Copy `pattern_family` data: `INSERT INTO prompt_cluster SELECT ... FROM pattern_family` (map columns, set state='active' default)
3. For each pattern_family row with `taxonomy_node_id IS NOT NULL`: UPDATE prompt_cluster SET umap_x/y/z/color_hex/persistence/stability/coherence/separation/parent_id/state from matching taxonomy_node row. Apply state mapping: confirmed→active (or mature if thresholds met), candidate→candidate, retired→archived.
4. INSERT hierarchy-only taxonomy_nodes as new prompt_cluster rows (member_count=0)
5. Create `prompt_cluster_new` versions of optimization_pattern and meta_pattern with renamed FKs, copy data, drop old, rename
6. Rename Optimization.taxonomy_node_id → cluster_id, remap values
7. Add legacy=True column to taxonomy_snapshot, UPDATE SET legacy=True
8. Drop taxonomy_nodes table, drop pattern_family table
9. Create all new indices

The downgrade function should note: "Manual restore from backup required. Run: cp data/synthesis.db.pre-migration data/synthesis.db"

- [ ] **Step 3: Create backup and run migration**

```bash
cp data/synthesis.db data/synthesis.db.pre-migration
cd backend && alembic upgrade head
```

- [ ] **Step 4: Verify migration**

```bash
cd backend && python -c "
from sqlalchemy import create_engine, inspect
e = create_engine('sqlite:///../data/synthesis.db')
insp = inspect(e)
tables = insp.get_table_names()
assert 'prompt_cluster' in tables, 'prompt_cluster missing'
assert 'pattern_family' not in tables, 'pattern_family not dropped'
assert 'taxonomy_nodes' not in tables, 'taxonomy_nodes not dropped'
cols = {c['name'] for c in insp.get_columns('prompt_cluster')}
assert 'state' in cols, 'state column missing'
assert 'prune_flag_count' in cols, 'prune_flag_count missing'
print(f'Migration OK — prompt_cluster has {len(cols)} columns')
"
```

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/
git commit -m "feat(migration): create-copy-swap to unified prompt_cluster table"
```

---

### Task 1.3: Cluster Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/clusters.py`

- [ ] **Step 1: Write schemas**

```python
# backend/app/schemas/clusters.py
"""Pydantic response models for the unified cluster API."""

from datetime import datetime
from pydantic import BaseModel


class ClusterNode(BaseModel):
    """Single cluster in tree/list responses."""
    id: str
    parent_id: str | None = None
    label: str
    state: str
    domain: str
    task_type: str
    persistence: float | None = None
    coherence: float | None = None
    separation: float | None = None
    stability: float | None = None
    member_count: int = 0
    usage_count: int = 0
    avg_score: float | None = None
    color_hex: str | None = None
    umap_x: float | None = None
    umap_y: float | None = None
    umap_z: float | None = None
    preferred_strategy: str | None = None
    created_at: datetime | None = None


class ClusterTreeResponse(BaseModel):
    nodes: list[ClusterNode]


class MetaPatternItem(BaseModel):
    id: str
    pattern_text: str
    source_count: int


class LinkedOptimization(BaseModel):
    id: str
    trace_id: str
    raw_prompt: str
    intent_label: str | None = None
    overall_score: float | None = None
    strategy_used: str | None = None
    created_at: datetime | None = None


class ClusterDetail(BaseModel):
    """Full cluster detail for Inspector."""
    id: str
    parent_id: str | None = None
    label: str
    state: str
    domain: str
    task_type: str
    member_count: int
    usage_count: int
    avg_score: float | None = None
    coherence: float | None = None
    separation: float | None = None
    preferred_strategy: str | None = None
    promoted_at: datetime | None = None
    meta_patterns: list[MetaPatternItem]
    optimizations: list[LinkedOptimization]
    children: list[ClusterNode] | None = None
    breadcrumb: list[ClusterNode] | None = None


class ClusterStats(BaseModel):
    q_system: float | None = None
    q_coherence: float | None = None
    q_separation: float | None = None
    q_coverage: float | None = None
    q_dbcv: float | None = None
    total_clusters: int = 0
    nodes: dict | None = None
    last_warm_path: datetime | None = None
    last_cold_path: datetime | None = None
    warm_path_age: int = 0
    q_history: list[float] | None = None
    q_sparkline: list[float] | None = None


class ClusterMatchResponse(BaseModel):
    match: dict | None = None


class ReclusterResponse(BaseModel):
    status: str
    snapshot_id: str | None = None
    q_system: float | None = None
    nodes_created: int = 0
    nodes_updated: int = 0
    umap_fitted: bool = False


class ClusterUpdateRequest(BaseModel):
    intent_label: str | None = None
    domain: str | None = None
    state: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/clusters.py
git commit -m "feat(schemas): add Pydantic models for unified cluster API"
```

---

### Task 1.4: Unified Clusters Router

**Files:**
- Create: `backend/app/routers/clusters.py`
- Create: `backend/tests/test_clusters_router.py`
- Modify: `backend/app/main.py` — swap router imports

- [ ] **Step 1: Write failing router test**

```python
# backend/tests/test_clusters_router.py
"""Tests for the unified clusters router."""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_cluster_tree(client):
    resp = await client.get("/api/clusters/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data


@pytest.mark.asyncio
async def test_get_cluster_stats(client):
    resp = await client.get("/api/clusters/stats")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_legacy_taxonomy_tree_redirect(client):
    resp = await client.get("/api/taxonomy/tree", follow_redirects=False)
    assert resp.status_code == 301
    assert "/api/clusters/tree" in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_legacy_patterns_families_redirect(client):
    resp = await client.get("/api/patterns/families", follow_redirects=False)
    assert resp.status_code == 301
    assert "/api/clusters" in resp.headers.get("location", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_clusters_router.py -v`
Expected: FAIL — endpoints not found

- [ ] **Step 3: Implement clusters router**

Create `backend/app/routers/clusters.py` — port endpoints from `taxonomy.py` (114 LOC) and `patterns.py` (290 LOC) into a single router. Use `PromptCluster` model everywhere. Key endpoints:

- `GET /api/clusters/tree` — flat node list with optional `min_persistence` filter
- `GET /api/clusters/{id}` — detail with children, breadcrumb, meta_patterns, linked optimizations
- `GET /api/clusters/stats` — Q_system metrics + sparkline
- `GET /api/clusters/templates` — state=template clusters sorted by avg_score
- `PATCH /api/clusters/{id}` — update label, domain, state
- `POST /api/clusters/match` — pattern match endpoint
- `POST /api/clusters/recluster` — cold path trigger

Add 301 redirect routes for legacy paths:
```python
from fastapi.responses import RedirectResponse

@router.get("/api/taxonomy/tree")
async def legacy_taxonomy_tree(request: Request):
    return RedirectResponse(url=f"/api/clusters/tree?{request.query_params}", status_code=301)
```

- [ ] **Step 4: Update main.py router registration**

In `backend/app/main.py`, replace:
```python
from app.routers import taxonomy, patterns
app.include_router(taxonomy.router)
app.include_router(patterns.router)
```
With:
```python
from app.routers import clusters
app.include_router(clusters.router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_clusters_router.py -v`
Expected: PASS

- [ ] **Step 6: Run existing taxonomy + pattern router tests (regression)**

Run: `cd backend && python -m pytest tests/test_taxonomy_router.py tests/test_patterns_router.py -v`
Expected: These may need import updates. Fix any failures from renamed model fields.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/clusters.py backend/app/main.py backend/tests/test_clusters_router.py
git commit -m "feat(api): add unified /api/clusters router with legacy 301 redirects"
```

---

### Task 1.5: Delete Old Routers and Schemas

**Files:**
- Delete: `backend/app/routers/taxonomy.py`
- Delete: `backend/app/routers/patterns.py`
- Delete: `backend/app/schemas/taxonomy.py`
- Update: `backend/tests/test_taxonomy_router.py` — retarget to new endpoints
- Update: `backend/tests/test_patterns_router.py` — retarget to new endpoints

- [ ] **Step 1: Update existing tests to use new endpoints**

Rewrite test imports and endpoint paths in both test files. The tests should now hit `/api/clusters/*` directly (not via 301 redirect).

- [ ] **Step 2: Delete old files**

```bash
rm backend/app/routers/taxonomy.py backend/app/routers/patterns.py backend/app/schemas/taxonomy.py
```

- [ ] **Step 3: Run full backend test suite**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: All tests pass. Fix any import errors from deleted files.

- [ ] **Step 4: Commit**

```bash
git add -A backend/app/routers/ backend/app/schemas/ backend/tests/
git commit -m "refactor: remove old taxonomy + patterns routers, consolidate into clusters"
```

---

## Phase 2: Engine Decomposition + Embedding Index

### Task 2.1: Embedding Index

**Files:**
- Create: `backend/app/services/taxonomy/embedding_index.py`
- Create: `backend/tests/test_embedding_index.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_embedding_index.py
"""Tests for the in-memory numpy embedding index."""
import numpy as np
import pytest
from backend.app.services.taxonomy.embedding_index import EmbeddingIndex


@pytest.fixture
def index():
    return EmbeddingIndex(dim=384)


def _rand_emb(dim=384):
    v = np.random.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def test_empty_search(index):
    results = index.search(_rand_emb(), k=5)
    assert results == []


@pytest.mark.asyncio
async def test_upsert_and_search(index):
    emb = _rand_emb()
    await index.upsert("a", emb)
    results = index.search(emb, k=1, threshold=0.5)
    assert len(results) == 1
    assert results[0][0] == "a"
    assert results[0][1] > 0.99  # near-identical


@pytest.mark.asyncio
async def test_remove(index):
    emb = _rand_emb()
    await index.upsert("a", emb)
    await index.remove("a")
    results = index.search(emb, k=1, threshold=0.5)
    assert results == []


@pytest.mark.asyncio
async def test_threshold_filtering(index):
    e1 = _rand_emb()
    e2 = _rand_emb()  # random = ~0 cosine to e1
    await index.upsert("a", e1)
    await index.upsert("b", e2)
    results = index.search(e1, k=5, threshold=0.8)
    assert len(results) == 1
    assert results[0][0] == "a"


@pytest.mark.asyncio
async def test_rebuild(index):
    e1, e2 = _rand_emb(), _rand_emb()
    await index.upsert("old", _rand_emb())
    await index.rebuild({"a": e1, "b": e2})
    results = index.search(e1, k=5, threshold=0.5)
    ids = [r[0] for r in results]
    assert "a" in ids
    assert "old" not in ids


@pytest.mark.asyncio
async def test_scale_500_clusters(index):
    """Search over 500 clusters completes in <10ms."""
    import time
    for i in range(500):
        await index.upsert(f"c{i}", _rand_emb())
    query = _rand_emb()
    start = time.perf_counter()
    results = index.search(query, k=5, threshold=0.3)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 10, f"Search took {elapsed_ms:.1f}ms, expected <10ms"
    assert len(results) <= 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_embedding_index.py -v`
Expected: FAIL — `embedding_index` module not found

- [ ] **Step 3: Implement EmbeddingIndex**

```python
# backend/app/services/taxonomy/embedding_index.py
"""In-memory numpy cosine search index for PromptCluster centroids.

Thread-safe: mutations gated by asyncio.Lock. Reads operate on immutable
snapshots (copy-on-write). At 2000 clusters (384-dim), search is ~3ms.
"""

import asyncio
import logging
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingIndex:
    """In-memory embedding search index for PromptCluster centroids."""

    def __init__(self, dim: int = 384):
        self._dim = dim
        self._lock = asyncio.Lock()
        # Immutable snapshots — replaced atomically on mutation
        self._matrix: np.ndarray = np.empty((0, dim), dtype=np.float32)
        self._ids: list[str] = []

    @property
    def size(self) -> int:
        return len(self._ids)

    def search(
        self, embedding: np.ndarray, k: int = 5, threshold: float = 0.72
    ) -> list[tuple[str, float]]:
        """Top-k cosine search. Lock-free — reads current snapshot.

        Returns list of (cluster_id, cosine_similarity) sorted descending.
        """
        matrix = self._matrix  # snapshot reference
        ids = self._ids
        if len(ids) == 0:
            return []

        # Normalize query
        query = embedding.astype(np.float32).ravel()
        norm = np.linalg.norm(query)
        if norm < 1e-9:
            return []
        query = query / norm

        # Cosine similarity via matmul (matrix rows are L2-normalized)
        scores = matrix @ query  # (n,)

        # Filter by threshold
        mask = scores >= threshold
        if not mask.any():
            return []

        # Top-k via argpartition
        valid_indices = np.where(mask)[0]
        valid_scores = scores[valid_indices]

        if len(valid_indices) <= k:
            top_indices = valid_indices[np.argsort(-valid_scores)]
        else:
            partition_idx = np.argpartition(-valid_scores, k)[:k]
            top_indices = valid_indices[partition_idx]
            top_scores = scores[top_indices]
            top_indices = top_indices[np.argsort(-top_scores)]

        return [(ids[i], float(scores[i])) for i in top_indices]

    async def upsert(self, cluster_id: str, embedding: np.ndarray) -> None:
        """Insert or update a single centroid. Creates new snapshot."""
        emb = embedding.astype(np.float32).ravel()
        norm = np.linalg.norm(emb)
        if norm < 1e-9:
            return
        emb = emb / norm

        async with self._lock:
            ids = list(self._ids)
            if cluster_id in ids:
                idx = ids.index(cluster_id)
                matrix = self._matrix.copy()
                matrix[idx] = emb
            else:
                ids.append(cluster_id)
                if self._matrix.shape[0] == 0:
                    matrix = emb.reshape(1, -1)
                else:
                    matrix = np.vstack([self._matrix, emb.reshape(1, -1)])

            # Atomic swap
            self._matrix = matrix
            self._ids = ids

    async def remove(self, cluster_id: str) -> None:
        """Remove a centroid from the index. Creates new snapshot."""
        async with self._lock:
            if cluster_id not in self._ids:
                return
            ids = list(self._ids)
            idx = ids.index(cluster_id)
            ids.pop(idx)
            matrix = np.delete(self._matrix, idx, axis=0)

            self._matrix = matrix
            self._ids = ids

    async def rebuild(self, centroids: dict[str, np.ndarray]) -> None:
        """Full rebuild from scratch (cold path). Acquires lock."""
        if not centroids:
            async with self._lock:
                self._matrix = np.empty((0, self._dim), dtype=np.float32)
                self._ids = []
            return

        ids = list(centroids.keys())
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

        logger.info("EmbeddingIndex rebuilt: %d centroids", len(ids))
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_embedding_index.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/embedding_index.py backend/tests/test_embedding_index.py
git commit -m "feat(taxonomy): add in-memory numpy EmbeddingIndex with O(1) search"
```

---

### Task 2.2: Extract family_ops.py from engine.py

**Files:**
- Create: `backend/app/services/taxonomy/family_ops.py`
- Modify: `backend/app/services/taxonomy/engine.py:1492-1850`

- [ ] **Step 1: Extract functions**

Move from `engine.py` to `family_ops.py`:
- `_assign_family()` (engine.py:1492) — rename internal PatternFamily refs to PromptCluster
- `_extract_meta_patterns()` (engine.py:1627)
- `_merge_meta_pattern()` (engine.py:1703)
- `_compute_pattern_centroid()` (engine.py:1781)

These functions take `self` (engine) — refactor to accept explicit dependencies (db session, embedding_index, provider) rather than accessing `self.*` directly.

- [ ] **Step 2: Update engine.py to import from family_ops**

Replace the extracted method bodies in `engine.py` with delegation calls:

```python
from .family_ops import assign_family, extract_meta_patterns, merge_meta_pattern

# In process_optimization():
family = await assign_family(db, self._embedding_index, embedding, optimization, self._lock)
```

- [ ] **Step 3: Run existing taxonomy tests (regression)**

Run: `cd backend && python -m pytest tests/taxonomy/ -v`
Expected: ALL PASS — behavior unchanged

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/taxonomy/family_ops.py backend/app/services/taxonomy/engine.py
git commit -m "refactor(taxonomy): extract family_ops from engine.py (~400 LOC)"
```

---

### Task 2.3: Extract matching.py from engine.py

**Files:**
- Create: `backend/app/services/taxonomy/matching.py`
- Modify: `backend/app/services/taxonomy/engine.py:276-560`

- [ ] **Step 1: Extract functions**

Move from `engine.py` to `matching.py`:
- `match_prompt()` (engine.py:276) — refactor to use EmbeddingIndex instead of full-table scan
- `map_domain()` (engine.py:1378)
- Adaptive threshold computation helpers
- `_build_breadcrumb()` (engine.py:1847)

Key change: `match_prompt()` replaces `select(PatternFamily).where(...)` with `self._embedding_index.search()`.

- [ ] **Step 2: Update engine.py to delegate**

```python
from .matching import match_prompt, map_domain
```

- [ ] **Step 3: Run existing match/domain tests (regression)**

Run: `cd backend && python -m pytest tests/taxonomy/test_domain_mapping.py tests/taxonomy/test_engine_hot_path.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/taxonomy/matching.py backend/app/services/taxonomy/engine.py
git commit -m "refactor(taxonomy): extract matching.py from engine.py (~350 LOC)"
```

---

### Task 2.4: Wire EmbeddingIndex into Engine Lifecycle

**Files:**
- Modify: `backend/app/services/taxonomy/__init__.py`
- Modify: `backend/app/services/taxonomy/engine.py`
- Modify: `backend/app/main.py:20-40`

- [ ] **Step 1: Add embedding_index to engine constructor**

```python
# In engine.py __init__:
from .embedding_index import EmbeddingIndex
self._embedding_index = EmbeddingIndex(dim=384)
```

- [ ] **Step 2: Warm-load index at startup in main.py lifespan**

After `set_engine(engine)`:
```python
# Warm-load embedding index
async with get_async_session() as db:
    clusters = (await db.execute(
        select(PromptCluster).where(PromptCluster.state != "archived")
    )).scalars().all()
    centroids = {}
    for c in clusters:
        if c.centroid_embedding:
            try:
                emb = np.frombuffer(c.centroid_embedding, dtype=np.float32)
                if emb.shape[0] == 384:
                    centroids[c.id] = emb
            except (ValueError, TypeError):
                continue
    await engine._embedding_index.rebuild(centroids)
    logger.info("EmbeddingIndex warm-loaded: %d centroids", len(centroids))
```

- [ ] **Step 3: Add index upsert/remove calls to hot/warm/cold paths**

In `family_ops.py` `assign_family()` — after creating/merging family: `await embedding_index.upsert(cluster_id, centroid)`
In warm path — after merge: `await self._embedding_index.upsert(...)`, after retire: `await self._embedding_index.remove(...)`
In cold path — after HDBSCAN: `await self._embedding_index.rebuild(centroids)`

- [ ] **Step 4: Run full taxonomy test suite**

Run: `cd backend && python -m pytest tests/taxonomy/ -v`
Expected: ALL PASS

- [ ] **Step 5: Verify engine.py is under 600 LOC**

Run: `wc -l backend/app/services/taxonomy/engine.py`
Expected: < 600

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/taxonomy/ backend/app/main.py
git commit -m "feat(taxonomy): wire EmbeddingIndex into engine hot/warm/cold paths"
```

---

## Phase 3: Prompt Lifecycle Service

### Task 3.1: Lifecycle Service — State Promotion + Curation

**Files:**
- Create: `backend/app/services/prompt_lifecycle.py`
- Create: `backend/tests/test_prompt_lifecycle.py`

- [ ] **Step 1: Write failing tests for state promotion**

```python
# backend/tests/test_prompt_lifecycle.py
import pytest
from backend.app.services.prompt_lifecycle import PromptLifecycleService

@pytest.mark.asyncio
async def test_promote_active_to_mature(db_session, make_cluster):
    """Cluster meeting thresholds promotes to mature."""
    cluster = await make_cluster(state="active", member_count=5, coherence=0.8, avg_score=7.5)
    svc = PromptLifecycleService()
    promoted = await svc.check_promotion(db_session, cluster.id)
    assert promoted == "mature"

@pytest.mark.asyncio
async def test_promote_mature_to_template(db_session, make_cluster):
    """Mature cluster with usage promotes to template."""
    cluster = await make_cluster(state="mature", usage_count=3, avg_score=7.8)
    svc = PromptLifecycleService()
    promoted = await svc.check_promotion(db_session, cluster.id)
    assert promoted == "template"

@pytest.mark.asyncio
async def test_no_promote_below_threshold(db_session, make_cluster):
    """Active cluster below thresholds stays active."""
    cluster = await make_cluster(state="active", member_count=2, coherence=0.5, avg_score=5.0)
    svc = PromptLifecycleService()
    promoted = await svc.check_promotion(db_session, cluster.id)
    assert promoted is None

@pytest.mark.asyncio
async def test_archive_stale_cluster(db_session, make_cluster):
    """Cluster with no activity for 90 days gets archived."""
    from datetime import datetime, timedelta
    old = datetime.utcnow() - timedelta(days=91)
    cluster = await make_cluster(state="active", updated_at=old, usage_count=0, last_used_at=old)
    svc = PromptLifecycleService()
    archived = await svc.curate(db_session)
    assert cluster.id in archived.get("archived", [])

@pytest.mark.asyncio
async def test_quality_prune_after_two_flags(db_session, make_cluster):
    """Low-score cluster archived after 2 consecutive flags."""
    cluster = await make_cluster(state="active", avg_score=3.0, member_count=4, prune_flag_count=1)
    svc = PromptLifecycleService()
    await svc.curate(db_session)
    # After curation, prune_flag_count should be 2, triggering archive
    assert cluster.state == "archived"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_prompt_lifecycle.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement PromptLifecycleService**

Create `backend/app/services/prompt_lifecycle.py` with:
- `check_promotion(db, cluster_id) -> str | None` — checks state transitions, returns new state or None
- `curate(db) -> dict` — runs dedup detection (cosine >= 0.90), stale detection (90 days + 0 usage), quality pruning (avg_score < 4.0, member_count >= 3, prune_flag_count tracking), returns summary dict
- `backfill_orphans(db, embedding_index) -> int` — batch-processes optimizations with null cluster_id
- `decay_usage(db) -> int` — temporal decay (usage_count * 0.9 for clusters with last_used_at > 30 days)

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_prompt_lifecycle.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/prompt_lifecycle.py backend/tests/test_prompt_lifecycle.py
git commit -m "feat: add PromptLifecycleService — state promotion, curation, decay"
```

---

### Task 3.2: Wire Lifecycle into Main.py

**Files:**
- Modify: `backend/app/main.py:128-150`

- [ ] **Step 1: Add lifecycle post-process hook**

In the taxonomy_changed event listener (after `engine.process_optimization()`):
```python
from app.services.prompt_lifecycle import PromptLifecycleService
lifecycle = PromptLifecycleService()
await lifecycle.check_promotion(db, optimization.cluster_id)
```

- [ ] **Step 2: Add lifecycle curation to warm path timer**

After `engine.run_warm_path()`:
```python
await lifecycle.curate(db)
await lifecycle.decay_usage(db)
```

- [ ] **Step 3: Add orphan backfill at startup**

In lifespan, after embedding index warm-load:
```python
orphans_linked = await lifecycle.backfill_orphans(db, engine._embedding_index)
logger.info("Backfill: %d orphan optimizations linked", orphans_linked)
```

- [ ] **Step 4: Run full backend test suite**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: wire lifecycle service into startup, hot path, and warm path timer"
```

---

## Phase 4: Frontend — Clusters Store + ClusterNavigator + Inspector

### Task 4.1: Unified Clusters API Client + Store

**Files:**
- Create: `frontend/src/lib/api/clusters.ts`
- Create: `frontend/src/lib/stores/clusters.svelte.ts`

- [ ] **Step 1: Create clusters.ts API client**

Port and merge from `patterns.ts` (69 LOC) + `taxonomy.ts` (84 LOC):
- `getClusterTree(minPersistence?): Promise<ClusterNode[]>`
- `getClusterStats(): Promise<ClusterStats>`
- `getClusterDetail(id): Promise<ClusterDetail>`
- `getClusterTemplates(): Promise<ClusterNode[]>`
- `matchPattern(text): Promise<ClusterMatchResponse>`
- `updateCluster(id, data): Promise<void>`
- `triggerRecluster(): Promise<ReclusterResponse>`
- `listClusters(params): Promise<PaginatedResponse<ClusterNode>>`

All hitting `/api/clusters/*` endpoints.

- [ ] **Step 2: Create clusters.svelte.ts store**

Port from `patterns.svelte.ts` (182 LOC) with renames:
- `selectedClusterId` replaces `selectedFamilyId`
- `clusterDetail` replaces `familyDetail`
- `selectCluster(id)` replaces `selectFamily(id)`
- Add: `templates = $state<ClusterNode[]>([])`
- Add: `loadTemplates()` method
- Add: `spawnTemplate(clusterId)` method — fetches detail, pre-fills forge store with highest-scoring member's optimized_prompt + preferred_strategy
- Preserve: paste detection, SSE invalidation, generation counters

- [ ] **Step 3: Delete old files**

```bash
rm frontend/src/lib/api/patterns.ts frontend/src/lib/api/taxonomy.ts
rm frontend/src/lib/stores/patterns.svelte.ts
```

- [ ] **Step 4: Update all imports across frontend**

Search and replace across all files that import from the deleted modules:
- `$lib/stores/patterns.svelte` → `$lib/stores/clusters.svelte`
- `$lib/api/patterns` → `$lib/api/clusters`
- `$lib/api/taxonomy` → `$lib/api/clusters`
- `patternsStore` → `clustersStore`
- `selectedFamilyId` → `selectedClusterId`
- `selectFamily` → `selectCluster`
- `familyDetail` → `clusterDetail`
- `invalidateTaxonomy` → `invalidateClusters`

Files to update: `Inspector.svelte`, `Navigator.svelte`, `PatternNavigator.svelte`, `SemanticTopology.svelte`, `StatusBar.svelte`, `+page.svelte`, `forge.svelte.ts`, `PromptEdit.svelte`

- [ ] **Step 5: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/
git commit -m "feat(frontend): unified clusters store + API client, replace patterns/taxonomy"
```

---

### Task 4.2: ClusterNavigator (rename PatternNavigator)

**Files:**
- Modify: `frontend/src/lib/components/layout/PatternNavigator.svelte` → rename to `ClusterNavigator.svelte`

- [ ] **Step 1: Rename file**

```bash
mv frontend/src/lib/components/layout/PatternNavigator.svelte frontend/src/lib/components/layout/ClusterNavigator.svelte
```

- [ ] **Step 2: Add state filter tabs**

At the top of the navigator content, add filter tabs (active | mature | template | archived):
- 0px border-radius (flat, sharp — brand compliance)
- Active tab: `color-mix(var(--color-neon-cyan) 8%, transparent)` with 1px cyan border
- Tab height: 20px, font: text-[10px], font-weight: 600
- Filtering: `filteredClusters = $derived(clusters.filter(c => !stateFilter || c.state === stateFilter))`

- [ ] **Step 3: Add "Proven Templates" section**

When `stateFilter === null` (no filter) or `stateFilter === 'template'`:
- Section heading: `PROVEN TEMPLATES` (Syne, 11px, uppercase, letter-spacing 0.1em, weight 700)
- List template-state clusters sorted by avg_score DESC
- Each shows: label, domain badge, avg_score, member_count, preferred_strategy
- "Use template" button: `.btn-outline-primary`, 20px height, text-[10px]
- Button click: `clustersStore.spawnTemplate(cluster.id)`

- [ ] **Step 4: Update imports in Navigator.svelte and EditorGroups.svelte**

```svelte
import ClusterNavigator from './ClusterNavigator.svelte';
```

- [ ] **Step 5: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/lib/components/layout/
git commit -m "feat(ui): rename PatternNavigator to ClusterNavigator, add state tabs + templates"
```

---

### Task 4.3: Inspector State Badges + Cluster Detail

**Files:**
- Modify: `frontend/src/lib/components/layout/Inspector.svelte`

- [ ] **Step 1: Add state badge to cluster detail header**

After the domain badge, add a state badge:
```svelte
<span
  class="state-badge"
  style="color: {stateColor(cluster.state)}; border-color: {stateColor(cluster.state)};"
>{cluster.state}</span>
```

State color mapping (add to `$lib/utils/colors.ts`):
```typescript
export function stateColor(state: string): string {
  const map: Record<string, string> = {
    candidate: '#7a7a9e',
    active: '#4d8eff',
    mature: '#a855f7',
    template: '#00e5ff',
    archived: '#2a2a3e',
  };
  return map[state] ?? '#7a7a9e';
}
```

Badge CSS: `font-size: 9px; font-family: var(--font-mono); border: 1px solid; border-radius: 2px; padding: 1px 4px; text-transform: uppercase; letter-spacing: 0.04em;`

- [ ] **Step 2: Add preferred strategy display**

After the stats row, if `cluster.preferred_strategy`:
```svelte
<div class="meta-row">
  <span class="meta-label">Strategy</span>
  <span class="meta-value meta-value--cyan">{cluster.preferred_strategy}</span>
</div>
```

- [ ] **Step 3: Add manual override actions**

Below the meta section, if user has selected a cluster:
- "Promote to template" button (visible when state = active or mature): `.btn-outline-primary`, calls `PATCH /api/clusters/{id}` with `{state: 'template'}`
- "Unarchive" button (visible when state = archived): `.btn-outline-secondary`, calls `PATCH /api/clusters/{id}` with `{state: 'active'}`

Both 20px height, text-[10px], full width.

- [ ] **Step 4: Fix topology tooltip brand tokens**

In `SemanticTopology.svelte` style block, replace:
```css
background: var(--color-surface);
border: 1px solid var(--color-contour);
color: var(--color-text);
```
With:
```css
background: var(--color-bg-card);
border: 1px solid var(--color-border-subtle);
color: var(--color-text-secondary);
padding: 4px 6px;
```

- [ ] **Step 5: Run frontend tests**

Run: `cd frontend && npm test`
Expected: Tests pass (may need import updates in Inspector.test.ts)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/components/ frontend/src/lib/utils/colors.ts
git commit -m "feat(ui): add state badges, strategy display, and override actions to Inspector"
```

---

### Task 4.4: SemanticTopology — State Encoding + Unified Selection

**Files:**
- Modify: `frontend/src/lib/components/taxonomy/TopologyData.ts`
- Modify: `frontend/src/lib/components/taxonomy/SemanticTopology.svelte`

- [ ] **Step 1: Update TopologyData.ts node properties for state**

In `buildSceneData()`, adjust node properties based on cluster state:

```typescript
function stateOpacity(state: string): number {
  return state === 'candidate' ? 0.4 : 1.0;
}

function stateSizeMultiplier(state: string): number {
  if (state === 'template') return 1.5;
  if (state === 'mature') return 1.2;
  return 1.0;
}

function stateColor(state: string, oklabColor: string | null): number {
  if (state === 'template') return 0x00e5ff; // neon-cyan override
  // Parse oklabColor hex or fallback
  return oklabColor ? parseInt(oklabColor.replace('#', ''), 16) : 0x7a7a9e;
}
```

Apply in node creation:
```typescript
size: baseSize * stateSizeMultiplier(node.state),
color: stateColor(node.state, node.color_hex),
opacity: stateOpacity(node.state),
```

- [ ] **Step 2: Update SemanticTopology to apply opacity**

In `rebuildScene()`, when creating materials:
```typescript
const material = new THREE.MeshBasicMaterial({
  color: node.color,
  transparent: node.opacity < 1,
  opacity: node.opacity,
});
```

- [ ] **Step 3: Update click handler to use selectCluster**

Replace `patternsStore.selectFamily(nodeId)` with `clustersStore.selectCluster(nodeId)` everywhere in SemanticTopology.svelte.

- [ ] **Step 4: Make template labels always visible**

In `rebuildScene()`, after building labels:
```typescript
// Template nodes: labels always visible regardless of LOD
for (const node of data.nodes) {
  if (node.state === 'template' && node.visible) {
    const sprite = labels.getOrCreate(node.id, node.label, node.color);
    sprite.visible = true; // override LOD
  }
}
```

- [ ] **Step 5: Verify frontend builds and renders**

Run: `cd frontend && npm run build`
Start dev server and visually verify topology renders with state-based styling.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/components/taxonomy/
git commit -m "feat(topology): state encoding via opacity+size+color, unified selectCluster"
```

---

## Phase 5: Auto-Injection + Template Spawning

### Task 5.1: Pipeline Auto-Injection Pre-Phase

**Files:**
- Modify: `backend/app/services/pipeline.py:310-340`
- Create: `backend/tests/test_pipeline_auto_inject.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_pipeline_auto_inject.py
import pytest

@pytest.mark.asyncio
async def test_auto_injection_adds_patterns(mock_pipeline, mock_embedding_index):
    """Pipeline pre-phase retrieves and injects cluster meta-patterns."""
    # Setup: embedding index returns a match for the prompt
    mock_embedding_index.search.return_value = [("cluster_1", 0.85)]
    result = await mock_pipeline.run("Write error handlers for FastAPI")
    assert result.context_sources is not None
    assert any("cluster" in s.get("type", "") for s in result.context_sources)
```

- [ ] **Step 2: Implement auto-injection in pipeline.py**

Before the optimize phase (around line 310), add a pre-phase:

```python
# Auto-injection: retrieve relevant cluster context
injected_patterns = []
if embedding_index and embedding_index.size > 0:
    prompt_embedding = await embedding_service.aembed_single(raw_prompt)
    matches = embedding_index.search(prompt_embedding, k=3, threshold=0.72)
    if matches:
        cluster_ids = [m[0] for m in matches]
        # Load meta-patterns from matched clusters
        patterns = await db.execute(
            select(MetaPattern).where(MetaPattern.cluster_id.in_(cluster_ids))
        )
        injected_patterns = [p.pattern_text for p in patterns.scalars().all()]

        # Add to optimizer context
        if injected_patterns:
            context_sources.append({
                "type": "cluster_injection",
                "cluster_ids": cluster_ids,
                "pattern_count": len(injected_patterns),
            })
            # SSE event
            yield format_sse("context_injected", {
                "clusters": cluster_ids,
                "patterns": len(injected_patterns),
            })
```

- [ ] **Step 3: Run test**

Run: `cd backend && python -m pytest tests/test_pipeline_auto_inject.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/pipeline.py backend/tests/test_pipeline_auto_inject.py
git commit -m "feat(pipeline): auto-inject cluster meta-patterns as optimizer context"
```

---

### Task 5.2: Template Spawning in Frontend

**Files:**
- Modify: `frontend/src/lib/stores/clusters.svelte.ts`
- Modify: `frontend/src/lib/stores/forge.svelte.ts`

- [ ] **Step 1: Implement spawnTemplate in clusters store**

```typescript
async spawnTemplate(clusterId: string): Promise<void> {
  const detail = await getClusterDetail(clusterId);
  if (!detail?.optimizations?.length) return;

  // Find highest-scoring member
  const best = detail.optimizations.reduce((a, b) =>
    (b.overall_score ?? 0) > (a.overall_score ?? 0) ? b : a
  );

  // Pre-fill forge
  forgeStore.setPrompt(best.raw_prompt ?? '');
  if (detail.preferred_strategy) {
    forgeStore.setStrategy(detail.preferred_strategy);
  }

  // Switch to editor tab
  editorStore.activatePromptTab();
}
```

- [ ] **Step 2: Add SSE handler for context_injected event**

In `+page.svelte` SSE handler:
```typescript
case 'context_injected':
  addToast('optimized', `context: ${data.clusters?.[0] ?? 'cluster'} · ${data.patterns} patterns injected`);
  break;
```

- [ ] **Step 3: Verify end-to-end flow**

Start dev server, create a prompt, verify auto-injection notification appears in SSE stream. Click "Use template" on a cluster, verify editor pre-fills.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/stores/ frontend/src/routes/app/+page.svelte
git commit -m "feat(ui): template spawning + context_injected SSE notification"
```

---

## Phase 6: Orphan Backfill + Temporal Decay + Strategy Affinity

### Task 6.1: Orphan Backfill Job

Already implemented in Task 3.1 (`backfill_orphans`) and wired in Task 3.2. This task adds a test.

**Files:**
- Add test to: `backend/tests/test_prompt_lifecycle.py`

- [ ] **Step 1: Write integration test**

```python
@pytest.mark.asyncio
async def test_backfill_orphans(db_session, make_optimization, make_cluster, embedding_index):
    """Orphan optimizations get linked to nearest cluster."""
    cluster = await make_cluster(state="active", centroid_embedding=some_embedding)
    opt = await make_optimization(raw_prompt="similar text", cluster_id=None)
    await embedding_index.upsert(cluster.id, some_embedding)

    svc = PromptLifecycleService()
    linked = await svc.backfill_orphans(db_session, embedding_index)
    assert linked >= 1
```

- [ ] **Step 2: Run test**

Run: `cd backend && python -m pytest tests/test_prompt_lifecycle.py::test_backfill_orphans -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_prompt_lifecycle.py
git commit -m "test: add orphan backfill integration test"
```

---

### Task 6.2: Strategy Affinity Tracking

**Files:**
- Modify: `backend/app/services/prompt_lifecycle.py`
- Add test to: `backend/tests/test_prompt_lifecycle.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_strategy_affinity(db_session, make_cluster, make_optimization):
    """Cluster preferred_strategy set after 3+ high-score optimizations with same strategy."""
    cluster = await make_cluster(state="active")
    for _ in range(3):
        await make_optimization(cluster_id=cluster.id, strategy_used="chain-of-thought", overall_score=8.0)

    svc = PromptLifecycleService()
    await svc.update_strategy_affinity(db_session, cluster.id)
    await db_session.refresh(cluster)
    assert cluster.preferred_strategy == "chain-of-thought"
```

- [ ] **Step 2: Implement update_strategy_affinity**

```python
async def update_strategy_affinity(self, db: AsyncSession, cluster_id: str) -> None:
    """Set preferred_strategy to the most successful strategy for this cluster."""
    result = await db.execute(
        select(Optimization.strategy_used, func.count(), func.avg(Optimization.overall_score))
        .join(OptimizationPattern, OptimizationPattern.optimization_id == Optimization.id)
        .where(OptimizationPattern.cluster_id == cluster_id)
        .where(Optimization.overall_score >= 7.0)
        .group_by(Optimization.strategy_used)
        .having(func.count() >= 3)
        .order_by(func.avg(Optimization.overall_score).desc())
        .limit(1)
    )
    row = result.first()
    if row:
        await db.execute(
            update(PromptCluster).where(PromptCluster.id == cluster_id)
            .values(preferred_strategy=row[0])
        )
        await db.commit()
```

- [ ] **Step 3: Wire into post_process (after hot path)**

In `lifecycle.post_process()`, after `check_promotion()`:
```python
await self.update_strategy_affinity(db, cluster_id)
```

- [ ] **Step 4: Run test**

Run: `cd backend && python -m pytest tests/test_prompt_lifecycle.py::test_strategy_affinity -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/prompt_lifecycle.py backend/tests/test_prompt_lifecycle.py
git commit -m "feat: add strategy affinity tracking to prompt lifecycle"
```

---

### Task 6.3: Final Regression + CLAUDE.md Update

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: ALL PASS

- [ ] **Step 2: Run frontend build + tests**

Run: `cd frontend && npm run build && npm test`
Expected: ALL PASS

- [ ] **Step 3: Update CLAUDE.md**

Update the following sections:
- Replace all `PatternFamily` references with `PromptCluster`
- Replace `/api/taxonomy/*` and `/api/patterns/*` with `/api/clusters/*`
- Replace `patterns.svelte.ts` with `clusters.svelte.ts`
- Add `embedding_index.py`, `family_ops.py`, `matching.py`, `prompt_lifecycle.py` to service descriptions
- Update taxonomy engine description to note module decomposition
- Add `prompt_lifecycle.py` to key services section
- Update architectural decisions section with unified model description

- [ ] **Step 4: Update CHANGELOG.md**

Under `## Unreleased`:
```markdown
### Added
- Unified PromptCluster model replacing PatternFamily + TaxonomyNode
- In-memory numpy embedding index for O(1) cosine search
- Prompt lifecycle service: auto-curation, state promotion, temporal decay, strategy affinity
- Template spawning from mature clusters
- Auto-injection of cluster context into optimizer pipeline
- Orphan backfill job for pre-pattern optimizations
- State-based chromatic encoding in SemanticTopology (opacity/size/color)
- ClusterNavigator with state filter tabs and Proven Templates section

### Changed
- Taxonomy engine decomposed: engine.py (2098 LOC) → engine.py (~500) + family_ops.py + matching.py
- All `/api/taxonomy/*` and `/api/patterns/*` endpoints consolidated to `/api/clusters/*`
- Frontend stores unified: patterns.svelte.ts → clusters.svelte.ts

### Fixed
- Identity mismatch: topology nodeId assumed to equal familyId (now unified entity)
- Topology tooltip used non-brand CSS tokens (--color-surface, --color-contour)
- Missing DB indices on critical FK columns
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/CHANGELOG.md
git commit -m "docs: update CLAUDE.md and CHANGELOG for unified prompt lifecycle"
```
