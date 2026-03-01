"""Kernel router for event bus introspection, SSE bridge, and publish API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

if TYPE_CHECKING:
    from kernel.bus.contracts import ContractRegistry
    from kernel.bus.event_bus import EventBus

router = APIRouter(prefix="/api/kernel/bus", tags=["kernel-bus"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Replay buffer — stores recent events for Last-Event-ID reconnection
# ---------------------------------------------------------------------------

@dataclass
class ReplayEvent:
    """A stored event for SSE replay."""

    id: int
    event_type: str
    data: dict
    source_app: str
    timestamp: float = field(default_factory=time.time)


class EventReplayBuffer:
    """Ring buffer storing recent bus events for SSE reconnection replay.

    Thread-safe for single event loop async code (deque is GIL-atomic).
    """

    def __init__(self, max_size: int = 200) -> None:
        self._buffer: deque[ReplayEvent] = deque(maxlen=max_size)
        self._counter: int = 0

    def append(self, event_type: str, data: dict, source_app: str) -> int:
        """Store an event and return its sequential ID."""
        self._counter += 1
        entry = ReplayEvent(
            id=self._counter,
            event_type=event_type,
            data=data,
            source_app=source_app,
        )
        self._buffer.append(entry)
        return self._counter

    def replay_after(self, last_id: int) -> list[ReplayEvent]:
        """Return all events with ID > last_id, in order."""
        return [e for e in self._buffer if e.id > last_id]

    def __len__(self) -> int:
        return len(self._buffer)


# Module-level singleton — created on first use.
_replay_buffer: EventReplayBuffer | None = None


def _get_replay_buffer() -> EventReplayBuffer:
    global _replay_buffer
    if _replay_buffer is None:
        _replay_buffer = EventReplayBuffer()
    return _replay_buffer


def reset_replay_buffer() -> None:
    """Reset the replay buffer (for testing)."""
    global _replay_buffer
    _replay_buffer = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_bus(request: Request) -> EventBus:
    """Retrieve the EventBus from the app registry's kernel reference."""
    from kernel.registry.app_registry import get_app_registry
    registry = get_app_registry()
    if not registry.kernel or not registry.kernel.services.has("bus"):
        raise HTTPException(status_code=503, detail="Event bus not available")
    return registry.kernel.services.get("bus")


def _get_contracts(request: Request) -> ContractRegistry:
    """Retrieve the ContractRegistry from the kernel services."""
    from kernel.registry.app_registry import get_app_registry
    registry = get_app_registry()
    if not registry.kernel or not registry.kernel.services.has("contracts"):
        raise HTTPException(status_code=503, detail="Contract registry not available")
    return registry.kernel.services.get("contracts")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class PublishRequest(BaseModel):
    event_type: str
    data: dict = {}
    source_app: str = "frontend"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/contracts")
async def list_contracts(request: Request):
    """List all registered event contracts."""
    contracts = _get_contracts(request)
    return {"contracts": contracts.to_json()}


@router.get("/subscriptions")
async def list_subscriptions(request: Request):
    """List all active event subscriptions."""
    bus = _get_bus(request)
    return {"subscriptions": bus.list_subscriptions()}


@router.post("/publish", status_code=202)
async def publish_event(body: PublishRequest, request: Request):
    """Publish an event onto the kernel bus from the frontend.

    Validates the payload against the ContractRegistry if a contract
    exists. Returns 202 Accepted on success.
    """
    bus = _get_bus(request)
    contracts = _get_contracts(request)

    # Validate against contract if one is registered
    contract = contracts.get_contract(body.event_type)
    if contract:
        try:
            contracts.validate_publish(body.event_type, body.data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    bus.publish(body.event_type, body.data, body.source_app)
    return {"status": "accepted", "event_type": body.event_type}


@router.get("/events")
async def stream_events(request: Request):
    """SSE endpoint streaming backend bus events to the frontend.

    Supports ``Last-Event-ID`` header for reconnection replay.
    Each event frame includes an ``id:`` field for the client to track.
    """
    bus = _get_bus(request)
    replay = _get_replay_buffer()
    queue: asyncio.Queue = asyncio.Queue()

    async def _relay(data: dict, source_app: str) -> None:
        await queue.put({"data": data, "source_app": source_app})

    # Subscribe to the SSE relay channel — publish() forwards all events here.
    from kernel.bus.event_bus import EventBus as _EB
    sub_id = bus.subscribe(_EB.SSE_RELAY_CHANNEL, _relay, app_id="kernel-sse")

    # Check for Last-Event-ID to replay missed events
    last_event_id_str = request.headers.get("Last-Event-ID", request.headers.get("last-event-id"))
    last_event_id = 0
    if last_event_id_str:
        try:
            last_event_id = int(last_event_id_str)
        except (ValueError, TypeError):
            pass

    async def event_generator():
        try:
            # Replay missed events first
            if last_event_id > 0:
                for entry in replay.replay_after(last_event_id):
                    payload = {
                        "event_type": entry.event_type,
                        **entry.data,
                        "source_app": entry.source_app,
                    }
                    yield f"id: {entry.id}\nevent: kernel_event\ndata: {json.dumps(payload)}\n\n"

            # Live stream
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Store in replay buffer and get sequential ID
                    event_data = event.get("data", {})
                    event_type = event_data.get("event_type", "unknown")
                    source_app = event.get("source_app", "unknown")
                    event_id = replay.append(event_type, event_data, source_app)

                    payload = {**event_data, "source_app": source_app}
                    yield f"id: {event_id}\nevent: kernel_event\ndata: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(sub_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
