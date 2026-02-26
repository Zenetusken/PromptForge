"""Tests for the MCP Activity Broadcaster and SSE router.

Covers the MCPActivityBroadcaster (in-memory event fanout, history tracking,
get_history_after), and the SSE generator (id: field, Last-Event-ID support).
"""

import json

import pytest

from app.services.mcp_activity import MCPActivityBroadcaster, MCPActivityEvent, MCPEventType

# ── MCPActivityBroadcaster unit tests ──


class TestBroadcasterPublish:
    def test_publish_adds_to_history(self):
        b = MCPActivityBroadcaster()
        event = MCPActivityEvent(event_type=MCPEventType.tool_complete, tool_name="optimize")
        b.publish(event)
        assert len(b._history) == 1
        assert b._history[0] is event

    def test_history_bounded_to_100(self):
        b = MCPActivityBroadcaster()
        for i in range(120):
            b.publish(MCPActivityEvent(event_type=MCPEventType.tool_complete, tool_name=f"t{i}"))
        assert len(b._history) == 100
        assert b._history[0].tool_name == "t20"

    def test_recent_history_returns_last_20(self):
        b = MCPActivityBroadcaster()
        for i in range(50):
            b.publish(MCPActivityEvent(event_type=MCPEventType.tool_complete, tool_name=f"t{i}"))
        recent = b.recent_history
        assert len(recent) == 20
        assert recent[0].tool_name == "t30"
        assert recent[-1].tool_name == "t49"

    def test_recent_history_returns_all_when_fewer_than_20(self):
        b = MCPActivityBroadcaster()
        for i in range(5):
            b.publish(MCPActivityEvent(event_type=MCPEventType.tool_complete, tool_name=f"t{i}"))
        assert len(b.recent_history) == 5

    def test_active_calls_tracked(self):
        b = MCPActivityBroadcaster()
        b.publish(
            MCPActivityEvent(
                event_type=MCPEventType.tool_start, tool_name="optimize", call_id="c1"
            )
        )
        assert "c1" in b._active_calls
        b.publish(
            MCPActivityEvent(
                event_type=MCPEventType.tool_complete, tool_name="optimize", call_id="c1"
            )
        )
        assert "c1" not in b._active_calls

    def test_tool_error_removes_active_call(self):
        b = MCPActivityBroadcaster()
        b.publish(
            MCPActivityEvent(
                event_type=MCPEventType.tool_start, tool_name="optimize", call_id="c2"
            )
        )
        b.publish(
            MCPActivityEvent(
                event_type=MCPEventType.tool_error, tool_name="optimize", call_id="c2"
            )
        )
        assert "c2" not in b._active_calls

    def test_tool_progress_updates_active_call(self):
        b = MCPActivityBroadcaster()
        b.publish(
            MCPActivityEvent(
                event_type=MCPEventType.tool_start, tool_name="optimize", call_id="c3"
            )
        )
        b.publish(
            MCPActivityEvent(
                event_type=MCPEventType.tool_progress,
                tool_name="optimize",
                call_id="c3",
                progress=0.5,
            )
        )
        assert b._active_calls["c3"].progress == 0.5

    def test_session_count_tracked(self):
        b = MCPActivityBroadcaster()
        b.publish(MCPActivityEvent(event_type=MCPEventType.session_connect))
        assert b._session_count == 1
        b.publish(MCPActivityEvent(event_type=MCPEventType.session_disconnect))
        assert b._session_count == 0
        # Can't go below zero
        b.publish(MCPActivityEvent(event_type=MCPEventType.session_disconnect))
        assert b._session_count == 0


class TestGetHistoryAfter:
    def _make_broadcaster_with_events(
        self, n: int
    ) -> tuple[MCPActivityBroadcaster, list[MCPActivityEvent]]:
        b = MCPActivityBroadcaster()
        events = []
        for i in range(n):
            e = MCPActivityEvent(event_type=MCPEventType.tool_complete, tool_name=f"tool_{i}")
            b.publish(e)
            events.append(e)
        return b, events

    def test_returns_events_after_known_id(self):
        b, events = self._make_broadcaster_with_events(5)
        after = b.get_history_after(events[2].id)
        assert len(after) == 2
        assert after[0].tool_name == "tool_3"
        assert after[1].tool_name == "tool_4"

    def test_returns_empty_after_last_event(self):
        b, events = self._make_broadcaster_with_events(5)
        after = b.get_history_after(events[4].id)
        assert after == []

    def test_returns_all_after_first_event(self):
        b, events = self._make_broadcaster_with_events(5)
        after = b.get_history_after(events[0].id)
        assert len(after) == 4
        assert after[0].tool_name == "tool_1"

    def test_falls_back_to_recent_history_for_unknown_id(self):
        b, events = self._make_broadcaster_with_events(5)
        fallback = b.get_history_after("nonexistent-id")
        assert len(fallback) == 5
        assert fallback == b.recent_history

    def test_falls_back_when_id_aged_out(self):
        b = MCPActivityBroadcaster()
        old_event = MCPActivityEvent(
            event_type=MCPEventType.tool_complete, tool_name="old"
        )
        b.publish(old_event)
        old_id = old_event.id
        for i in range(100):
            b.publish(
                MCPActivityEvent(event_type=MCPEventType.tool_complete, tool_name=f"new_{i}")
            )
        assert not any(e.id == old_id for e in b._history)
        fallback = b.get_history_after(old_id)
        assert fallback == b.recent_history


