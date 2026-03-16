"""Real-time SSE event stream endpoint."""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["events"])


class InternalEventRequest(BaseModel):
    event_type: str
    data: dict


@router.post("/events/_publish")
async def publish_event(body: InternalEventRequest):
    """Internal endpoint for cross-process event publishing (used by MCP server)."""
    event_bus.publish(body.event_type, body.data)
    return {"ok": True}


@router.get("/events")
async def event_stream():
    """SSE endpoint -- streams real-time events with periodic keepalive."""
    logger.info("New SSE event stream connection")

    async def generate():
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        event_bus._subscribers.add(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    event_type = event["event"]
                    data = json.dumps(event["data"])
                    yield f"event: {event_type}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # SSE keepalive comment (ignored by EventSource, keeps connection alive)
                    yield ": keepalive\n\n"
        finally:
            event_bus._subscribers.discard(queue)
            logger.info("SSE subscriber disconnected")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
