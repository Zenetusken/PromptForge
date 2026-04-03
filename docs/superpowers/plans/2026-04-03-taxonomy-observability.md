# Taxonomy Engine Observability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured decision tracing to all taxonomy engine paths (hot/warm/cold) with JSONL persistence, in-memory ring buffer for real-time SSE, and a frontend Activity panel.

**Architecture:** New `TaxonomyEventLogger` service (mirrors `TraceLogger` pattern) dual-writes to daily JSONL files + deque ring buffer. ~17 instrumentation points across `family_ops.py`, `warm_path.py`, `warm_phases.py`, `cold_path.py`, and `split.py`. Two new API endpoints serve events. Frontend `ActivityPanel.svelte` displays real-time feed via SSE.

**Tech Stack:** Python 3.12, FastAPI, JSONL, collections.deque, Svelte 5 runes, SSE

**Spec:** `docs/superpowers/specs/2026-04-03-taxonomy-observability-design.md`

---

### Task 1: TaxonomyEventLogger Service

**Files:**
- Create: `backend/app/services/taxonomy/event_logger.py`
- Create: `backend/tests/test_taxonomy_event_logger.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_taxonomy_event_logger.py
"""Tests for TaxonomyEventLogger — JSONL persistence + ring buffer."""

import json
import time
from pathlib import Path

import pytest

from app.services.taxonomy.event_logger import TaxonomyEventLogger


@pytest.fixture
def logger(tmp_path: Path) -> TaxonomyEventLogger:
    return TaxonomyEventLogger(events_dir=tmp_path, publish_to_bus=False)


class TestLogDecision:
    def test_writes_jsonl_file(self, logger: TaxonomyEventLogger, tmp_path: Path) -> None:
        logger.log_decision(
            path="hot", op="assign", decision="merge_into",
            cluster_id="c1", context={"raw_score": 0.72},
        )
        files = list(tmp_path.glob("decisions-*.jsonl"))
        assert len(files) == 1
        line = files[0].read_text().strip()
        event = json.loads(line)
        assert event["path"] == "hot"
        assert event["op"] == "assign"
        assert event["decision"] == "merge_into"
        assert event["cluster_id"] == "c1"
        assert event["context"]["raw_score"] == 0.72
        assert "ts" in event

    def test_appends_to_ring_buffer(self, logger: TaxonomyEventLogger) -> None:
        logger.log_decision(path="warm", op="phase", decision="accepted", context={})
        recent = logger.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0]["op"] == "phase"

    def test_ring_buffer_capped(self, tmp_path: Path) -> None:
        small_logger = TaxonomyEventLogger(
            events_dir=tmp_path, publish_to_bus=False, buffer_size=5,
        )
        for i in range(10):
            small_logger.log_decision(
                path="hot", op="assign", decision="create_new",
                context={"idx": i},
            )
        recent = small_logger.get_recent(limit=20)
        assert len(recent) == 5
        # Oldest should be idx=5 (first 5 evicted)
        assert recent[-1]["context"]["idx"] == 5


class TestGetRecent:
    def test_filter_by_path(self, logger: TaxonomyEventLogger) -> None:
        logger.log_decision(path="hot", op="assign", decision="merge_into", context={})
        logger.log_decision(path="warm", op="phase", decision="accepted", context={})
        assert len(logger.get_recent(path="hot")) == 1
        assert len(logger.get_recent(path="warm")) == 1

    def test_filter_by_op(self, logger: TaxonomyEventLogger) -> None:
        logger.log_decision(path="warm", op="split", decision="success", context={})
        logger.log_decision(path="warm", op="merge", decision="success", context={})
        assert len(logger.get_recent(op="split")) == 1

    def test_limit(self, logger: TaxonomyEventLogger) -> None:
        for _ in range(10):
            logger.log_decision(path="hot", op="assign", decision="create_new", context={})
        assert len(logger.get_recent(limit=3)) == 3


class TestGetHistory:
    def test_reads_from_jsonl(self, logger: TaxonomyEventLogger) -> None:
        logger.log_decision(path="cold", op="refit", decision="accepted", context={})
        from datetime import UTC, datetime
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        history = logger.get_history(date=today)
        assert len(history) == 1
        assert history[0]["op"] == "refit"

    def test_pagination(self, logger: TaxonomyEventLogger) -> None:
        for i in range(5):
            logger.log_decision(
                path="hot", op="assign", decision="create_new", context={"i": i},
            )
        from datetime import UTC, datetime
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        page1 = logger.get_history(date=today, limit=2, offset=0)
        page2 = logger.get_history(date=today, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2

    def test_missing_date_returns_empty(self, logger: TaxonomyEventLogger) -> None:
        assert logger.get_history(date="1999-01-01") == []


class TestRotate:
    def test_deletes_old_files(self, tmp_path: Path) -> None:
        old_file = tmp_path / "decisions-2020-01-01.jsonl"
        old_file.write_text('{"test": true}\n')
        logger = TaxonomyEventLogger(events_dir=tmp_path, publish_to_bus=False)
        deleted = logger.rotate(retention_days=1)
        assert deleted == 1
        assert not old_file.exists()

    def test_keeps_recent_files(self, logger: TaxonomyEventLogger, tmp_path: Path) -> None:
        logger.log_decision(path="hot", op="assign", decision="merge_into", context={})
        deleted = logger.rotate(retention_days=1)
        assert deleted == 0
        assert len(list(tmp_path.glob("*.jsonl"))) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_taxonomy_event_logger.py -v 2>&1 | head -30`
Expected: ModuleNotFoundError — `event_logger` does not exist yet.

- [ ] **Step 3: Implement TaxonomyEventLogger**

