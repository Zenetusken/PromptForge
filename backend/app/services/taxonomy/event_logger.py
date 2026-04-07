"""TaxonomyEventLogger — structured decision tracing for taxonomy engine.

Dual-writes to:
  1. Daily JSONL files in data/taxonomy_events/ (persistence)
  2. In-memory ring buffer (real-time reads via API)

Optionally publishes to the EventBus for SSE streaming.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum number of failed events to keep for retry on next successful delivery.
_MAX_RETRY_QUEUE = 50

# URL for cross-process event forwarding (must match events router).
_PUBLISH_URL = "http://127.0.0.1:8000/api/events/_publish"

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


def reset_event_logger() -> None:
    """Clear the process singleton (test cleanup only)."""
    global _instance
    _instance = None


# ---------------------------------------------------------------------------
# Logger class
# ---------------------------------------------------------------------------


class TaxonomyEventLogger:
    """Structured decision event logger for taxonomy hot/warm/cold paths."""

    def __init__(
        self,
        events_dir: str | Path = "data/taxonomy_events",
        publish_to_bus: bool = True,
        cross_process: bool = False,
        buffer_size: int = 500,
    ) -> None:
        self._events_dir = Path(events_dir)
        self._events_dir.mkdir(parents=True, exist_ok=True)
        self._publish_to_bus = publish_to_bus
        self._cross_process = cross_process
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        # Consecutive dedup: suppress truly back-to-back identical events.
        # Only the single most recent event is tracked (not per-key), so
        # non-consecutive events with identical payloads are never falsely
        # suppressed — fixing the over-suppression bug where two Q-gate
        # evaluations with the same scores in different phases were dropped.
        self._last_dedup_signature: str | None = None
        # Track pending cross-process forwarding tasks so they aren't
        # silently cancelled on shutdown.  Regular set with cleanup in
        # _on_forward_done to avoid relying on CPython's asyncio internals
        # for task liveness.
        self._pending_tasks: set[asyncio.Task] = set()
        # Bounded retry queue for events that failed cross-process
        # forwarding.  Drained on next successful delivery.
        self._retry_queue: deque[dict[str, Any]] = deque(maxlen=_MAX_RETRY_QUEUE)

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
        # Consecutive dedup: suppress truly back-to-back identical events.
        # Only the immediately preceding event is checked — if ANY other
        # event was logged in between, the same payload is allowed through.
        # This prevents over-suppression of semantically different events
        # that happen to share identical context (e.g., two Q-gate
        # evaluations with the same scores across different warm phases).
        _sig = hashlib.md5(json.dumps(
            {"path": path, "op": op, "decision": decision,
             "cluster_id": cluster_id, "context": context or {}},
            sort_keys=True, default=str,
        ).encode()).hexdigest()
        if _sig == self._last_dedup_signature:
            return  # Suppress consecutive duplicate
        self._last_dedup_signature = _sig

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

        # 3. Publish for SSE delivery
        if self._publish_to_bus:
            try:
                from app.services.event_bus import event_bus
                event_bus.publish("taxonomy_activity", event)
            except Exception as _bus_exc:
                logger.warning(
                    "SSE bridge publish failed for %s/%s: %s",
                    op, decision, _bus_exc,
                )
        elif self._cross_process:
            # MCP server process: forward via HTTP to backend's event bus.
            # Tasks are tracked so they can be drained on shutdown instead
            # of being silently cancelled.
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(
                    self._forward_with_retry(event, op, decision),
                    name=f"taxonomy_fwd_{op}_{decision}",
                )
                self._pending_tasks.add(task)
                task.add_done_callback(self._on_forward_done)
                logger.debug("Cross-process event queued: %s/%s", op, decision)
            except RuntimeError:
                # No running event loop — fall back to synchronous HTTP POST
                # so events aren't silently dropped to JSONL-only.
                self._forward_sync(event, op, decision)
            except Exception as _cp_exc:
                logger.warning(
                    "Cross-process notification failed for %s/%s: %s",
                    op, decision, _cp_exc,
                )
                self._retry_queue.append(event)

    # ------------------------------------------------------------------
    # Cross-process forwarding helpers
    # ------------------------------------------------------------------

    def _forward_sync(self, event: dict[str, Any], op: str, decision: str) -> None:
        """Synchronous HTTP POST fallback when no asyncio event loop is running.

        Runs in a daemon thread to avoid blocking the caller.  This ensures
        events logged from synchronous contexts (thread-pool tasks, sync
        helpers) are not silently dropped to JSONL-only.
        """
        def _post() -> None:
            try:
                import httpx
                httpx.post(
                    _PUBLISH_URL,
                    json={"event_type": "taxonomy_activity", "data": event},
                    timeout=5.0,
                ).raise_for_status()
                logger.debug("Cross-process sync forward OK: %s/%s", op, decision)
            except Exception as exc:
                logger.warning(
                    "Cross-process sync forward failed for %s/%s: %s — queued for retry",
                    op, decision, exc,
                )
                self._retry_queue.append(event)

        t = threading.Thread(target=_post, daemon=True, name=f"taxonomy_sync_fwd_{op}")
        t.start()

    async def _forward_with_retry(
        self, event: dict[str, Any], op: str, decision: str,
    ) -> None:
        """Forward an event and drain any pending retries on success."""
        from app.services.event_notification import notify_event_bus

        try:
            await notify_event_bus("taxonomy_activity", event)
        except Exception:
            self._retry_queue.append(event)
            raise

        # Success — drain retry queue while we have a working connection.
        while self._retry_queue:
            stale_event = self._retry_queue.popleft()
            try:
                await notify_event_bus("taxonomy_activity", stale_event)
                logger.info(
                    "Retry-delivered stale cross-process event: %s/%s",
                    stale_event.get("op", "?"), stale_event.get("decision", "?"),
                )
            except Exception as exc:
                # Put it back and stop draining — backend is struggling again.
                self._retry_queue.appendleft(stale_event)
                logger.debug("Retry drain stopped: %s", exc)
                break

    # ------------------------------------------------------------------
    # Task tracking
    # ------------------------------------------------------------------

    def _on_forward_done(self, task: asyncio.Task) -> None:
        """Callback for completed cross-process forwarding tasks.

        Removes the task from the pending set and logs failures.
        Failed events are already in the retry queue (added by
        ``_forward_with_retry``).
        """
        self._pending_tasks.discard(task)
        if task.cancelled():
            logger.warning("Cross-process forwarding task cancelled: %s", task.get_name())

    async def drain_pending(self, timeout: float = 10.0) -> int:
        """Await all pending cross-process forwarding tasks.

        Call during shutdown to avoid silently dropping events.
        Returns the number of tasks that were still pending.
        """
        tasks = [t for t in self._pending_tasks if not t.done()]
        if not tasks:
            return 0
        logger.info("Draining %d pending cross-process event tasks (timeout=%.1fs)", len(tasks), timeout)
        done, pending = await asyncio.wait(tasks, timeout=timeout)
        if pending:
            logger.warning(
                "%d cross-process event tasks did not complete within %.1fs — cancelling",
                len(pending), timeout,
            )
            for t in pending:
                t.cancel()
        return len(tasks)

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

    @property
    def retry_queue_size(self) -> int:
        """Number of events waiting to be retried."""
        return len(self._retry_queue)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _daily_file(self) -> Path:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        return self._events_dir / f"decisions-{date_str}.jsonl"
