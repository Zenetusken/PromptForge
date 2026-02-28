"""Tests for kernel event bus and contract registry."""

import asyncio

import pytest
from pydantic import BaseModel

from kernel.bus.contracts import ContractRegistry, EventContract
from kernel.bus.event_bus import EventBus


# ── EventBus ─────────────────────────────────────────────────────────


class TestEventBus:
    """Tests for the EventBus publish/subscribe/request system."""

    def test_subscribe_returns_id(self):
        bus = EventBus()
        sub_id = bus.subscribe("test:event", lambda d, s: None)
        assert isinstance(sub_id, str)
        assert len(sub_id) > 0

    def test_unsubscribe(self):
        bus = EventBus()
        sub_id = bus.subscribe("test:event", lambda d, s: None)
        bus.unsubscribe(sub_id)
        assert len(bus.list_subscriptions()) == 0

    def test_unsubscribe_nonexistent(self):
        bus = EventBus()
        # Should not raise
        bus.unsubscribe("nonexistent-id")

    def test_list_subscriptions(self):
        bus = EventBus()
        bus.subscribe("a:event", lambda d, s: None, app_id="app-a")
        bus.subscribe("b:event", lambda d, s: None, app_id="app-b")
        subs = bus.list_subscriptions()
        assert len(subs) == 2
        app_ids = {s["app_id"] for s in subs}
        assert app_ids == {"app-a", "app-b"}

    @pytest.mark.asyncio
    async def test_publish_fires_handler(self):
        bus = EventBus()
        received = []

        async def handler(data, source_app):
            received.append({"data": data, "source": source_app})

        bus.subscribe("test:event", handler, app_id="listener")
        bus.publish("test:event", {"msg": "hello"}, "sender")

        # Give the async task time to run
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0]["data"] == {"msg": "hello"}
        assert received[0]["source"] == "sender"

    @pytest.mark.asyncio
    async def test_publish_multiple_subscribers(self):
        bus = EventBus()
        results = []

        async def handler1(data, source_app):
            results.append("h1")

        async def handler2(data, source_app):
            results.append("h2")

        bus.subscribe("test:event", handler1)
        bus.subscribe("test:event", handler2)
        bus.publish("test:event", {}, "sender")

        await asyncio.sleep(0.05)
        assert sorted(results) == ["h1", "h2"]

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        bus = EventBus()
        # Should not raise
        bus.publish("nobody:listening", {"data": 1}, "sender")

    @pytest.mark.asyncio
    async def test_publish_handler_error_does_not_propagate(self):
        bus = EventBus()

        async def bad_handler(data, source_app):
            raise RuntimeError("Handler crashed")

        bus.subscribe("test:event", bad_handler)
        bus.publish("test:event", {}, "sender")
        # Should complete without error
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_request_response(self):
        bus = EventBus()

        async def responder(data, source_app):
            return {"echo": data.get("msg"), "from": source_app}

        bus.subscribe("rpc:echo", responder, app_id="echo-service")
        result = await bus.request("rpc:echo", {"msg": "ping"}, "requester")
        assert result == {"echo": "ping", "from": "requester"}

    @pytest.mark.asyncio
    async def test_request_no_handlers_raises(self):
        bus = EventBus()
        with pytest.raises(ValueError, match="No handlers"):
            await bus.request("rpc:missing", {}, "requester")

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        bus = EventBus()

        async def slow_handler(data, source_app):
            await asyncio.sleep(10)
            return {}

        bus.subscribe("rpc:slow", slow_handler)
        with pytest.raises(TimeoutError):
            await bus.request("rpc:slow", {}, "requester", timeout=0.05)

    @pytest.mark.asyncio
    async def test_request_non_dict_result_wrapped(self):
        bus = EventBus()

        async def handler(data, source_app):
            return "plain string"

        bus.subscribe("rpc:wrap", handler)
        result = await bus.request("rpc:wrap", {}, "requester")
        assert result == {"result": "plain string"}


# ── ContractRegistry ─────────────────────────────────────────────────


class ExamplePayload(BaseModel):
    message: str
    count: int = 0


class ExampleResponse(BaseModel):
    status: str