```python
# backend/app/services/taxonomy/event_logger.py
"""TaxonomyEventLogger — structured decision tracing for taxonomy engine.

Dual-writes to:
  1. Daily JSONL files in data/taxonomy_events/ (persistence)
  2. In-memory ring buffer (real-time reads via API)

Optionally publishes to the EventBus for SSE streaming.
"""

import json
import logging
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: "TaxonomyEventLogger | None" = None


def get_event_logger() -> "TaxonomyEventLogger":
    """Return the process-wide TaxonomyEventLogger (set during lifespan)."""
    if _instance is None:
        raise RuntimeError("TaxonomyEventLogger not initialized — call set_event_logger() first")
    return _instance


def set_event_logger(inst: "TaxonomyEventLogger") -> None:
    global _instance
    _instance = inst


# ---------------------------------------------------------------------------
# Logger class
# ---------------------------------------------------------------------------


class TaxonomyEventLogger:
    """Structured decision event logger for taxonomy hot/warm/cold paths."""

    def __init__(
        self,
        events_dir: str | Path = "data/taxonomy_events",
        publish_to_bus: bool = True,
        buffer_size: int = 500,
    ) -> None:
        self._events_dir = Path(events_dir)
        self._events_dir.mkdir(parents=True, exist_ok=True)
        self._publish_to_bus = publish_to_bus
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def log_decision(
        self,
        *,
        path: str,
        op: str,
        decision: str,
        cluster_id: str | None = None,
        optimization_id: str | None = None,
        duration_ms: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log a taxonomy decision event.

        Args:
            path: "hot", "warm", or "cold".
            op: Operation type (assign, split, merge, retire, phase, refit, etc.).
            decision: Outcome (merge_into, create_new, accepted, rejected, etc.).
            cluster_id: Affected cluster ID (nullable).
            optimization_id: Triggering optimization ID (nullable).
            duration_ms: Wall-clock time in ms (nullable).
            context: Operation-specific decision context dict.
        """
        event: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "path": path,
            "op": op,
            "decision": decision,
        }
        if cluster_id is not None:
            event["cluster_id"] = cluster_id
        if optimization_id is not None:
            event["optimization_id"] = optimization_id
        if duration_ms is not None:
            event["duration_ms"] = duration_ms
        if context:
            event["context"] = context

        # 1. Append to ring buffer
        self._buffer.append(event)

        # 2. Append to daily JSONL file
        try:
            daily_file = self._daily_file()
            with daily_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            logger.warning("Failed to write taxonomy event to JSONL: %s", exc)

        # 3. Publish to event bus for SSE
        if self._publish_to_bus:
            try:
                from app.services.event_bus import event_bus
                event_bus.publish("taxonomy_activity", event)
            except Exception:
                pass  # Non-fatal — don't break taxonomy operations

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_recent(
        self,
        limit: int = 50,
        path: str | None = None,
        op: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent events from ring buffer (newest first)."""
        events = list(self._buffer)
        if path:
            events = [e for e in events if e.get("path") == path]
        if op:
            events = [e for e in events if e.get("op") == op]
        events.reverse()  # newest first
        return events[:limit]

    def get_history(
        self,
        date: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Read events from a specific day's JSONL file."""
        filepath = self._events_dir / f"decisions-{date}.jsonl"
        if not filepath.exists():
            return []

        events: list[dict[str, Any]] = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events[offset : offset + limit]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def rotate(self, retention_days: int = 30) -> int:
        """Delete JSONL event files older than retention_days."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        deleted = 0
        for filepath in self._events_dir.glob("decisions-*.jsonl"):
            try:
                date_str = filepath.stem.replace("decisions-", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                if file_date < cutoff:
                    filepath.unlink()
                    deleted += 1
                    logger.info("Deleted old taxonomy event file: %s", filepath.name)
            except (ValueError, OSError) as exc:
                logger.warning("Could not process event file %s: %s", filepath.name, exc)
        return deleted

    @property
    def buffer_size(self) -> int:
        """Current number of events in ring buffer."""
        return len(self._buffer)

    @property
    def oldest_ts(self) -> str | None:
        """Timestamp of oldest event in buffer, or None if empty."""
        return self._buffer[0]["ts"] if self._buffer else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _daily_file(self) -> Path:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        return self._events_dir / f"decisions-{date_str}.jsonl"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_taxonomy_event_logger.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 5: Export from taxonomy __init__.py**

Add to `backend/app/services/taxonomy/__init__.py` imports and `__all__`:

```python
from app.services.taxonomy.event_logger import (
    TaxonomyEventLogger,
    get_event_logger,
    set_event_logger,
)
```

Add `"TaxonomyEventLogger"`, `"get_event_logger"`, `"set_event_logger"` to the `__all__` list.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/taxonomy/event_logger.py backend/tests/test_taxonomy_event_logger.py backend/app/services/taxonomy/__init__.py
git commit -m "feat: add TaxonomyEventLogger with JSONL persistence + ring buffer"
```

---

### Task 2: Lifespan Integration + API Endpoints

**Files:**
- Modify: `backend/app/main.py` (lifespan initialization + rotation)
- Modify: `backend/app/routers/clusters.py` (new endpoints)
- Modify: `backend/app/schemas/clusters.py` (response models)

- [ ] **Step 1: Initialize event logger in main.py lifespan**

In `backend/app/main.py`, near the taxonomy engine initialization (around line 99-110 where `set_engine()` is called), add:

```python
from app.services.taxonomy.event_logger import TaxonomyEventLogger, set_event_logger

taxonomy_event_logger = TaxonomyEventLogger(
    events_dir=DATA_DIR / "taxonomy_events",
    publish_to_bus=True,
)
set_event_logger(taxonomy_event_logger)
```

In the shutdown section (after the trace logger rotation, around line 697-703), add:

```python
from app.services.taxonomy.event_logger import get_event_logger
try:
    tel = get_event_logger()
    tel_deleted = tel.rotate(retention_days=settings.TRACE_RETENTION_DAYS)
    if tel_deleted:
        logger.info("Rotated %d old taxonomy event files", tel_deleted)
except RuntimeError:
    pass  # Logger not initialized (unlikely during shutdown)
```

- [ ] **Step 2: Add response schemas**

In `backend/app/schemas/clusters.py`, add at the end:

