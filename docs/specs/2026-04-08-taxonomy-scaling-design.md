# Taxonomy Scaling Design Spec

**Date:** 2026-04-08
**ADR:** [ADR-005](../../adr/ADR-005-taxonomy-scaling-architecture.md)
**Status:** Approved design, pending implementation

## Problem

At 161 optimizations, 67% of taxonomy clusters are singletons. The system creates ~3-4 new singletons per day. At vibe-coder scale (100-500 prompts/day across multiple projects), three bottlenecks emerge: warm path O(N) scanning, SQLite write contention during hot-path bursts, and single-namespace noise diluting cross-project pattern quality.

The singleton problem solves itself at scale (same semantic patterns recur across projects), but the infrastructure must support that scale without degradation.

## Design Overview

Three-layer tiered taxonomy with self-tuning warm path:

```
Layer 3: GlobalPattern (cross-project, durable, 500 cap)
Layer 2: Domain nodes (per-project semantic groups)
Layer 1: Clusters (per-project, managed by warm path)
```

**Project as tree parent:** `PromptCluster` with `state='project'` in existing hierarchy. No new tables for projects. Unified tree: project → domain → cluster.

## Data Model Changes

### PromptCluster

- Add `state='project'` to state enum (alongside active, candidate, mature, template, archived, domain)
- No new columns — project identity is expressed through the tree hierarchy

### Optimization

- Add `project_id: str | null` — denormalized FK for fast filtering. Set from linked repo at optimization time. Null = legacy.

### GlobalPattern (new table)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | PK |
| pattern_text | TEXT | No | Technique description |
| embedding | BLOB | Yes | 384-dim float32 for injection search |
| source_cluster_ids | JSON | No | Contributing cluster UUIDs |
| source_project_ids | JSON | No | Contributing project UUIDs |
| cross_project_count | INT | No | Distinct projects (>= 2) |
| global_source_count | INT | No | Distinct clusters (>= 5) |
| avg_cluster_score | FLOAT | Yes | Mean avg_score of source clusters |
| promoted_at | DATETIME | No | Graduation timestamp |
| last_validated_at | DATETIME | No | Last warm-path validation |
| state | TEXT | No | `active` / `demoted` / `retired` |

### Migration

1. Create `GlobalPattern` table
2. Add `project_id` column to `Optimization` (nullable, no FK constraint for SQLite compat)
3. Create "Legacy" project node: `INSERT INTO prompt_clusters (state='project', label='Legacy')`
4. Re-parent all existing domain nodes: `UPDATE prompt_clusters SET parent_id = <legacy_id> WHERE state = 'domain'`
5. Backfill `Optimization.project_id` from cluster ancestry

## Hot Path Changes

### Project-scoped assignment

```
embed(prompt)
  → search embedding_index(project_filter=current_project, threshold=0.59)
  → if match: assign to in-project cluster
  → else: search embedding_index(project_filter=None, threshold=0.70)
    → if cross-project match: assign to that cluster (becomes multi-project)
    → else: create new singleton under current project's domain subtree
```

### Embedding index

- Tag each vector with `project_id`
- `search(embedding, k, threshold, project_filter=None)` — filters before cosine
- No algorithm change (numpy brute-force). HNSW deferred to Phase 3.

## Warm Path Changes

### Dirty-set tracking

- New `_dirty_set: set[str]` on TaxonomyEngine
- Hot path: `_dirty_set.add(cluster_id)` when member added/removed
- Warm path: process only clusters in `_dirty_set`, clear after cycle
- Existing `pattern_stale=True` flag still drives Phase 4 (refresh)

### Adaptive scheduler

Rolling window of last 10 cycles: `(dirty_count, duration_ms)`.

**Derived thresholds (self-tuning):**
- `target_cycle_ms`: p75 of recent durations
- `dirty_boundary`: linear regression of (dirty_count → duration) — the dirty count at which estimated duration exceeds target