class TestContractRegistry:
    """Tests for typed event contract registration and validation."""

    def test_register_contract(self):
        reg = ContractRegistry()
        contract = EventContract(
            event_type="test:event",
            source_app="test-app",
            payload_schema=ExamplePayload,
        )
        reg.register(contract)
        assert len(reg.get_contracts()) == 1
        assert reg.get_contract("test:event") is contract

    def test_get_contract_missing(self):
        reg = ContractRegistry()
        assert reg.get_contract("missing") is None

    def test_validate_publish_valid(self):
        reg = ContractRegistry()
        reg.register(EventContract(
            event_type="test:event",
            source_app="test-app",
            payload_schema=ExamplePayload,
        ))
        # Should not raise
        reg.validate_publish("test:event", {"message": "hello"})

    def test_validate_publish_invalid_data(self):
        from pydantic import ValidationError

        reg = ContractRegistry()
        reg.register(EventContract(
            event_type="test:event",
            source_app="test-app",
            payload_schema=ExamplePayload,
        ))
        with pytest.raises(ValidationError):
            reg.validate_publish("test:event", {"wrong_field": 123})

    def test_validate_publish_no_contract(self):
        reg = ContractRegistry()
        with pytest.raises(ValueError, match="No contract"):
            reg.validate_publish("missing:event", {"data": 1})

    def test_to_json(self):
        reg = ContractRegistry()
        reg.register(EventContract(
            event_type="test:event",
            source_app="test-app",
            payload_schema=ExamplePayload,
            response_schema=ExampleResponse,
        ))
        result = reg.to_json()
        assert len(result) == 1
        assert result[0]["event_type"] == "test:event"
        assert result[0]["source_app"] == "test-app"
        assert "properties" in result[0]["payload_schema"]
        assert "properties" in result[0]["response_schema"]

    def test_to_json_no_response_schema(self):
        reg = ContractRegistry()
        reg.register(EventContract(
            event_type="test:event",
            source_app="test-app",
            payload_schema=ExamplePayload,
        ))
        result = reg.to_json()
        assert result[0]["response_schema"] is None

    def test_overwrite_warning(self):
        reg = ContractRegistry()
        reg.register(EventContract(
            event_type="test:event", source_app="app-a",
            payload_schema=ExamplePayload,
        ))
        reg.register(EventContract(
            event_type="test:event", source_app="app-b",
            payload_schema=ExamplePayload,
        ))
        # Latest registration wins
        assert reg.get_contract("test:event").source_app == "app-b"


# ── AppBase event hooks ──────────────────────────────────────────────


class TestAppBaseEventHooks:
    """Tests for the default event hook methods on AppBase."""

    def test_default_get_event_contracts(self):
        from kernel.registry.hooks import AppBase

        class DummyApp(AppBase):
            @property
            def app_id(self):
                return "dummy"

        app = DummyApp()
        assert app.get_event_contracts() == []

    def test_default_get_event_handlers(self):
        from kernel.registry.hooks import AppBase

        class DummyApp(AppBase):
            @property
            def app_id(self):
                return "dummy"

        app = DummyApp()
        assert app.get_event_handlers() == {}


# ── SSE Relay ────────────────────────────────────────────────────────


class TestSSERelay:
    """Tests for EventBus SSE relay channel forwarding."""

    @pytest.mark.asyncio
    async def test_publish_forwards_to_sse_relay(self):
        bus = EventBus()
        relayed = []

        async def relay_handler(data, source_app):
            relayed.append({"data": data, "source": source_app})

        bus.subscribe(EventBus.SSE_RELAY_CHANNEL, relay_handler, app_id="sse")
        bus.publish("prompt:optimized", {"id": "abc"}, "promptforge")

        await asyncio.sleep(0.05)

        assert len(relayed) == 1
        assert relayed[0]["data"]["event_type"] == "prompt:optimized"
        assert relayed[0]["data"]["id"] == "abc"
        assert relayed[0]["source"] == "promptforge"

    @pytest.mark.asyncio
    async def test_relay_does_not_recurse(self):
        bus = EventBus()
        relayed = []

        async def relay_handler(data, source_app):
            relayed.append(data)

        bus.subscribe(EventBus.SSE_RELAY_CHANNEL, relay_handler)
        # Publishing to the relay channel itself should NOT trigger relay again
        bus.publish(EventBus.SSE_RELAY_CHANNEL, {"test": True}, "kernel")

        await asyncio.sleep(0.05)

        # Exactly 1: the direct subscriber, no recursive relay
        assert len(relayed) == 1


# ── Bus router endpoints ─────────────────────────────────────────────


class TestBusRouter:
    """Tests for the kernel bus REST API endpoints."""

    @pytest.mark.asyncio
    async def test_list_contracts_empty(self, client):
        resp = await client.get("/api/kernel/bus/contracts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contracts"] == []

    @pytest.mark.asyncio
    async def test_list_subscriptions(self, client):
        resp = await client.get("/api/kernel/bus/subscriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "subscriptions" in data