```python
class TaxonomyActivityEvent(BaseModel):
    """Single taxonomy decision event."""
    ts: str
    path: str
    op: str
    decision: str
    cluster_id: str | None = None
    optimization_id: str | None = None
    duration_ms: int | None = None
    context: dict = {}


class ActivityResponse(BaseModel):
    """Response for GET /api/clusters/activity."""
    events: list[TaxonomyActivityEvent]
    total_in_buffer: int
    oldest_ts: str | None = None


class ActivityHistoryResponse(BaseModel):
    """Response for GET /api/clusters/activity/history."""
    events: list[TaxonomyActivityEvent]
    total: int
    has_more: bool
```

- [ ] **Step 3: Add API endpoints**

In `backend/app/routers/clusters.py`, add the import at the top (with existing schema imports):

```python
from app.schemas.clusters import (
    # ... existing imports ...
    ActivityResponse,
    ActivityHistoryResponse,
    TaxonomyActivityEvent,
)
from app.services.taxonomy.event_logger import get_event_logger
```

Add two new endpoints (before the legacy redirect section at the bottom):

```python
@router.get("/api/clusters/activity")
async def get_cluster_activity(
    limit: int = Query(50, ge=1, le=200),
    path: str | None = Query(None, regex="^(hot|warm|cold)$"),
    op: str | None = Query(None),
    errors_only: bool = Query(False),
) -> ActivityResponse:
    """Recent taxonomy decision events from ring buffer."""
    try:
        tel = get_event_logger()
        op_filter = "error" if errors_only else op
        events = tel.get_recent(limit=limit, path=path, op=op_filter)
        return ActivityResponse(
            events=[TaxonomyActivityEvent(**e) for e in events],
            total_in_buffer=tel.buffer_size,
            oldest_ts=tel.oldest_ts,
        )
    except RuntimeError:
        return ActivityResponse(events=[], total_in_buffer=0)
    except Exception as exc:
        logger.error("GET /api/clusters/activity failed: %s", exc, exc_info=True)
        raise HTTPException(500, "Failed to load activity events") from exc


@router.get("/api/clusters/activity/history")
async def get_cluster_activity_history(
    date: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ActivityHistoryResponse:
    """Historical taxonomy events from JSONL file for a specific date."""
    try:
        tel = get_event_logger()
        events = tel.get_history(date=date, limit=limit + 1, offset=offset)
        has_more = len(events) > limit
        events = events[:limit]
        return ActivityHistoryResponse(
            events=[TaxonomyActivityEvent(**e) for e in events],
            total=len(events),
            has_more=has_more,
        )
    except RuntimeError:
        return ActivityHistoryResponse(events=[], total=0, has_more=False)
    except Exception as exc:
        logger.error("GET /api/clusters/activity/history failed: %s", exc, exc_info=True)
        raise HTTPException(500, "Failed to load activity history") from exc
```

- [ ] **Step 4: Verify endpoints start cleanly**

Run: `cd /home/drei/my_project/builder/claude-quickstarts/autonomous-coding/generations/PromptForge_v2 && ./init.sh restart && sleep 3 && curl -s http://localhost:8000/api/clusters/activity | python3 -m json.tool`
Expected: `{"events": [], "total_in_buffer": 0, "oldest_ts": null}`

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/routers/clusters.py backend/app/schemas/clusters.py
git commit -m "feat: taxonomy activity API endpoints + lifespan initialization"
```

---

### Task 3: Instrument Hot Path

**Files:**
- Modify: `backend/app/services/taxonomy/family_ops.py` (assign_cluster)
- Modify: `backend/app/services/taxonomy/engine.py` (process_optimization error handling)

- [ ] **Step 1: Instrument assign_cluster() in family_ops.py**

At the top of `family_ops.py`, add the import:

```python
from app.services.taxonomy.event_logger import get_event_logger
```

Inside `assign_cluster()` (lines 253-497), we need to:

**A)** Collect candidate evaluations. After the cosine search at line 314, before the `if matches and matches[0][1] > 0:` check, initialize a candidates list:

```python
        if centroids:
            _candidates_log: list[dict] = []  # Decision trace
            matches = EmbeddingService.cosine_search(embedding, centroids, top_k=1)
```

**B)** After computing `effective_score` (after line 337), log the candidate evaluation:

```python
                _candidates_log.append({
                    "id": matched.id,
                    "label": matched.label,
                    "raw_score": round(score, 4),
                    "threshold": round(threshold, 4),
                    "effective_score": round(effective_score, 4),
                    "member_count": matched.member_count or 0,
                    "penalties": {
                        "coherence": round((0.4 - (matched.coherence or 1.0)) * 0.3, 4) if matched.coherence is not None and matched.coherence < 0.4 else 0.0,
                        "output_coh": round((0.35 - (_out_coh or 1.0)) * 0.4, 4) if _out_coh is not None and _out_coh < 0.35 else 0.0,
                        "task_type": 0.12 if (task_type and matched.task_type and task_type != matched.task_type) else 0.0,
                    },
                })
```

**C)** After the successful merge return (line 411 `return matched`), right before the return, log the decision:

```python
                        try:
                            get_event_logger().log_decision(
                                path="hot", op="assign", decision="merge_into",
                                cluster_id=matched.id,
                                context={
                                    "candidates": _candidates_log,
                                    "winner_id": matched.id,
                                    "winner_label": matched.label,
                                    "new_cluster": False,
                                    "prompt_domain": domain,
                                    "prompt_task_type": task_type,
                                },
                            )
                        except RuntimeError:
                            pass
                        return matched
```

**D)** After the cross-domain merge prevention (line 351, where it falls through to creation), log that candidate with gate info:

```python
                        _candidates_log[-1]["gate"] = "cross_domain"
```

**E)** After the "Below adaptive threshold" debug log (line 418), also mark it:

```python
                    _candidates_log[-1]["gate"] = "below_threshold"
