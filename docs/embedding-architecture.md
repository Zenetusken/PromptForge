# Embedding Architecture

How embeddings are produced, stored, indexed, and consumed across the taxonomy engine.

## Embedding Types

| Column | Dim | Produced By | Description |
|--------|-----|-------------|-------------|
| `Optimization.embedding` | 384 | Hot path (`engine.py`) | `embed(raw_prompt)` — what the user asked |
| `Optimization.optimized_embedding` | 384 | Hot path (`engine.py`) | `embed(optimized_prompt)` — what the system produced |
| `Optimization.transformation_embedding` | 384 | Hot path (`engine.py`) | `L2_norm(optimized_emb - raw_emb)` — direction of improvement |
| `PromptCluster.centroid_embedding` | 384 | Hot path running mean + warm/cold reconciliation | Score-weighted mean of member raw embeddings (`max(0.1, score/10)`) |
| `MetaPattern.embedding` | 384 | Warm-path pattern extraction (Haiku) | `embed(pattern_text)` — reusable technique |

## In-Memory Indices

| Index | Contents | Consumers |
|-------|----------|-----------|
| `EmbeddingIndex` | Raw centroid per cluster | Hot-path assignment, pattern injection cluster search, composite fusion cluster lookup, warm merge pair finding |
| `OptimizedEmbeddingIndex` | Mean optimized embedding per cluster | Composite fusion Signal 3 (output direction) |
| `TransformationIndex` | Mean transformation vector per cluster | Composite fusion Signal 2 (technique direction) |

All three indices are maintained across the full lifecycle: hot path (running mean upsert), warm path (reconciliation, merge/remove, retire/remove, split/remove), cold path (full rebuild), startup (cache load + DB backfill).

## Consumption Paths

### HDBSCAN Clustering (warm split, cold refit, all merge paths)

```
blend_embeddings(raw=0.65, optimized=0.20, transformation=0.15)
    │
    ├─ raw: PromptCluster.centroid_embedding (cold/merge) or Optimization.embedding (warm split)
    ├─ optimized: OptimizedEmbeddingIndex.get_vector(cluster_id)
    └─ transformation: TransformationIndex.get_vector(cluster_id)
    │
    └─▶ batch_cluster(blended_embeddings) → HDBSCAN labels
         └─ Raw centroids stored on nodes (not blended)
```

All merge paths use blended centroids: global best-pair, same-domain label merge, and same-domain embedding merge.

**Hot-path assignment stays raw-only** — avoids circular dependency (optimized/transformation embeddings are computed from the current optimization, which depends on cluster assignment).

### Shared Blend Core

Both `blend_embeddings()` (HDBSCAN) and `CompositeQuery.fuse()` (composite fusion) delegate to `weighted_blend()` in `clustering.py`. This centralizes zero-vector detection (threshold 1e-9), weight redistribution, and L2-normalization to prevent algorithmic drift between the two paths.

### Composite Fusion (pattern injection, matching)

```
resolve_fused_embedding(raw_prompt, phase)
    │
    ├─ Signal 1 (topic):         embed(raw_prompt)
    ├─ Signal 2 (transformation): TransformationIndex.get_vector(matched_cluster)
    ├─ Signal 3 (output):         OptimizedEmbeddingIndex.get_vector(matched_cluster)
    └─ Signal 4 (pattern):        avg(top 3 MetaPattern.embedding WHERE global_source_count >= 3)
    │
    └─▶ PhaseWeights.fuse() → L2-normalized 384-dim query vector
```

Per-phase default profiles: analysis (topic 0.60), optimization (transform 0.35), pattern_injection (pattern 0.30), scoring (output 0.45).

### Few-Shot Retrieval

```
retrieve_few_shot_examples(raw_prompt)
    │
    ├─ input_sim:  cosine(embed(raw_prompt), Optimization.embedding)        threshold 0.50
    └─ output_sim: cosine(embed(raw_prompt), Optimization.optimized_embedding)  threshold 0.40
    │
    └─▶ Qualify if either passes → re-rank by max(input_sim, output_sim) * overall_score
```

### Cross-Cluster Pattern Injection

```
auto_inject_patterns(raw_prompt)
    │
    ├─ Topic-matched patterns:  top-5 clusters via EmbeddingIndex.search()
    └─ Universal patterns:      MetaPattern WHERE global_source_count >= 3
    │
    └─▶ Relevance = cosine_sim * log2(1 + global_source_count) * cluster_score_factor
```

## Weight Learning Flow

```
Layer 1: resolve_contextual_weights(task_type, cluster_learned_weights)
    │
    ├─ Phase defaults (4 profiles × 4 signals)
    ├─ + task-type bias (_TASK_TYPE_WEIGHT_BIAS: 7 types)
    └─ + cluster learned weights blend (alpha=0.3)
    │
    └─▶ Stored on Optimization.phase_weights_json

Layer 2: compute_score_correlated_target(scored_profiles)  [warm path, min 10 samples]
    │
    ├─ z-score above median → contribution weight
    └─ Weighted mean of above-median profiles
    │
    ├─▶ Global: adapt preferences (EMA alpha=0.05)
    └─▶ Per-cluster: store in cluster_metadata["learned_phase_weights"]

Layer 3: decay_toward_target(current, phase, target)  [warm path, rate=0.01]
    │
    └─ Drift toward cluster learned weights (or defaults if no learning yet)
    │
    └─▶ Runs BEFORE Layer 2 so adaptation (0.05) dominates decay (0.01)
```

## Design Decisions

**Blend vs. concatenation for HDBSCAN**: Weighted blend (384-dim) chosen over concatenation (1152-dim). HDBSCAN uses Euclidean distance on L2-normalized vectors — concatenating three different embedding spaces makes normalization semantically incoherent. HDBSCAN also degrades in high dimensions.

**Hot-path raw-only**: Cluster assignment at ingestion time uses raw embedding only. The optimization's output embedding is computed from the current optimization, creating a chicken-and-egg problem if used for assignment. Warm/cold paths correct misassignments using blended HDBSCAN.

**Default blend weights (0.65/0.20/0.15)**: Raw dominates because topic similarity is the primary clustering signal. Optimized adds output-quality signal (clusters producing similar outputs). Transformation adds technique-direction signal (clusters using similar improvement strategies). Configurable via `CLUSTERING_BLEND_W_*` constants in `_constants.py`.

**Score-weighted centroids**: `max(0.1, score/10)` gives 9:1 weight ratio between score-9 and score-1 optimizations, shifting centroids toward high-quality members without completely ignoring low-scoring ones.
