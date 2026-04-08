# ADR-005 Phase 1 — Implementation Decomposition

> **Spec:** `docs/specs/2026-04-08-taxonomy-scaling-design.md`
> **ADR:** `docs/adr/ADR-005-taxonomy-scaling-architecture.md`

Phase 1 decomposes into 3 independent sub-plans that can be built and tested separately. Each produces working, testable software on its own.

## Sub-plan A: State Constant + Project Migration (tasks 1-4)

**Goal:** Introduce `EXCLUDED_STRUCTURAL_STATES` constant, add `state='project'` convention, create Legacy project node, re-parent domains, add `project_id` to Optimization.

**Dependencies:** None — this is the foundation everything else builds on.

**Files to modify:**
- `backend/app/services/taxonomy/_constants.py` — add constant
- `backend/app/services/taxonomy/engine.py` — replace 8 `.notin_()` + 1 `not in`
- `backend/app/services/taxonomy/warm_phases.py` — replace 14 `.notin_()` + 3 `not in`
- `backend/app/services/taxonomy/cold_path.py` — replace 7 `.notin_()` + 1 `not in`
- `backend/app/services/taxonomy/warm_path.py` — replace 1 `.notin_()`
- `backend/app/services/taxonomy/family_ops.py` — replace 1 `.notin_()`
- `backend/app/services/taxonomy/quality.py` — replace 2 `not in`
- `backend/app/routers/clusters.py` — convert `!= "archived"` patterns to `.notin_()`
- `backend/app/routers/health.py` — domain count query
- `backend/app/models.py` — add `project_id` to Optimization, add GlobalPattern model
- `backend/app/main.py` — migration in lifespan startup

**Estimated tasks:** 6 (constant, replace all, model changes, migration, backfill, tests)

## Sub-plan B: Dirty-Set Tracking + Warm Path Optimization (tasks 5-7)

**Goal:** Add `_dirty_set` to TaxonomyEngine, modify warm path phases to process only dirty clusters where appropriate, add adaptive scheduler measurement infrastructure.

**Dependencies:** None — can be built before or after Sub-plan A.

**Files to modify:**
- `backend/app/services/taxonomy/engine.py` — add `_dirty_set`, mark dirty in `process_optimization()`
- `backend/app/services/taxonomy/warm_path.py` — snapshot/clear dirty set, pass to phases
- `backend/app/services/taxonomy/warm_phases.py` — phase-specific dirty scoping (Phases 0-6)
- `backend/app/main.py` — restart full-scan detection, scheduler rolling window

**Estimated tasks:** 5 (dirty-set, phase scoping, scheduler measurement, restart recovery, tests)

## Sub-plan C: Embedding Index Project Filter (task 8)

**Goal:** Add `project_filter` parameter to `EmbeddingIndex.search()` with `_project_ids` array for per-project vector filtering.

**Dependencies:** None — can be built independently. Tested with Sub-plan A data.

**Files to modify:**
- `backend/app/services/taxonomy/embedding_index.py` — all 8+ methods
- `backend/app/services/taxonomy/transformation_index.py` — mirror if same pattern
- `backend/app/services/taxonomy/optimized_index.py` — mirror if same pattern

**Estimated tasks:** 4 (project_ids array, search filter, cache compat, tests)

## Execution Order — MANDATORY: A first

**A → B → C** (strict sequential). Sub-plan A MUST run first because:
- A modifies `warm_path.py` (`_load_active_nodes()` constant replacement) — B also modifies `warm_path.py` (dirty-set wiring). Running B first causes merge conflicts.
- A modifies `main.py` (migration function) — C also modifies `main.py` (startup rebuild callers). Running C first causes merge conflicts.
- A creates the `state='project'` convention that B and C's code must respect.

B and C are independent of each other but both depend on A's changes being committed first.

## Next Step

Start a new conversation session. Reference this decomposition and the spec. Build Sub-plan A first using `superpowers:writing-plans` to generate the detailed task-by-task plan, then execute with `superpowers:subagent-driven-development`.