```

**F)** After the new cluster creation (around line 497 `return new_cluster`), log the create decision:

```python
    try:
        get_event_logger().log_decision(
            path="hot", op="assign", decision="create_new",
            cluster_id=new_cluster.id,
            context={
                "candidates": _candidates_log if 'centroids' in dir() and centroids else [],
                "winner_id": None,
                "new_cluster": True,
                "new_label": label,
                "prompt_domain": domain,
                "prompt_task_type": task_type,
                "parent_domain": domain_node.label if domain_node else None,
            },
        )
    except (RuntimeError, NameError):
        pass
    return new_cluster
```

- [ ] **Step 2: Instrument process_optimization error handler in engine.py**

In `engine.py`, at the top add:

```python
from app.services.taxonomy.event_logger import get_event_logger
```

After the successful commit and event publish (around line 376, after `logger.debug("Taxonomy extraction complete...")`), add a success event:

```python
            try:
                get_event_logger().log_decision(
                    path="hot", op="assign", decision="extraction_complete",
                    cluster_id=cluster.id,
                    optimization_id=optimization_id,
                    context={
                        "cluster_label": cluster.label,
                        "meta_patterns_added": len(meta_texts),
                        "reassigned_from": old_cluster_id if old_cluster_id and old_cluster_id != cluster.id else None,
                    },
                )
            except RuntimeError:
                pass
```

In the `except` block of `process_optimization()` (lines 389-395), add an error event:

```python
        except Exception as exc:
            logger.error(
                "Taxonomy process_optimization failed for %s: %s",
                optimization_id,
                exc,
                exc_info=True,
            )
            try:
                get_event_logger().log_decision(
                    path="hot", op="error", decision="failed",
                    optimization_id=optimization_id,
                    context={
                        "source": "process_optimization",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:500],
                        "recovery": "skipped",
                    },
                )
            except RuntimeError:
                pass
```

- [ ] **Step 3: Verify hot path instrumentation**

Run: `cd /home/drei/my_project/builder/claude-quickstarts/autonomous-coding/generations/PromptForge_v2 && ./init.sh restart`

Then optimize a prompt through the UI or MCP tool and check:

```bash
curl -s http://localhost:8000/api/clusters/activity | python3 -m json.tool
```

Expected: At least one `assign` event with `candidates` array and decision context.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/taxonomy/family_ops.py backend/app/services/taxonomy/engine.py
git commit -m "feat: instrument hot path assign_cluster with decision tracing"
```

---

### Task 4: Instrument Warm Path

**Files:**
- Modify: `backend/app/services/taxonomy/warm_path.py` (_run_speculative_phase Q-gate)
- Modify: `backend/app/services/taxonomy/warm_phases.py` (split, merge, retire, discover, reconcile, refresh)

- [ ] **Step 1: Instrument Q-gate in warm_path.py**

In `warm_path.py`, add import at the top:

```python
from app.services.taxonomy.event_logger import get_event_logger
```

In `_run_speculative_phase()`, after the non-regression gate decision (lines 142-159), add logging for both accept and reject paths.

Replace the existing accept/reject logging with enhanced versions. After `phase_result.accepted = True` (line 144) and before `return phase_result` (line 149):

```python
            phase_result.accepted = True
            logger.info(
                "Phase %s accepted: Q %.4f -> %.4f (ops=%d)",
                phase_name, q_before, q_after, phase_result.ops_accepted,
            )
            try:
                get_event_logger().log_decision(
                    path="warm", op="phase", decision="accepted",
                    context={
                        "phase_name": phase_name,
                        "q_before": round(q_before, 4),
                        "q_after": round(q_after, 4),
                        "delta": round(q_after - q_before, 4),
                        "operations": phase_result.operations[:10],  # cap for size
                        "ops_attempted": phase_result.ops_attempted,
                        "ops_accepted": phase_result.ops_accepted,
                    },
                )
            except RuntimeError:
                pass
            return phase_result
```

After `phase_result.accepted = False` (line 154) and before `return phase_result` (line 159):

```python
            phase_result.accepted = False
            logger.warning(
                "Phase %s rejected (Q regression): Q %.4f -> %.4f",
                phase_name, q_before, q_after,
            )
            try:
                get_event_logger().log_decision(
                    path="warm", op="phase", decision="rejected",
                    context={
                        "phase_name": phase_name,
                        "q_before": round(q_before, 4),
                        "q_after": round(q_after, 4),
                        "delta": round(q_after - q_before, 4),
                        "rejection_count": engine._phase_rejection_counters.get(phase_name, 0),
                    },
                )
            except RuntimeError:
                pass
            return phase_result
```

- [ ] **Step 2: Instrument warm_phases.py — split, merge, retire, reconcile, discover, refresh**

In `warm_phases.py`, add import at the top:

```python
from app.services.taxonomy.event_logger import get_event_logger
```

**A) phase_split_emerge** — After each successful `split_cluster()` call (around line 537), log the split event:

```python
        if split_res.success:
            try:
                get_event_logger().log_decision(
                    path="warm", op="split", decision="success",
                    cluster_id=node.id,
                    context={
                        "trigger": "coherence_floor",
                        "coherence": round(node.coherence or 0, 4),
                        "floor": round(dynamic_floor, 4),
                        "children_created": split_res.children_created,
                        "noise_reassigned": split_res.noise_reassigned,
                        "children": [
                            {"id": c.id, "label": c.label, "members": c.member_count or 0,
                             "coherence": round(c.coherence or 0, 3)}
                            for c in split_res.children
                        ],
                        "fallback": "none",
                    },
                )
            except RuntimeError:
                pass
```

**A2) phase_split_emerge — emerge events** — When a new cluster emerges (not from splitting, but from family formation), log the emerge event. Find the emerge operation within `phase_split_emerge()` and add:

```python
            try:
                get_event_logger().log_decision(
                    path="warm", op="emerge", decision="created",
                    cluster_id=new_node.id,
                    context={
                        "member_count": new_node.member_count or 0,
                        "coherence": round(new_node.coherence or 0, 4),
                        "domain": new_node.domain or "general",
                        "parent_id": new_node.parent_id,
                    },
                )
            except RuntimeError:
                pass
```

**B) phase_merge** — After each merge candidate evaluation (where `best_score >= merge_threshold` is checked), log the merge gate outcome. After a successful merge execution:

```python
            try:
                get_event_logger().log_decision(
                    path="warm", op="merge", decision="executed",
                    cluster_id=survivor.id,
                    context={
                        "pair": [node_a.id, node_b.id],
                        "labels": [node_a.label, node_b.label],
                        "similarity": round(best_score, 4),
                        "threshold": round(merge_threshold, 4),
                        "gate": "passed",
                        "survivor_id": survivor.id,
                        "combined_members": (survivor.member_count or 0),
                    },
                )
            except RuntimeError:
                pass
```

When a merge is blocked by a gate (coherence floor, output coherence, protection):

```python
            try:
                get_event_logger().log_decision(
                    path="warm", op="merge", decision="blocked",
                    context={
                        "pair": [node_a.id, node_b.id],
                        "labels": [node_a.label, node_b.label],
                        "similarity": round(best_score, 4),
                        "threshold": round(merge_threshold, 4),
                        "gate": gate_reason,  # "coherence_floor", "output_floor", "merge_protected"
                    },
                )
            except RuntimeError:
                pass
```

**C) phase_retire** — After each successful retirement:

```python
            try:
                get_event_logger().log_decision(
                    path="warm", op="retire", decision="executed",
                    cluster_id=node.id,
                    context={
                        "node_label": node.label,
                        "member_count_before": node.member_count or 0,
                        "sibling_target_id": getattr(retire_result, 'target_id', None),
                        "sibling_label": getattr(retire_result, 'target_label', None),
                    },
                )
            except RuntimeError:
                pass
```

**D) phase_reconcile** — After zombie archival summary:

```python
        if reconcile_result.zombies_archived > 0:
            try:
                get_event_logger().log_decision(
                    path="warm", op="reconcile", decision="zombies_archived",
                    context={
                        "count": reconcile_result.zombies_archived,
                        "member_counts_fixed": reconcile_result.member_counts_fixed,
                        "coherence_updated": reconcile_result.coherence_updated,
                    },
                )
            except RuntimeError:
                pass
```

**E) phase_discover** — After domain creation:

```python
            try:
                get_event_logger().log_decision(
                    path="warm", op="discover", decision="domain_created",
                    context={
                        "domain_label": domain_label,
                        "seed_cluster_id": seed.id if seed else None,
                        "consistency_pct": round(consistency * 100, 1),
                        "members_reparented": reparented_count,
                    },
                )
            except RuntimeError:
                pass
```

**F) phase_refresh** — After stale re-extraction:

```python
        if refresh_result.clusters_refreshed > 0:
            try:
                get_event_logger().log_decision(
                    path="warm", op="refresh", decision="patterns_refreshed",
                    context={"count": refresh_result.clusters_refreshed},
                )
            except RuntimeError:
                pass
```

- [ ] **Step 3: Verify warm path events**

Run: `cd /home/drei/my_project/builder/claude-quickstarts/autonomous-coding/generations/PromptForge_v2 && ./init.sh restart`

Trigger a recluster via UI or API and check:

```bash
curl -s 'http://localhost:8000/api/clusters/activity?path=warm' | python3 -m json.tool
```

Expected: Phase events with q_before/q_after, and any split/merge/retire events.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/taxonomy/warm_path.py backend/app/services/taxonomy/warm_phases.py
git commit -m "feat: instrument warm path phases with decision tracing"
```

---

### Task 5: Instrument Cold Path + Split

**Files:**
- Modify: `backend/app/services/taxonomy/cold_path.py` (refit, mega-cluster detection)
- Modify: `backend/app/services/taxonomy/split.py` (HDBSCAN, children, noise)

- [ ] **Step 1: Instrument cold_path.py**

In `cold_path.py`, add import at the top:

```python
from app.services.taxonomy.event_logger import get_event_logger
```

**A) After HDBSCAN refit result** — After `batch_cluster()` returns and clusters are processed, log the refit summary:

```python
        try:
            get_event_logger().log_decision(
                path="cold", op="refit", decision="accepted" if accepted else "rejected",
                context={
                    "clusters_input": len(active_clusters),
                    "hdbscan_clusters": hdbscan_result.n_clusters,
                    "q_before": round(q_before, 4),
                    "q_after": round(q_after, 4),
                },
            )
        except RuntimeError:
            pass
```

**B) Mega-cluster detection** — After each mega-cluster is identified for splitting:

```python
            try:
                get_event_logger().log_decision(
                    path="cold", op="split", decision="mega_cluster_detected",
                    cluster_id=mega.id,
                    context={
                        "trigger": "mega_cluster",
                        "member_count": mega.member_count or 0,
                        "coherence": round(mega.coherence or 0, 4),
                    },
                )
            except RuntimeError:
                pass
```

- [ ] **Step 2: Instrument split.py**

In `split.py`, add import at the top:

```python
from app.services.taxonomy.event_logger import get_event_logger
```

**A) After HDBSCAN/K-means result** — After the fallback logic (line 138), before child creation, log the split algorithm result:

```python
    # Log split algorithm result
    try:
        get_event_logger().log_decision(
            path="warm" if not hasattr(node, '_cold_split') else "cold",
            op="split", decision="algorithm_complete",
            cluster_id=node.id,
            context={
                "hdbscan_clusters": int(split_result.n_clusters),
                "noise_count": int(split_result.noise_count),
                "fallback": "kmeans" if split_result.n_clusters >= 2 and hasattr(split_result, '_km_fallback') else "none",
                "total_members": len(child_blended),
            },
        )
    except (RuntimeError, AttributeError):
        pass
```

**B) After all children created** — After the `if len(new_children) < 2` check (line 248), before archiving parent, log child creation summary:

```python
    # Log per-child creation
    try:
        get_event_logger().log_decision(
            path="warm", op="split", decision="children_created",
            cluster_id=node.id,
            context={
                "children": [
                    {"id": c.id, "label": c.label, "members": c.member_count or 0,
                     "coherence": round(c.coherence or 0, 3)}
                    for c in new_children
                ],
                "noise_count": len(noise_ids) if 'noise_ids' in dir() else 0,
            },
        )
    except RuntimeError:
        pass