class TestGetStatus:
    def test_status_shape(self):
        b = MCPActivityBroadcaster()
        status = b.get_status()
        assert "subscriber_count" in status
        assert "active_calls" in status
        assert "session_count" in status
        assert "total_events" in status

    def test_status_reflects_active_calls(self):
        b = MCPActivityBroadcaster()
        b.publish(
            MCPActivityEvent(
                event_type=MCPEventType.tool_start, tool_name="optimize", call_id="c1"
            )
        )
        status = b.get_status()
        assert len(status["active_calls"]) == 1
        assert status["active_calls"][0]["call_id"] == "c1"


class TestSubscriberFanout:
    @pytest.mark.asyncio
    async def test_subscriber_receives_events(self):
        b = MCPActivityBroadcaster()
        queue = b.subscribe()
        event = MCPActivityEvent(event_type=MCPEventType.tool_complete, tool_name="test")
        b.publish(event)
        received = queue.get_nowait()
        assert received.tool_name == "test"
        b.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_unsubscribed_queue_stops_receiving(self):
        b = MCPActivityBroadcaster()
        queue = b.subscribe()
        b.unsubscribe(queue)
        b.publish(MCPActivityEvent(event_type=MCPEventType.tool_complete))
        assert queue.empty()


# ── SSE event format tests ──


class TestSSEEventFormat:
    def test_to_sse_contains_id(self):
        event = MCPActivityEvent(
            event_type=MCPEventType.tool_complete, tool_name="optimize"
        )
        sse_data = json.loads(event.to_sse())
        assert "id" in sse_data
        assert sse_data["id"] == event.id

    def test_to_sse_strips_none_values(self):
        event = MCPActivityEvent(event_type=MCPEventType.tool_complete)
        sse_data = json.loads(event.to_sse())
        assert "tool_name" not in sse_data
        assert "call_id" not in sse_data
        assert "error" not in sse_data


# ── SSE generator snapshot tests ──
# Test the snapshot phase of _sse_generator by collecting only the yielded
# values before the generator enters the blocking live stream loop.


class TestSSEGeneratorSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_includes_id_field(self):
        """SSE generator snapshot output includes 'id:' lines for activity events."""
        from app.routers.mcp_activity import _sse_generator

        # Use a fresh broadcaster to control the test state
        b = MCPActivityBroadcaster()
        event = MCPActivityEvent(
            event_type=MCPEventType.tool_complete, tool_name="id_test"
        )
        b.publish(event)

        # Monkey-patch the module-level singleton for this test
        import app.routers.mcp_activity as router_mod

        original = router_mod.mcp_activity
        router_mod.mcp_activity = b
        try:
            chunks = []
            gen = _sse_generator()
            async for chunk in gen:
                chunks.append(chunk)
                # The snapshot phase yields status + history, then enters the
                # live loop which blocks on queue.get(). After history is done,
                # next yield won't happen until a live event or keepalive.
                # We break after finding our test event.
                if "id_test" in chunk:
                    break

            activity_chunks = [c for c in chunks if "mcp_activity" in c and "id_test" in c]
            assert len(activity_chunks) == 1
            assert f"id: {event.id}" in activity_chunks[0]
        finally:
            router_mod.mcp_activity = original

    @pytest.mark.asyncio
    async def test_fresh_connect_sends_recent_history(self):
        """Without Last-Event-ID, snapshot sends recent_history."""
        from app.routers.mcp_activity import _sse_generator

        b = MCPActivityBroadcaster()
        events = []
        for i in range(5):
            e = MCPActivityEvent(
                event_type=MCPEventType.tool_complete, tool_name=f"fresh_{i}"
            )
            b.publish(e)
            events.append(e)

        import app.routers.mcp_activity as router_mod

        original = router_mod.mcp_activity
        router_mod.mcp_activity = b
        try:
            chunks = []
            gen = _sse_generator()
            async for chunk in gen:
                chunks.append(chunk)
                if "fresh_4" in chunk:
                    break

            activity_chunks = [c for c in chunks if "mcp_activity" in c]
            tool_names = []
            for chunk in activity_chunks:
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("tool_name", "").startswith("fresh_"):
                            tool_names.append(data["tool_name"])

            # All 5 events sent (fewer than 20 = recent_history returns all)
            assert tool_names == ["fresh_0", "fresh_1", "fresh_2", "fresh_3", "fresh_4"]
        finally:
            router_mod.mcp_activity = original

    @pytest.mark.asyncio
    async def test_last_event_id_sends_gap_fill(self):
        """With Last-Event-ID, snapshot sends only events after that ID."""
        from app.routers.mcp_activity import _sse_generator

        b = MCPActivityBroadcaster()
        events = []
        for i in range(5):
            e = MCPActivityEvent(
                event_type=MCPEventType.tool_complete, tool_name=f"gap_{i}"
            )
            b.publish(e)
            events.append(e)

        import app.routers.mcp_activity as router_mod

        original = router_mod.mcp_activity
        router_mod.mcp_activity = b
        try:
            chunks = []
            # Reconnect with the 3rd event as the last seen
            gen = _sse_generator(last_event_id=events[2].id)
            async for chunk in gen:
                chunks.append(chunk)
                if "gap_4" in chunk:
                    break

            activity_chunks = [c for c in chunks if "mcp_activity" in c]
            tool_names = []
            for chunk in activity_chunks:
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("tool_name", "").startswith("gap_"):
                            tool_names.append(data["tool_name"])

            # Only events AFTER the given ID should appear
            assert tool_names == ["gap_3", "gap_4"]
        finally:
            router_mod.mcp_activity = original

    @pytest.mark.asyncio
    async def test_last_event_id_unknown_falls_back(self):
        """Unknown Last-Event-ID falls back to recent_history."""
        from app.routers.mcp_activity import _sse_generator

        b = MCPActivityBroadcaster()
        for i in range(3):
            b.publish(
                MCPActivityEvent(
                    event_type=MCPEventType.tool_complete, tool_name=f"fb_{i}"
                )
            )

        import app.routers.mcp_activity as router_mod

        original = router_mod.mcp_activity
        router_mod.mcp_activity = b
        try:
            chunks = []
            gen = _sse_generator(last_event_id="nonexistent-id")
            async for chunk in gen:
                chunks.append(chunk)
                if "fb_2" in chunk:
                    break

            activity_chunks = [c for c in chunks if "mcp_activity" in c]
            tool_names = []
            for chunk in activity_chunks:
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("tool_name", "").startswith("fb_"):
                            tool_names.append(data["tool_name"])

            # Fallback = all recent history
            assert tool_names == ["fb_0", "fb_1", "fb_2"]
        finally:
            router_mod.mcp_activity = original


