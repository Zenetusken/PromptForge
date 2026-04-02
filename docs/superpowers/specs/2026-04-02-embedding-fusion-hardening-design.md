# Embedding Fusion Hardening Design

**Date**: 2026-04-02
**Status**: Approved
**Scope**: Three targeted gaps in the composite embedding fusion system

---

## Context

An audit of the composite embedding fusion system confirmed 9 of 10 planned features fully implemented. Three gaps remain that affect startup resilience, quality metric completeness, and cold-path clustering fidelity. This spec addresses all three.

---

## Gap 1: Disk Cache for TransformationIndex + OptimizedEmbeddingIndex

### Problem

`EmbeddingIndex` has `save_cache`/`load_cache` for fast startup recovery. `TransformationIndex` and `OptimizedEmbeddingIndex` do not. After process restart, composite fusion Signals 2 (transformation) and 3 (output) degrade to zero vectors until the hot path refills them or a cold path runs.

### Design

Mirror `EmbeddingIndex.save_cache`/`load_cache` (pickle + max_age_seconds + lock) on both classes.

**TransformationIndex** (`transformation_index.py`):
- Add `save_cache(cache_path: Path)` — pickle `{"matrix": self._matrix, "ids": self._ids}` under lock
- Add `load_cache(cache_path: Path, max_age_seconds: int = 3600) -> bool` — load if file exists and fresh

**OptimizedEmbeddingIndex** (`optimized_index.py`):
- Identical `save_cache`/`load_cache` methods

**Cold path** (`cold_path.py`):
- After existing `save_cache` for `EmbeddingIndex` (line ~637), add `save_cache` calls for both indices:
  - `DATA_DIR / "transformation_index.pkl"`
  - `DATA_DIR / "optimized_index.pkl"`

**Engine startup** (`engine.py`):
- Add `async def load_index_caches(self, data_dir: Path)` method
- Calls `load_cache` on all three indices
- Called from app startup (e.g., `main.py` lifespan or `get_engine()` initialization)

**Cache file paths**:
- `data/embedding_index.pkl` (existing)
- `data/transformation_index.pkl` (new)
- `data/optimized_index.pkl` (new)

### Files Modified

| File | Change |
|------|--------|
| `transformation_index.py` | Add `save_cache`, `load_cache` |
| `optimized_index.py` | Add `save_cache`, `load_cache` |
| `cold_path.py` | Add save calls after rebuild (~line 678, ~line 718) |
| `engine.py` | Add `load_index_caches()` method |
| `main.py` | Call `load_index_caches()` at startup |

---

## Gap 2: Silhouette-Based Cluster Validity Metric

### Problem

`Q_system` has a `w_d` (DBCV) weight slot that's always 0.0 because `ramp_progress` is hardcoded to 0.0. The quality gate operates on coherence + separation + coverage only — no density-based validation of cluster quality.

### Design

Use `sklearn.metrics.silhouette_score` as the cluster validity metric. It measures how similar each point is to its own cluster vs the nearest other cluster — semantically equivalent to what DBCV captures. sklearn's HDBSCAN doesn't expose `relative_validity_`, but `silhouette_score` is readily available and well-tested.

**ClusterResult** (`clustering.py`):
- Add `silhouette: float = 0.0` field to the dataclass
- After HDBSCAN fit, compute: `silhouette_score(mat[labels >= 0], labels[labels >= 0])` if >= 2 clusters and >= 2 non-noise points
- Rescale from [-1, 1] to [0, 1]: `(raw + 1) / 2`
- Store on `ClusterResult.silhouette`

**Q_system ramp activation** (`engine.py`):
- Replace `ramp = 0.0` in `_compute_q_from_nodes` with:
  ```python
  n_active = len(metrics)
  ramp = min(1.0, max(0.0, (n_active - 5) / 20))
  ```
- Below 5 active nodes: ramp = 0.0 (DBCV weight stays 0)
- At 25+ active nodes: ramp = 1.0 (DBCV weight reaches full `_W_D_TARGET = 0.15`)
- Pass silhouette score through as `dbcv` parameter

**Silhouette computation for Q_system** (`engine.py` or `warm_phases.py`):
- Both warm and cold paths need the silhouette score of the current taxonomy state
- Add helper `compute_taxonomy_silhouette(nodes, engine)` that:
  1. Collects centroids from active nodes
  2. Constructs label array (each node is its own "cluster" in centroid space — this is separation quality)
  3. Actually: use the blended embedding matrix from the most recent cold path, or compute from stored centroids
