# Taxonomy Hot-Path Orphan Recovery

## Problem

When `process_optimization()` fails mid-transaction (IntegrityError, session rollback, timeout), the `Optimization` row persists with `overall_score` set but `embedding IS NULL`, leaving it permanently excluded from taxonomy clustering, pattern injection, and few-shot retrieval. Currently 4 orphans exist in production.

The existing semi-orphan repair in warm_phases.py Phase 0.5 only handles optimizations that already HAVE embeddings but have stale/null `cluster_id`. Optimizations with `embedding IS NULL` are invisible to it.

## Design

### New file: `backend/app/services/orphan_recovery.py`

A standalone service with no router imports. Single public async function + metrics accessor.

```python
class OrphanRecoveryService:
    # In-memory counters (reset on restart)
    _orphan_count: int = 0
    _recovered_total: int = 0
    _failed_total: int = 0
    _last_scan_at: datetime | None = None
    _last_recovery_at: datetime | None = None
    # In-memory guard for concurrent recovery
    _in_progress: set[str] = set()

    async def scan_and_recover(
        self,
        session_factory: Callable,
        engine: TaxonomyEngine,
    ) -> dict:
        """Scan for orphans and recover them. Returns stats dict."""

    def get_metrics(self) -> dict:
        """Return health endpoint metrics."""
```

### Detection query

```python
select(Optimization).where(
    Optimization.embedding.is_(None),
    Optimization.overall_score.isnot(None),  # pipeline completed
    Optimization.created_at < (utcnow() - timedelta(minutes=5)),
    # Exclude exhausted orphans
).limit(20)
```

Post-query filter: skip any with `heuristic_flags` containing `"recovery_exhausted"` (check both dict and list formats since existing code writes lists).

### Recovery sequence (per orphan, fresh session)

1. **Compute embeddings** (outside write transaction):
   - `embedding` from `raw_prompt` via `EmbeddingService.aembed_single()`
   - `optimized_embedding` from `optimized_prompt` if present
   - `transformation_embedding` = normalized diff if both exist

2. **Open write session** (short transaction):
   - Re-read optimization row (may have been recovered concurrently)
   - If `embedding` now set, skip (idempotent)
   - If `cluster_id` set and cluster active, skip assignment
   - If `cluster_id` points to archived cluster, clear it
   - Call `assign_cluster()` for two-tier assignment
   - Write embeddings + cluster_id + project_id
   - Create `OptimizationPattern(relationship="source")` if not exists
   - Mark cluster dirty via `engine.mark_dirty()`
   - Commit

3. **On failure**: increment retry counter in `heuristic_flags`, log warning. After 3 attempts, set `"recovery_exhausted"` flag.

### heuristic_flags format

Currently written as `list[str]` (divergence flags like `["clarity", "specificity"]`). Recovery metadata will use a convention: append `"recovery_attempt:N"` strings and `"recovery_exhausted"` string. This keeps the existing list format intact.

### Integration: warm-path timer in main.py

Piggyback on the warm-path timer loop. After the warm path completes (or skips), run recovery:

```python
# After warm path result handling (~line 1178)
try:
    from app.services.orphan_recovery import recovery_service
    await recovery_service.scan_and_recover(async_session_factory, engine)
except Exception:
    logger.debug("Orphan recovery failed (non-fatal)", exc_info=True)
```

Singleton `recovery_service` instance at module level in `orphan_recovery.py`.

### Health endpoint

Add `recovery` field to `HealthResponse`:
```python
recovery: dict | None = Field(default=None, description="Orphan recovery metrics.")
```

Populated from `recovery_service.get_metrics()` in the health handler.

### Observability

Three event types via `TaxonomyEventLogger.log_decision()`:

| path | op | decision | context |
|------|----|----------|---------|
| `warm` | `recovery` | `scan` | `{orphan_count, recovered, failed}` |
| `warm` | `recovery` | `success` | `{optimization_id, cluster_id, cluster_label}` |
| `warm` | `recovery` | `failed` | `{optimization_id, error_type, error_message, attempt}` |

### ActivityPanel display

Add `recovery` to the `keyMetric()` function in `ActivityPanel.svelte`:
```
if (e.op === 'recovery') — display orphan count, recovered count, or error message
```

## Files to modify

| File | Change |
|------|--------|
| `backend/app/services/orphan_recovery.py` | **NEW** — OrphanRecoveryService |
| `backend/app/main.py` | Hook recovery into warm-path timer loop |
| `backend/app/routers/health.py` | Add `recovery` field to HealthResponse |
| `frontend/.../ActivityPanel.svelte` | Add `recovery` op handler |
| `docs/CHANGELOG.md` | Add entry |

## Constraints

- No schema migration — uses existing `embedding`, `cluster_id`, `heuristic_flags` columns
- No router imports from service
- Embedding computation outside write transaction (SQLite single-writer)
- Max 20 orphans per scan, 3 retry attempts per orphan
- In-memory concurrency guard (`_in_progress` set)
- Graceful degradation — all failures non-fatal

## Verification

1. Manually null out an optimization's embedding → run recovery → verify restored
2. Run full test suite (2010+ tests)
3. Check health endpoint shows recovery metrics
4. Check ActivityPanel shows recovery events
