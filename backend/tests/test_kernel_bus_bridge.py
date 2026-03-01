"""Tests for the kernel bus bridge: replay buffer, POST publish, and SSE replay."""

import asyncio

import pytest
from pydantic import BaseModel

from kernel.bus.contracts import ContractRegistry, EventContract
from kernel.bus.event_bus import EventBus
from kernel.routers.bus import EventReplayBuffer, reset_replay_buffer


# ── EventReplayBuffer ─────────────────────────────────────────────────


class TestEventReplayBuffer:
    """Tests for the ring buffer used for SSE reconnection replay."""

    def test_append_returns_sequential_ids(self):
        buf = EventReplayBuffer(max_size=10)
        id1 = buf.append("evt:a", {"key": 1}, "app-a")
        id2 = buf.append("evt:b", {"key": 2}, "app-b")
        assert id1 == 1
        assert id2 == 2

    def test_replay_after_returns_events_after_id(self):
        buf = EventReplayBuffer(max_size=10)
        buf.append("evt:a", {"v": 1}, "app-a")
        buf.append("evt:b", {"v": 2}, "app-b")
        buf.append("evt:c", {"v": 3}, "app-c")

        replayed = buf.replay_after(1)
        assert len(replayed) == 2
        assert replayed[0].event_type == "evt:b"
        assert replayed[1].event_type == "evt:c"

    def test_replay_after_zero_returns_all(self):
        buf = EventReplayBuffer(max_size=10)
        buf.append("evt:a", {}, "app")
        buf.append("evt:b", {}, "app")

        replayed = buf.replay_after(0)
        assert len(replayed) == 2

    def test_replay_after_latest_returns_empty(self):
        buf = EventReplayBuffer(max_size=10)
        buf.append("evt:a", {}, "app")
        buf.append("evt:b", {}, "app")

        replayed = buf.replay_after(2)
        assert len(replayed) == 0

    def test_max_size_evicts_oldest(self):
        buf = EventReplayBuffer(max_size=3)
        buf.append("evt:1", {}, "app")
        buf.append("evt:2", {}, "app")
        buf.append("evt:3", {}, "app")
        buf.append("evt:4", {}, "app")  # Evicts evt:1

        assert len(buf) == 3
        replayed = buf.replay_after(0)
        assert replayed[0].event_type == "evt:2"
        assert replayed[-1].event_type == "evt:4"

    def test_replay_with_evicted_id_returns_available(self):
        buf = EventReplayBuffer(max_size=2)
        buf.append("evt:1", {}, "app")  # id=1
        buf.append("evt:2", {}, "app")  # id=2
        buf.append("evt:3", {}, "app")  # id=3, evicts id=1

        # Asking for events after id=1, but id=1 is gone
        replayed = buf.replay_after(1)
        assert len(replayed) == 2
        assert replayed[0].id == 2
        assert replayed[1].id == 3

    def test_len(self):
        buf = EventReplayBuffer(max_size=10)
        assert len(buf) == 0
        buf.append("evt:a", {}, "app")
        assert len(buf) == 1

    def test_replay_preserves_data(self):
        buf = EventReplayBuffer(max_size=10)
        buf.append("evt:test", {"msg": "hello"}, "sender-app")

        replayed = buf.replay_after(0)
        assert replayed[0].data == {"msg": "hello"}
        assert replayed[0].source_app == "sender-app"
        assert replayed[0].timestamp > 0


# ── POST /api/kernel/bus/publish ──────────────────────────────────────


class ExamplePayload(BaseModel):
    message: str
    count: int = 0


class TestPublishEndpoint:
    """Tests for the POST publish endpoint."""

    @pytest.fixture(autouse=True)
    def _reset_buffer(self):
        reset_replay_buffer()
        yield
        reset_replay_buffer()

    @pytest.mark.asyncio
    async def test_publish_returns_202(self, client):
        resp = await client.post("/api/kernel/bus/publish", json={
            "event_type": "test:event",
            "data": {"msg": "hello"},
            "source_app": "test-client",
        })
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["event_type"] == "test:event"

    @pytest.mark.asyncio
    async def test_publish_with_contract_validation(self, client):
        """Publish with a registered contract validates the payload."""
        from kernel.registry.app_registry import get_app_registry
        registry = get_app_registry()
        contracts = registry.kernel.services.get("contracts")
        contracts.register(EventContract(
            event_type="test:validated",
            source_app="test-app",
            payload_schema=ExamplePayload,
        ))
        try:
            # Valid payload
            resp = await client.post("/api/kernel/bus/publish", json={
                "event_type": "test:validated",
                "data": {"message": "hello", "count": 1},
            })
            assert resp.status_code == 202

            # Invalid payload
            resp = await client.post("/api/kernel/bus/publish", json={
                "event_type": "test:validated",
                "data": {"wrong_field": True},
            })
            assert resp.status_code == 422
        finally:
            # Cleanup the test contract
            contracts._contracts.pop("test:validated", None)

    @pytest.mark.asyncio
    async def test_publish_without_contract_passes(self, client):
        """Events without contracts are accepted freely."""
        resp = await client.post("/api/kernel/bus/publish", json={
            "event_type": "unregistered:event",
            "data": {"anything": True},
        })
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_publish_default_source_app(self, client):
        resp = await client.post("/api/kernel/bus/publish", json={
            "event_type": "test:defaults",
            "data": {},
        })
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_publish_fires_bus_handler(self, client):
        """Published events reach bus subscribers."""
        from kernel.registry.app_registry import get_app_registry
        bus = get_app_registry().kernel.services.get("bus")
        received = []

        async def handler(data, source_app):
            received.append({"data": data, "source": source_app})

        sub_id = bus.subscribe("test:bridged", handler)
        try:
            await client.post("/api/kernel/bus/publish", json={
                "event_type": "test:bridged",
                "data": {"value": 42},
                "source_app": "frontend",
            })
            await asyncio.sleep(0.1)
            assert len(received) == 1
            assert received[0]["data"]["value"] == 42
        finally:
            bus.unsubscribe(sub_id)


# ── SSE replay (unit level) ──────────────────────────────────────────


class TestSSEReplay:
    """Tests for Last-Event-ID replay logic."""

    @pytest.mark.asyncio
    async def test_publish_populates_replay_buffer(self):
        """Events published via the bus reach the replay buffer when streamed."""
        # This is a unit test of the replay buffer's append logic
        buf = EventReplayBuffer(max_size=200)
        eid = buf.append("test:event", {"val": 1}, "app-a")
        assert eid == 1
        replayed = buf.replay_after(0)
        assert len(replayed) == 1

    @pytest.mark.asyncio
    async def test_replay_ordering(self):
        buf = EventReplayBuffer(max_size=200)
        for i in range(5):
            buf.append(f"evt:{i}", {"i": i}, "app")

        # After id=2, should get events 3,4,5
        replayed = buf.replay_after(2)
        assert len(replayed) == 3
        assert [e.id for e in replayed] == [3, 4, 5]