- **Simpler approach**: Compute silhouette in `batch_cluster()` where we already have the matrix and labels. Store on `ClusterResult`. Cold path passes it through. Warm path computes incrementally from stored centroids.

**Cold path** (`cold_path.py`):
- `batch_cluster()` now returns `silhouette` on `ClusterResult`
- Store the silhouette score for use in Q_system computation
- Pass to `_compute_q_from_nodes` (add `silhouette` parameter)

**Warm path** (`warm_phases.py`):
- After final `_compute_q_from_nodes`, compute silhouette from active node centroids
- Use the same rescale formula

**`_compute_q_from_nodes` signature change** (`engine.py`):
```python
def _compute_q_from_nodes(self, nodes: list[PromptCluster], silhouette: float = 0.0) -> float:
```

### Files Modified

| File | Change |
|------|--------|
| `clustering.py` | Add `silhouette` to `ClusterResult`, compute after HDBSCAN fit |
| `engine.py` | Update `_compute_q_from_nodes`: accept `silhouette` param, activate ramp |
| `cold_path.py` | Pass `cluster_result.silhouette` through to Q computation |
| `warm_phases.py` | Compute silhouette from active centroids, pass to Q computation |
| `quality.py` | No changes needed — `QWeights.from_ramp` and `compute_q_system` already support DBCV slot |

---

## Gap 3: Output-Coherence-Weighted Blend in Cold Path

### Problem

Cold path HDBSCAN uses static blend weights (0.65/0.20/0.15) for all clusters. If a cluster historically produces divergent outputs (low `output_coherence`), its optimized embedding mean is unreliable as a clustering signal — but the static weights don't account for this.

### Design

Per-cluster adaptive blend weights in the cold path loop based on `output_coherence` from cluster metadata.

**Cold path blend loop** (`cold_path.py:180-189`):
- Before blending, look up the source cluster's `output_coherence` from metadata
- Adjust `w_optimized` based on coherence:
  - `output_coherence >= 0.5`: keep default 0.20 (optimized embeddings are informative)
  - `output_coherence < 0.5`: scale linearly: `w_optimized = 0.20 * max(0.25, output_coherence / 0.5)`
  - Floor at `0.05` (never fully zero — some signal is better than none)
  - Missing metadata: keep default 0.20
- Redistributed weight goes to raw: `w_raw = 1.0 - w_optimized - w_transform`
- `w_transform` stays at 0.15 (transformation vectors are independent of output coherence)

**Implementation**:
```python
for i, f in enumerate(valid_families):
    opt_vec = opt_idx.get_vector(f.id) if opt_idx else None
    trans_vec = trans_idx.get_vector(f.id) if trans_idx else None
    
    # Adaptive blend: downweight optimized signal when output coherence is low
    w_opt = CLUSTERING_BLEND_W_OPTIMIZED  # 0.20
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

**Graceful degradation**: If `cluster_metadata` is None or `output_coherence` is missing, static weights are used — identical to current behavior.

### Files Modified

| File | Change |
|------|--------|
| `cold_path.py` | Adaptive blend weights in the HDBSCAN input loop |

---

## Testing Strategy

### Gap 1 Tests
- `test_transformation_index.py`: Add tests for `save_cache`/`load_cache` (round-trip, stale cache rejection, missing file)
- `test_optimized_index.py`: Same tests
- Integration: verify engine startup loads caches and composite fusion signals are non-zero after restart

### Gap 2 Tests
- `test_clustering.py` or new `test_silhouette.py`: Verify `ClusterResult.silhouette` is computed correctly (known clusters), rescaled to [0, 1], returns 0.0 for single-cluster or all-noise
- `test_quality.py`: Verify ramp activation — Q_system increases when silhouette is high and ramp > 0

### Gap 3 Tests
- `test_cold_path_adaptive_blend.py` or extend existing cold path tests: Verify low output_coherence reduces `w_optimized`, missing metadata uses defaults, `w_raw + w_optimized + w_transform == 1.0` invariant holds

---

## Verification

1. Run full backend test suite: `cd backend && pytest --cov=app -v`
2. Start services (`./init.sh restart`), run an optimization, trigger warm path, verify silhouette appears in Q_system logs
3. Verify cache files created in `data/` after cold path
4. Restart backend, verify composite fusion signals are non-zero on first optimization (loaded from cache)