```

**C) After noise reassignment** — After the noise loop (line 305), log summary:

```python
    if noise_reassigned > 0:
        try:
            get_event_logger().log_decision(
                path="warm", op="split", decision="noise_reassigned",
                cluster_id=node.id,
                context={"noise_reassigned": noise_reassigned},
            )
        except RuntimeError:
            pass
```

**D) Error handling** — Wrap existing `except` blocks with error events where split fails:

At the end of `split_cluster()`, if the function returns an unsuccessful result early (line 101 or 138), log it:

```python
    if len(child_blended) < SPLIT_MIN_MEMBERS:
        try:
            get_event_logger().log_decision(
                path="warm", op="split", decision="skipped",
                cluster_id=node.id,
                context={"reason": "too_few_members", "count": len(child_blended)},
            )
        except RuntimeError:
            pass
        return SplitResult(success=False, children_created=0, noise_reassigned=0)
```

- [ ] **Step 3: Verify cold path + split events**

Trigger a manual recluster:

```bash
curl -s -X POST http://localhost:8000/api/clusters/recluster | python3 -m json.tool
sleep 5
curl -s 'http://localhost:8000/api/clusters/activity?path=cold' | python3 -m json.tool
```

Expected: `refit` event with cluster counts and Q values. If mega-clusters exist, `split` events.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/taxonomy/cold_path.py backend/app/services/taxonomy/split.py
git commit -m "feat: instrument cold path + split with decision tracing"
```

---

### Task 6: Frontend API Client + Store

**Files:**
- Modify: `frontend/src/lib/api/clusters.ts` (new API functions + types)
- Modify: `frontend/src/lib/stores/clusters.svelte.ts` (activity state + methods)

- [ ] **Step 1: Add types and API functions to clusters.ts**

In `frontend/src/lib/api/clusters.ts`, add types before the `// -- API functions --` comment (around line 157):

```typescript
// -- Activity types --

export interface TaxonomyActivityEvent {
  ts: string;
  path: 'hot' | 'warm' | 'cold';
  op: string;
  decision: string;
  cluster_id?: string;
  optimization_id?: string;
  duration_ms?: number;
  context: Record<string, unknown>;
}

export interface ActivityResponse {
  events: TaxonomyActivityEvent[];
  total_in_buffer: number;
  oldest_ts: string | null;
}

export interface ActivityHistoryResponse {
  events: TaxonomyActivityEvent[];
  total: number;
  has_more: boolean;
}
```

At the end of the file (before the closing), add the API functions:

```typescript
export async function getClusterActivity(params?: {
  limit?: number;
  path?: string;
  op?: string;
  errors_only?: boolean;
}): Promise<ActivityResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set('limit', String(params.limit));
  if (params?.path) search.set('path', params.path);
  if (params?.op) search.set('op', params.op);
  if (params?.errors_only) search.set('errors_only', 'true');
  const qs = search.toString();
  return apiFetch<ActivityResponse>(`/clusters/activity${qs ? '?' + qs : ''}`);
}

export async function getClusterActivityHistory(
  date: string,
  params?: { limit?: number; offset?: number },
): Promise<ActivityHistoryResponse> {
  const search = new URLSearchParams({ date });
  if (params?.limit != null) search.set('limit', String(params.limit));
  if (params?.offset != null) search.set('offset', String(params.offset));
  return apiFetch<ActivityHistoryResponse>(`/clusters/activity/history?${search.toString()}`);
}
```

- [ ] **Step 2: Add activity state and methods to clusters.svelte.ts**

In `frontend/src/lib/stores/clusters.svelte.ts`, add the import:

```typescript
import type { TaxonomyActivityEvent } from '$lib/api/clusters';
import { getClusterActivity } from '$lib/api/clusters';
```

Add state properties (near other `$state` declarations at the top of the class):

```typescript
  // Activity panel state
  activityEvents = $state<TaxonomyActivityEvent[]>([]);
  activityOpen = $state(false);
  activityLoading = $state(false);
```

Add methods (near `invalidateClusters()`):