# ── Router integration tests (non-streaming) ──


class TestRouterEndpoints:
    @pytest.mark.asyncio
    async def test_webhook_publishes_event(self, client):
        """POST to /internal/mcp-event accepts valid payloads."""
        response = await client.post(
            "/internal/mcp-event",
            json={
                "event_type": "tool_complete",
                "tool_name": "optimize",
                "call_id": "test-123",
            },
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_webhook_rejects_unknown_type(self, client):
        """Unknown event types are logged but don't error."""
        response = await client.post(
            "/internal/mcp-event",
            json={"event_type": "unknown_type"},
        )
        # Returns 204 (no content) even for unknown types — silently drops
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_mcp_status_endpoint(self, client):
        """GET /api/mcp/status returns status dict with recent_events."""
        response = await client.get("/api/mcp/status")
        assert response.status_code == 200
        data = response.json()
        assert "subscriber_count" in data
        assert "recent_events" in data
        assert "active_calls" in data
        assert "session_count" in data


# ── Webhook authentication tests ──


class TestWebhookAuth:
    VALID_SECRET = "test-webhook-secret-abc123"

    @pytest.mark.asyncio
    async def test_webhook_rejected_without_secret(self, client, monkeypatch):
        """POST /internal/mcp-event returns 403 without X-Webhook-Secret."""
        from app import config
        monkeypatch.setattr(config, "INTERNAL_WEBHOOK_SECRET", self.VALID_SECRET)
        response = await client.post(
            "/internal/mcp-event",
            json={"event_type": "tool_complete", "tool_name": "test"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_webhook_accepted_with_valid_secret(self, client, monkeypatch):
        """Correct X-Webhook-Secret passes, returns 204."""
        from app import config
        monkeypatch.setattr(config, "INTERNAL_WEBHOOK_SECRET", self.VALID_SECRET)
        response = await client.post(
            "/internal/mcp-event",
            json={"event_type": "tool_complete", "tool_name": "test"},
            headers={"X-Webhook-Secret": self.VALID_SECRET},
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_webhook_rejected_with_wrong_secret(self, client, monkeypatch):
        """Wrong X-Webhook-Secret returns 403."""
        from app import config
        monkeypatch.setattr(config, "INTERNAL_WEBHOOK_SECRET", self.VALID_SECRET)
        response = await client.post(
            "/internal/mcp-event",
            json={"event_type": "tool_complete", "tool_name": "test"},
            headers={"X-Webhook-Secret": "wrong-secret"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_webhook_passes_when_secret_empty(self, client):
        """Dev mode: empty INTERNAL_WEBHOOK_SECRET allows all requests."""
        # conftest sets INTERNAL_WEBHOOK_SECRET="" globally — no header needed
        response = await client.post(
            "/internal/mcp-event",
            json={"event_type": "tool_complete", "tool_name": "test"},
        )
        assert response.status_code == 204
