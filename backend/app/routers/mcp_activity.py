"""MCP Activity router — webhook receiver, SSE stream, and status endpoint.

POST /internal/mcp-event  — Webhook from MCP server (internal, no CORS/auth)
GET  /api/mcp/events       — SSE stream for frontend (snapshot + live events)
GET  /api/mcp/status        — REST polling fallback
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app import config
from app.services.mcp_activity import MCPActivityEvent, MCPEventType, mcp_activity

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Webhook receiver (from MCP server) ──


class MCPEventPayload(BaseModel):
    """Payload expected from the MCP server webhook."""

    event_type: str
    tool_name: str | None = None
    call_id: str | None = None
    client_id: str | None = None
    progress: float | None = None
    message: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    result_summary: dict | None = None


@router.post("/internal/mcp-event", status_code=204)
async def receive_mcp_event(payload: MCPEventPayload, request: Request):
    """Receive an MCP tool event from the MCP server process.

    Internal endpoint — not exposed via CORS, exempt from auth.
    Validated via X-Webhook-Secret header when INTERNAL_WEBHOOK_SECRET is set.
    """
    expected = config.INTERNAL_WEBHOOK_SECRET
    if expected:
        provided = request.headers.get("X-Webhook-Secret", "")
        if not hmac.compare_digest(provided, expected):
            return JSONResponse(
                {"error": "Invalid webhook secret"}, status_code=403,
            )

    try:
        event_type = MCPEventType(payload.event_type)
    except ValueError:
        logger.warning("Unknown MCP event type: %s", payload.event_type)
        return

    event = MCPActivityEvent(
        event_type=event_type,
        tool_name=payload.tool_name,
        call_id=payload.call_id,
        client_id=payload.client_id,
        progress=payload.progress,
        message=payload.message,
        duration_ms=payload.duration_ms,
        error=payload.error,
        result_summary=payload.result_summary,
    )
    mcp_activity.publish(event)


# ── SSE stream for frontend ──


async def _sse_generator(
    last_event_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE events: snapshot on connect, then live events.

    When *last_event_id* is provided (SSE reconnection), the snapshot phase
    replays only events published after that ID.  If the ID has aged out of
    the history buffer, falls back to ``recent_history`` (same as a fresh
    connect).
    """
    queue = mcp_activity.subscribe()
    try:
        # 1. Send status snapshot
        status = mcp_activity.get_status()
        yield f"event: mcp_status\ndata: {json.dumps(status)}\n\n"

        # 2. Send history — gap-fill on reconnect, or recent batch on fresh connect
        if last_event_id:
            history = mcp_activity.get_history_after(last_event_id)
        else:
            history = mcp_activity.recent_history
        for event in history:
            yield f"id: {event.id}\nevent: mcp_activity\ndata: {event.to_sse()}\n\n"

        # 3. Stream live events
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"id: {event.id}\nevent: mcp_activity\ndata: {event.to_sse()}\n\n"
            except TimeoutError:
                # Send keepalive comment to prevent connection timeout
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        mcp_activity.unsubscribe(queue)


@router.get("/api/mcp/events")
async def mcp_events_stream(request: Request):
    """SSE stream of MCP activity events for the frontend."""
    last_event_id = request.headers.get("Last-Event-ID")
    return StreamingResponse(
        _sse_generator(last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── REST status endpoint (polling fallback) ──


@router.get("/api/mcp/status")
async def mcp_status():
    """Current MCP activity status and recent events."""
    status = mcp_activity.get_status()
    status["recent_events"] = [
        json.loads(e.to_sse()) for e in mcp_activity.recent_history
    ]
    return status