```typescript
  /** Load recent activity events from ring buffer. */
  async loadActivity(params?: { path?: string; op?: string }): Promise<void> {
    this.activityLoading = true;
    try {
      const resp = await getClusterActivity({ limit: 200, ...params });
      this.activityEvents = resp.events;
    } catch (err) {
      console.warn('Activity load failed:', err);
    } finally {
      this.activityLoading = false;
    }
  }

  /** Prepend a real-time activity event from SSE. */
  pushActivityEvent(event: TaxonomyActivityEvent): void {
    this.activityEvents = [event, ...this.activityEvents].slice(0, 200);
  }

  /** Toggle activity panel open/closed. Loads on first open. */
  toggleActivity(): void {
    this.activityOpen = !this.activityOpen;
    if (this.activityOpen && this.activityEvents.length === 0) {
      this.loadActivity();
    }
  }
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx svelte-check --threshold error 2>&1 | tail -10`
Expected: No errors related to activity types.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/clusters.ts frontend/src/lib/stores/clusters.svelte.ts
git commit -m "feat: frontend activity API client + store state"
```

---

### Task 7: Frontend ActivityPanel Component

**Files:**
- Create: `frontend/src/lib/components/taxonomy/ActivityPanel.svelte`

- [ ] **Step 1: Create ActivityPanel.svelte**

```svelte
<!-- frontend/src/lib/components/taxonomy/ActivityPanel.svelte -->
<script lang="ts">
  import { clustersStore } from '$lib/stores/clusters.svelte';
  import type { TaxonomyActivityEvent } from '$lib/api/clusters';
  import { tick } from 'svelte';

  // Reactive derived state
  const events = $derived(clustersStore.activityEvents);
  const loading = $derived(clustersStore.activityLoading);

  // Local filter state
  let pathFilter = $state<string | null>(null);
  let opFilter = $state<string | null>(null);
  let errorsOnly = $state(false);
  let expandedId = $state<string | null>(null);
  let pinToBottom = $state(true);

  let scrollContainer: HTMLDivElement | undefined;

  // Filtered events
  const filtered = $derived.by(() => {
    let result = events;
    if (pathFilter) result = result.filter(e => e.path === pathFilter);
    if (opFilter) result = result.filter(e => e.op === opFilter);
    if (errorsOnly) result = result.filter(e => e.op === 'error');
    return result;
  });

  // Auto-scroll on new events
  let prevCount = $state(0);
  $effect(() => {
    const count = filtered.length;
    if (count > prevCount && pinToBottom && scrollContainer) {
      tick().then(() => {
        scrollContainer?.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
    prevCount = count;
  });

  // Path filter chips
  const PATH_CHIPS = [
    { value: null, label: 'All' },
    { value: 'hot', label: 'Hot' },
    { value: 'warm', label: 'Warm' },
    { value: 'cold', label: 'Cold' },
  ] as const;

  // Decision color mapping
  function decisionColor(event: TaxonomyActivityEvent): string {
    if (event.op === 'error') return 'var(--color-neon-red, #ff2255)';
    const d = event.decision;
    if (d === 'merge_into' || d === 'accepted' || d === 'executed' || d === 'success')
      return 'var(--color-neon-green, #00ff88)';
    if (d === 'create_new' || d === 'domain_created' || d === 'children_created')
      return 'var(--color-neon-cyan, #00e5ff)';
    if (d === 'rejected' || d === 'blocked' || d === 'skipped')
      return 'var(--color-neon-yellow, #ffc800)';
    return 'var(--color-text-muted, #7a7a9e)';
  }

  // Op badge labels
  function opLabel(op: string): string {
    const map: Record<string, string> = {
      assign: 'ASSIGN', split: 'SPLIT', merge: 'MERGE', retire: 'RETIRE',
      phase: 'PHASE', refit: 'REFIT', discover: 'DISCOVER', emerge: 'EMERGE',
      reconcile: 'RECON', refresh: 'REFRESH', error: 'ERROR',
    };
    return map[op] ?? op.toUpperCase();
  }

  // Format timestamp
  function fmtTime(ts: string): string {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  }

  // Cluster click navigation
  function selectCluster(id: string | undefined) {
    if (id) {
      clustersStore.selectCluster(id);
    }
  }

  function toggleExpand(ts: string) {
    expandedId = expandedId === ts ? null : ts;
  }

  function reload() {
    clustersStore.loadActivity({
      path: pathFilter ?? undefined,
      op: errorsOnly ? 'error' : opFilter ?? undefined,
    });
  }
</script>

<div class="ap-container">
  <!-- Header -->
  <div class="ap-header">
    <span class="ap-title">ACTIVITY</span>
    <div class="ap-filters">
      {#each PATH_CHIPS as chip}
        <button
          class="ap-chip"
          class:ap-chip-active={pathFilter === chip.value}
          onclick={() => { pathFilter = chip.value; }}
        >{chip.label}</button>
      {/each}
      <button
        class="ap-chip ap-chip-error"
        class:ap-chip-active={errorsOnly}
        onclick={() => { errorsOnly = !errorsOnly; }}
      >Errors</button>
    </div>
    <div class="ap-actions">
      <button class="ap-btn" onclick={reload} title="Refresh">
        {#if loading}...{:else}↻{/if}
      </button>
      <button
        class="ap-btn"
        class:ap-btn-active={pinToBottom}
        onclick={() => { pinToBottom = !pinToBottom; }}
        title="Pin to top"
      >⤓</button>
      <button class="ap-btn" onclick={() => { clustersStore.activityOpen = false; }} title="Close">✕</button>
    </div>
  </div>

  <!-- Event list -->
  <div class="ap-list" bind:this={scrollContainer}>
    {#if filtered.length === 0}
      <div class="ap-empty">{loading ? 'Loading...' : 'No events'}</div>
    {:else}
      {#each filtered as event (event.ts + event.op + event.decision)}
        <button
          class="ap-row"
          onclick={() => toggleExpand(event.ts)}
        >
          <span class="ap-time">{fmtTime(event.ts)}</span>
          <span class="ap-path-badge" data-path={event.path}>{event.path.toUpperCase()}</span>
          <span class="ap-op-badge">{opLabel(event.op)}</span>
          <span class="ap-decision" style="color: {decisionColor(event)}">{event.decision}</span>
          {#if event.cluster_id}
            <button
              class="ap-cluster-link"
              onclick|stopPropagation={() => selectCluster(event.cluster_id)}
              title="Select in topology"
            >{event.context?.winner_label ?? event.context?.node_label ?? event.cluster_id?.slice(0, 8)}</button>
          {/if}
          {#if event.context?.q_before != null}
            <span class="ap-metric">Q {event.context.q_before} → {event.context.q_after}</span>
          {/if}
        </button>
        {#if expandedId === event.ts}
          <div class="ap-detail">
            <pre>{JSON.stringify(event.context, null, 2)}</pre>
          </div>
        {/if}
      {/each}
    {/if}
  </div>
</div>

<style>
  .ap-container {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    max-height: 40%;
    display: flex;
    flex-direction: column;
    background: rgba(10, 10, 14, 0.95);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px;
    z-index: 20;
  }

  .ap-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
  }

  .ap-title {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    color: rgba(255, 255, 255, 0.5);
  }

  .ap-filters {
    display: flex;
    gap: 4px;
    flex: 1;
  }

  .ap-chip {
    padding: 2px 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 10px;
    cursor: pointer;
    font-family: inherit;
  }
  .ap-chip:hover { color: rgba(255, 255, 255, 0.7); }
  .ap-chip-active {
    border-color: var(--color-neon-cyan, #00e5ff);
    color: var(--color-neon-cyan, #00e5ff);
  }
  .ap-chip-error.ap-chip-active {
    border-color: var(--color-neon-red, #ff2255);
    color: var(--color-neon-red, #ff2255);
  }

  .ap-actions {
    display: flex;
    gap: 4px;
  }

  .ap-btn {
    padding: 2px 6px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 11px;
    cursor: pointer;
    font-family: inherit;
  }
  .ap-btn:hover { color: rgba(255, 255, 255, 0.8); }
  .ap-btn-active { color: var(--color-neon-cyan, #00e5ff); }

  .ap-list {
    overflow-y: auto;
    flex: 1;
    min-height: 60px;
    max-height: 250px;
  }

  .ap-empty {
    padding: 16px;
    text-align: center;
    color: rgba(255, 255, 255, 0.25);
  }

  .ap-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    background: transparent;
    width: 100%;
    text-align: left;
    cursor: pointer;
    font-family: inherit;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.6);
  }
  .ap-row:hover { background: rgba(255, 255, 255, 0.03); }

  .ap-time {
    color: rgba(255, 255, 255, 0.3);
    flex-shrink: 0;
    width: 65px;
  }

  .ap-path-badge {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 1px 4px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    flex-shrink: 0;
    width: 36px;
    text-align: center;
  }
  .ap-path-badge[data-path="hot"] { border-color: #ff6b35; color: #ff6b35; }
  .ap-path-badge[data-path="warm"] { border-color: #ffc800; color: #ffc800; }
  .ap-path-badge[data-path="cold"] { border-color: #36b5ff; color: #36b5ff; }

  .ap-op-badge {
    font-size: 9px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.5);
    flex-shrink: 0;
    width: 52px;
  }

  .ap-decision {
    flex-shrink: 0;
  }

  .ap-cluster-link {
    border: none;
    background: none;
    color: var(--color-neon-cyan, #00e5ff);
    font-family: inherit;
    font-size: 11px;
    cursor: pointer;
    padding: 0;
    text-decoration: underline;
    text-decoration-style: dotted;
  }
  .ap-cluster-link:hover { opacity: 0.8; }

  .ap-metric {
    color: rgba(255, 255, 255, 0.3);
    margin-left: auto;
    flex-shrink: 0;
  }

  .ap-detail {
    padding: 6px 10px 6px 90px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }
  .ap-detail pre {
    margin: 0;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.45);
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 200px;
    overflow-y: auto;
  }
</style>
```

- [ ] **Step 2: Verify component compiles**

Run: `cd frontend && npx svelte-check --threshold error 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/taxonomy/ActivityPanel.svelte
git commit -m "feat: ActivityPanel component for taxonomy decision trace display"
```

---

### Task 8: Frontend Integration

**Files:**
- Modify: `frontend/src/lib/components/taxonomy/SemanticTopology.svelte` (add ActivityPanel)
- Modify: `frontend/src/lib/components/taxonomy/TopologyControls.svelte` (add toggle button)
- Modify: `frontend/src/routes/app/+page.svelte` (SSE handler for taxonomy_activity)

- [ ] **Step 1: Add SSE handler in +page.svelte**

In `frontend/src/routes/app/+page.svelte`, after the `taxonomy_changed` handler (around line 119), add:

```typescript
      if (type === 'taxonomy_activity') {
        clustersStore.pushActivityEvent(data as import('$lib/api/clusters').TaxonomyActivityEvent);
      }
```

- [ ] **Step 2: Add activity toggle to TopologyControls.svelte**

In `frontend/src/lib/components/taxonomy/TopologyControls.svelte`, in the LAYERS section (around line 63-88 where the toggle buttons are), add a new toggle after the existing ones:

```svelte
      <button
        class="tc-toggle"
        class:tc-toggle-active={clustersStore.activityOpen}
        style="--toggle-color: #ffc800"
        onclick={() => { clustersStore.toggleActivity(); }}
      >
        <span class="tc-toggle-dot"></span>
        Activity
      </button>
```

- [ ] **Step 3: Add ActivityPanel to SemanticTopology.svelte**

In `frontend/src/lib/components/taxonomy/SemanticTopology.svelte`, add the import at the top of the script:

```typescript
  import ActivityPanel from './ActivityPanel.svelte';
```

In the template, after the `TopologyControls` component (around line 689), add:

```svelte
  {#if clustersStore.activityOpen}
    <ActivityPanel />
  {/if}
```

- [ ] **Step 4: Verify end-to-end**

1. Run: `cd /home/drei/my_project/builder/claude-quickstarts/autonomous-coding/generations/PromptForge_v2 && ./init.sh restart`
2. Open the app in browser, navigate to the Topology view
3. Click the "Activity" toggle in the controls panel
4. Optimize a prompt — activity events should appear in real-time
5. Click a cluster name in the activity feed — should select in topology

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/app/+page.svelte frontend/src/lib/components/taxonomy/TopologyControls.svelte frontend/src/lib/components/taxonomy/SemanticTopology.svelte
git commit -m "feat: wire ActivityPanel into topology view + SSE handler"
```

---

### Task 9: Verify Complete System

- [ ] **Step 1: Backend test suite**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_taxonomy_event_logger.py -v`
Expected: All tests PASS.

- [ ] **Step 2: Frontend type check**

Run: `cd frontend && npx svelte-check --threshold error`
Expected: No errors.

- [ ] **Step 3: JSONL persistence check**

After optimizing a prompt:

```bash
ls -la data/taxonomy_events/
cat data/taxonomy_events/decisions-$(date -u +%Y-%m-%d).jsonl | python3 -m json.tool --no-ensure-ascii | head -50
```

Expected: JSONL file with structured events.

- [ ] **Step 4: API endpoint check**

```bash
curl -s http://localhost:8000/api/clusters/activity | python3 -m json.tool
curl -s "http://localhost:8000/api/clusters/activity?path=hot" | python3 -m json.tool
curl -s "http://localhost:8000/api/clusters/activity/history?date=$(date -u +%Y-%m-%d)" | python3 -m json.tool
```

- [ ] **Step 5: SSE streaming check**

Open browser dev tools, Network tab, filter for `events`. After optimizing a prompt, verify `taxonomy_activity` events appear in the SSE stream.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: taxonomy engine observability — complete implementation"
```
