"""Kernel router for event bus introspection and SSE bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

if TYPE_CHECKING:
    from kernel.bus.contracts import ContractRegistry
    from kernel.bus.event_bus import EventBus

router = APIRouter(prefix="/api/kernel/bus", tags=["kernel-bus"])

logger = logging.getLogger(__name__)


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


@router.get("/events")
async def stream_events(request: Request):
    """SSE endpoint streaming backend bus events to the frontend.

    Bridges the backend EventBus into an SSE stream. The frontend
    can consume this to receive real-time cross-app events.
    """
    bus = _get_bus(request)
    queue: asyncio.Queue = asyncio.Queue()

    async def _relay(data: dict, source_app: str) -> None:
        await queue.put({"data": data, "source_app": source_app})

    # Subscribe to the SSE relay channel — publish() forwards all events here.
    from kernel.bus.event_bus import EventBus as _EB
    sub_id = bus.subscribe(_EB.SSE_RELAY_CHANNEL, _relay, app_id="kernel-sse")

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
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
