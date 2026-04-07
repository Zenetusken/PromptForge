"""Tests for event delivery chain reliability fixes.

Covers:
  Fix 1 — sync fallback for cross-process forwarding (no event loop)
  Fix 2 — lazy-init ring buffer in _publish endpoint
  Fix 3 — retry queue for failed cross-process events
  Fix 4 — increased replay buffer for warm-path bursts
  Fix 5 — single-previous-event dedup prevents over-suppression
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.event_bus import _REPLAY_BUFFER_SIZE, EventBus
from app.services.taxonomy.event_logger import (
    _MAX_RETRY_QUEUE,
    TaxonomyEventLogger,
    reset_event_logger,
    set_event_logger,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tel(tmp_path: Path) -> TaxonomyEventLogger:
    """Cross-process event logger (like MCP server)."""
    return TaxonomyEventLogger(
        events_dir=tmp_path, publish_to_bus=False, cross_process=True,
    )


@pytest.fixture
def local_tel(tmp_path: Path) -> TaxonomyEventLogger:
    """Local event logger (like backend process)."""
    return TaxonomyEventLogger(
        events_dir=tmp_path, publish_to_bus=False, cross_process=False,
    )


# ---------------------------------------------------------------------------
# Fix 1 — Sync fallback when no event loop is running
# ---------------------------------------------------------------------------


class TestSyncFallback:
    """When log_decision is called outside an async context, events should
    still be forwarded via synchronous HTTP POST in a daemon thread."""

    def test_forward_sync_calls_httpx_post(self, tel: TaxonomyEventLogger) -> None:
        """_forward_sync should POST to the backend endpoint in a thread."""
        event = {"ts": "2026-04-06T00:00:00Z", "path": "hot", "op": "assign", "decision": "merge_into"}

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            original_forward = tel._forward_sync

            def tracked_forward(ev, op, dec):
                original_forward(ev, op, dec)

            tracked_forward(event, "assign", "merge_into")
            # Wait for daemon thread to finish
            time.sleep(1.0)

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["event_type"] == "taxonomy_activity"
            assert call_kwargs["json"]["data"] == event

    def test_forward_sync_failure_queues_retry(self, tel: TaxonomyEventLogger) -> None:
        """Failed sync forward should add event to retry queue."""
        event = {"path": "hot", "op": "score", "decision": "scored"}

        with patch("httpx.post", side_effect=ConnectionError("backend down")):
            tel._forward_sync(event, "score", "scored")
            time.sleep(1.0)

        assert tel.retry_queue_size >= 1

    def test_log_decision_no_loop_uses_sync(self, tel: TaxonomyEventLogger) -> None:
        """log_decision from sync context (no event loop) should use sync fallback."""
        with patch.object(tel, '_forward_sync') as mock_sync:
            tel.log_decision(
                path="hot", op="assign", decision="merge_into",
                context={"test": True},
            )
            mock_sync.assert_called_once()


# ---------------------------------------------------------------------------
# Fix 2 — Lazy-init ring buffer in _publish endpoint
# ---------------------------------------------------------------------------


class TestLazyInitRingBuffer:
    """The _publish endpoint should lazy-init the event logger rather than
    silently dropping events from the ring buffer."""

    @pytest.mark.asyncio
    async def test_publish_inits_logger_when_missing(self, app_client: AsyncClient) -> None:
        """POST to _publish with taxonomy_activity should lazy-init the logger."""
        reset_event_logger()

        payload = {
            "event_type": "taxonomy_activity",
            "data": {
                "ts": "2026-04-06T00:00:00Z",
                "path": "warm",
                "op": "phase",
                "decision": "accepted",
            },
        }
        response = await app_client.post("/api/events/_publish", json=payload)
        assert response.status_code == 200

        from app.services.taxonomy.event_logger import get_event_logger
        tel = get_event_logger()
        assert tel.buffer_size >= 1
        assert tel._buffer[-1]["op"] == "phase"

    @pytest.mark.asyncio
    async def test_publish_appends_to_existing_logger(self, app_client: AsyncClient) -> None:
        """If logger already exists, events are simply appended."""
        existing = TaxonomyEventLogger(publish_to_bus=False)
        set_event_logger(existing)

        payload = {
            "event_type": "taxonomy_activity",
            "data": {"ts": "now", "path": "hot", "op": "assign", "decision": "create_new"},
        }
        response = await app_client.post("/api/events/_publish", json=payload)
        assert response.status_code == 200
        assert existing.buffer_size >= 1


# ---------------------------------------------------------------------------
# Fix 3 — Retry queue for failed cross-process events
# ---------------------------------------------------------------------------


class TestRetryQueue:
    """Failed forward events should be queued and drained on next success."""

    @pytest.mark.asyncio
    async def test_forward_failure_queues_event(self, tel: TaxonomyEventLogger) -> None:
        """When forwarding fails, the event is added to the retry queue."""
        event = {"path": "warm", "op": "merge", "decision": "accepted"}

        with patch(
            "app.services.event_notification.notify_event_bus",
            new_callable=AsyncMock,
            side_effect=ConnectionError("backend down"),
        ):
            with pytest.raises(ConnectionError):
                await tel._forward_with_retry(event, "merge", "accepted")

        assert tel.retry_queue_size == 1
        assert tel._retry_queue[0] == event

    @pytest.mark.asyncio
    async def test_success_drains_retry_queue(self, tel: TaxonomyEventLogger) -> None:
        """Successful forward should drain pending retries."""
        stale_event = {"path": "hot", "op": "score", "decision": "scored"}
        tel._retry_queue.append(stale_event)
        assert tel.retry_queue_size == 1

        new_event = {"path": "warm", "op": "phase", "decision": "accepted"}

        with patch(
            "app.services.event_notification.notify_event_bus",
            new_callable=AsyncMock,
        ) as mock_notify:
            await tel._forward_with_retry(new_event, "phase", "accepted")

        assert mock_notify.call_count == 2
        assert tel.retry_queue_size == 0

    @pytest.mark.asyncio
    async def test_retry_drain_stops_on_failure(self, tel: TaxonomyEventLogger) -> None:
        """If draining retries fails, remaining events stay in the queue."""
        for i in range(3):
            tel._retry_queue.append({"path": "hot", "op": "assign", "decision": f"d{i}"})

        new_event = {"path": "warm", "op": "phase", "decision": "accepted"}
        call_count = 0

        async def selective_fail(event_type, data):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise ConnectionError("backend struggling")

        with patch(
            "app.services.event_notification.notify_event_bus",
            new_callable=AsyncMock,
            side_effect=selective_fail,
        ):
            await tel._forward_with_retry(new_event, "phase", "accepted")

        # 1 succeeded, 1 failed (re-queued), 1 never attempted = 2 remain
        assert tel.retry_queue_size == 2

    def test_retry_queue_bounded(self, tel: TaxonomyEventLogger) -> None:
        """Retry queue should not grow beyond _MAX_RETRY_QUEUE."""
        for i in range(_MAX_RETRY_QUEUE + 10):
            tel._retry_queue.append({"i": i})
        assert tel.retry_queue_size == _MAX_RETRY_QUEUE

    @pytest.mark.asyncio
    async def test_on_forward_done_no_exception_on_cancel(self, tel: TaxonomyEventLogger) -> None:
        """Cancelled tasks should be logged but not crash."""
        task = asyncio.create_task(asyncio.sleep(100))
        tel._pending_tasks.add(task)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        tel._on_forward_done(task)
        assert task not in tel._pending_tasks


# ---------------------------------------------------------------------------
# Fix 4 — Replay buffer size increased
# ---------------------------------------------------------------------------


class TestReplayBufferSize:
    """Replay buffer should be large enough to survive warm-path bursts."""

    def test_replay_buffer_size_at_least_500(self) -> None:
        assert _REPLAY_BUFFER_SIZE >= 500

    def test_replay_buffer_holds_500_events(self) -> None:
        bus = EventBus()
        for i in range(500):
            bus.publish("burst", {"i": i})
        assert len(bus.replay_since(0)) == 500

    def test_replay_evicts_beyond_capacity(self) -> None:
        bus = EventBus()
        for i in range(_REPLAY_BUFFER_SIZE + 100):
            bus.publish("x", {"i": i})

        all_events = bus.replay_since(0)
        assert len(all_events) == _REPLAY_BUFFER_SIZE
        assert all_events[0]["data"]["i"] == 100


# ---------------------------------------------------------------------------
# Fix 5 — Single-previous-event dedup prevents over-suppression
# ---------------------------------------------------------------------------


class TestDedup:
    """Dedup now tracks only the single most recent event, so non-consecutive
    identical events are not falsely suppressed."""

    def test_consecutive_identical_suppressed(
        self, local_tel: TaxonomyEventLogger,
    ) -> None:
        """Two truly consecutive identical calls should dedup."""
        local_tel.log_decision(
            path="warm", op="phase", decision="accepted",
            context={"q_before": 0.5, "q_after": 0.6},
        )
        local_tel.log_decision(
            path="warm", op="phase", decision="accepted",
            context={"q_before": 0.5, "q_after": 0.6},
        )
        assert local_tel.buffer_size == 1

    def test_non_consecutive_identical_allowed(
        self, local_tel: TaxonomyEventLogger,
    ) -> None:
        """Same event separated by a different event should NOT be suppressed.
        This was the original over-suppression bug with per-key dedup."""
        ctx = {"q_before": 0.5, "q_after": 0.6}
        local_tel.log_decision(path="warm", op="phase", decision="accepted", context=ctx)
        # Intervening different event resets the single-previous tracker
        local_tel.log_decision(path="hot", op="assign", decision="merge_into", context={})
        local_tel.log_decision(path="warm", op="phase", decision="accepted", context=ctx)
        assert local_tel.buffer_size == 3

    def test_different_context_never_deduped(
        self, local_tel: TaxonomyEventLogger,
    ) -> None:
        """Events with different context are never suppressed."""
        local_tel.log_decision(
            path="warm", op="phase", decision="accepted",
            context={"q_before": 0.5, "q_after": 0.6},
        )
        local_tel.log_decision(
            path="warm", op="phase", decision="accepted",
            context={"q_before": 0.6, "q_after": 0.7},
        )
        assert local_tel.buffer_size == 2

    def test_different_ops_never_deduped(
        self, local_tel: TaxonomyEventLogger,
    ) -> None:
        """Events with different (path, op, decision) are independent."""
        local_tel.log_decision(path="hot", op="assign", decision="merge_into", context={})
        local_tel.log_decision(path="warm", op="merge", decision="accepted", context={})
        local_tel.log_decision(path="hot", op="assign", decision="merge_into", context={})
        assert local_tel.buffer_size == 3

    def test_dedup_signature_tracks_last_event(
        self, local_tel: TaxonomyEventLogger,
    ) -> None:
        """The _last_dedup_signature should update on every non-suppressed event."""
        assert local_tel._last_dedup_signature is None
        local_tel.log_decision(path="hot", op="assign", decision="create_new", context={"i": 1})
        sig1 = local_tel._last_dedup_signature
        assert sig1 is not None

        local_tel.log_decision(path="hot", op="assign", decision="create_new", context={"i": 2})
        sig2 = local_tel._last_dedup_signature
        assert sig2 != sig1  # Different context = different signature
