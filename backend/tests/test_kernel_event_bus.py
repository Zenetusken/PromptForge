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


# ── Contract Validation in EventBus.publish ──────────────────────────


class TestContractValidationInPublish:
    """Tests for contract validation during publish()."""

    @pytest.mark.asyncio
    async def test_valid_payload_dispatches(self):
        from kernel.bus.contracts import ContractRegistry
        reg = ContractRegistry()
        reg.register(EventContract(
            event_type="test:valid",
            source_app="test-app",
            payload_schema=ExamplePayload,
        ))
        bus = EventBus(contract_registry=reg)
        received = []

        async def handler(data, source_app):
            received.append(data)

        bus.subscribe("test:valid", handler)
        bus.publish("test:valid", {"message": "hello", "count": 1}, "test-app")

        await asyncio.sleep(0.05)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_invalid_payload_blocked(self):
        from kernel.bus.contracts import ContractRegistry
        reg = ContractRegistry()
        reg.register(EventContract(
            event_type="test:strict",
            source_app="test-app",
            payload_schema=ExamplePayload,
        ))
        bus = EventBus(contract_registry=reg)
        received = []

        async def handler(data, source_app):
            received.append(data)

        bus.subscribe("test:strict", handler)
        # Missing required "message" field
        bus.publish("test:strict", {"wrong": "data"}, "test-app")

        await asyncio.sleep(0.05)
        assert len(received) == 0  # Handler never called

    @pytest.mark.asyncio
    async def test_no_contract_still_publishes(self):
        from kernel.bus.contracts import ContractRegistry
        reg = ContractRegistry()
        bus = EventBus(contract_registry=reg)
        received = []

        async def handler(data, source_app):
            received.append(data)

        bus.subscribe("unregistered:event", handler)
        bus.publish("unregistered:event", {"anything": True}, "test-app")

        await asyncio.sleep(0.05)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_no_registry_still_publishes(self):
        bus = EventBus()  # No contract_registry
        received = []

        async def handler(data, source_app):
            received.append(data)

        bus.subscribe("any:event", handler)
        bus.publish("any:event", {"data": 1}, "test-app")

        await asyncio.sleep(0.05)
        assert len(received) == 1


# ── PromptForge Contracts ────────────────────────────────────────────


class TestPromptForgeContracts:
    """Tests that PromptForge event contracts are valid."""

    def test_contracts_are_valid(self):
        from apps.promptforge.events import PROMPTFORGE_CONTRACTS
        assert len(PROMPTFORGE_CONTRACTS) == 4

        types = {c.event_type for c in PROMPTFORGE_CONTRACTS}
        assert "promptforge:optimization.started" in types
        assert "promptforge:optimization.completed" in types
        assert "promptforge:prompt.created" in types
        assert "promptforge:prompt.updated" in types

    def test_contracts_validate_payloads(self):
        from apps.promptforge.events import PROMPTFORGE_CONTRACTS
        from kernel.bus.contracts import ContractRegistry

        reg = ContractRegistry()
        for c in PROMPTFORGE_CONTRACTS:
            reg.register(c)

        # Valid payload
        reg.validate_publish("promptforge:optimization.started", {
            "optimization_id": "abc-123",
            "raw_prompt": "test prompt",
        })

        # Invalid payload
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            reg.validate_publish("promptforge:optimization.started", {
                "wrong_field": True,
            })


class TestTextForgeContracts:
    """Tests that TextForge event contracts are valid."""

    def test_contracts_are_valid(self):
        from apps.textforge.events import TEXTFORGE_CONTRACTS
        assert len(TEXTFORGE_CONTRACTS) == 2
        event_types = [c.event_type for c in TEXTFORGE_CONTRACTS]
        assert "textforge:transform.completed" in event_types
        assert "textforge:auto-simplify.completed" in event_types


# ── Cross-App Handlers ───────────────────────────────────────────────


class TestCrossAppHandlers:
    """Tests for cross-app event handler registration."""

    def test_textforge_subscribes_to_promptforge_events(self):
        from apps.textforge.app import TextForgeApp
        app = TextForgeApp()
        handlers = app.get_event_handlers()
        assert "promptforge:optimization.completed" in handlers

    def test_promptforge_publishes_contracts(self):
        from apps.promptforge.app import PromptForgeApp
        app = PromptForgeApp()
        contracts = app.get_event_contracts()
        assert len(contracts) == 4

    @pytest.mark.asyncio
    async def test_cross_app_event_delivery(self):
        from kernel.bus.contracts import ContractRegistry
        from apps.promptforge.events import PROMPTFORGE_CONTRACTS

        reg = ContractRegistry()
        for c in PROMPTFORGE_CONTRACTS:
            reg.register(c)

        bus = EventBus(contract_registry=reg)
        received = []

        async def handler(data, source_app):
            received.append({"data": data, "source": source_app})

        bus.subscribe("promptforge:optimization.completed", handler, app_id="textforge")
        bus.publish("promptforge:optimization.completed", {
            "optimization_id": "test-123",
            "overall_score": 8.5,
            "strategy": "chain-of-thought",
        }, "promptforge")

        await asyncio.sleep(0.05)
        assert len(received) == 1
        assert received[0]["data"]["optimization_id"] == "test-123"
        assert received[0]["source"] == "promptforge"