**Mode decision:**
- `dirty_count <= boundary` → all-dirty mode (process all dirty clusters across all projects)
- `dirty_count > boundary` → round-robin mode (process highest-priority project only)

**Bootstrap:** Static fallbacks (boundary=20, target=10000ms) for first 10 cycles.

**Priority in round-robin:** Project with most dirty clusters goes first.

### Per-project Q metrics

- `_compute_q_from_nodes()` gains `project_filter` parameter
- Speculative Q-gate evaluates within project scope
- Cross-project operations (merge at cosine > 0.7) use the target project's Q metrics

## Global Pattern Tier

### Promotion (warm path Phase 4)

During `global_source_count` computation:
1. For each MetaPattern, compute distinct project count from source clusters
2. If `cross_project_count >= 2` AND `global_source_count >= 5` AND `avg_cluster_score >= 6.0`:
   - Check for existing GlobalPattern with cosine >= 0.90 (dedup)
   - If exists: update source lists and counts
   - If new: create GlobalPattern with `state='active'`

### Injection (pattern_injection.py)

Cross-cluster injection query expanded:
```sql
-- Existing: MetaPattern with high global_source_count
UNION
-- New: GlobalPattern with state='active'
```
GlobalPatterns get 1.3x relevance multiplier in ranking.

### Validation (every 10th warm cycle)

For each GlobalPattern:
- Re-check source clusters: how many still active?
- `avg_cluster_score < 5.5` → `state = 'demoted'` (no multiplier, still injectable)
- All source clusters archived AND `promoted_at > 30 days ago` → `state = 'retired'` (excluded from injection)
- Otherwise: update `last_validated_at`

### Retention

- Hard cap: 500 active GlobalPatterns
- When cap hit: retire least-recently-validated first
- Demoted patterns evicted before active ones
- Retired patterns kept in table for audit trail

## State Exclusion Updates

Every tree query that filters by state needs `state='project'` added to exclusions. Affected locations:

- `engine.py`: `_load_active_nodes()`, `_compute_q_from_nodes()`, `_update_per_node_separation()`
- `warm_phases.py`: all phase functions that query `PromptCluster.state.notin_([...])`
- `cold_path.py`: HDBSCAN input, UMAP projection, quality gate
- `clustering.py`: `batch_cluster()` input filtering
- `routers/clusters.py`: tree endpoint, stats endpoint
- `health.py`: domain count query

Pattern: replace `["domain", "archived"]` with `["domain", "archived", "project"]` in all `.notin_()` calls.

## Testing Strategy

### Unit tests
- Adaptive scheduler: verify mode switching at boundary, bootstrap behavior, threshold convergence
- Dirty-set tracking: verify add/clear lifecycle, warm path only processes dirty clusters
- GlobalPattern promotion: threshold enforcement, dedup, validation, retention cap

### Integration tests
- Project creation + domain migration under project node
- Hot-path project-scoped search + cross-project assignment
- Warm path skips clean clusters, processes dirty ones
- GlobalPattern survives source cluster archival
- Injection includes GlobalPatterns with multiplier

### E2E validation
- Create 2 projects, seed 50 prompts each, verify cross-project pattern emergence
- Monitor warm path cycle times via `/api/monitoring`
- Verify topology view respects project filter

## Implementation Phases

### Phase 1: Foundation
- `state='project'` enum addition + state exclusion updates
- "Legacy" project node migration
- `project_id` on Optimization
- Dirty-set tracking on TaxonomyEngine
- Warm path: dirty-only processing
- Adaptive scheduler with rolling window
- Embedding index: project_filter parameter

### Phase 2: Multi-Project
- Project creation on repo link
- Hot-path project-scoped search + cross-project assignment
- Per-project Q metrics
- GlobalPattern model + promotion + injection + validation + retention
- Topology UI: project filter

### Phase 3: Performance (data-driven triggers)
- HNSW embedding index (when search > 50ms)
- PostgreSQL migration (when SQLite contention > 30s p95)
- Round-robin warm scheduling (when cycle time > 30s)
