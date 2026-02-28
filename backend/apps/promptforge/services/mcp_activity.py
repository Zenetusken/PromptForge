"""MCP Activity Broadcaster — in-memory event fan-out for MCP tool call tracking.

Bridges MCP server tool invocations into the PromptForge frontend via SSE.
The MCP server POSTs events to /internal/mcp-event, and this broadcaster
fans them out to all connected SSE clients on /api/mcp/events.

Events are ephemeral (no DB persistence) — fresh on each page load with
a snapshot of recent history on SSE connect.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

logger = logging.getLogger(__name__)


class MCPEventType(StrEnum):
    tool_start = "tool_start"
    tool_progress = "tool_progress"
    tool_complete = "tool_complete"
    tool_error = "tool_error"
    session_connect = "session_connect"
    session_disconnect = "session_disconnect"


@dataclass
class MCPActivityEvent:
    event_type: MCPEventType
    tool_name: str | None = None
    call_id: str | None = None
    client_id: str | None = None
    progress: float | None = None
    message: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    result_summary: dict | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_sse(self) -> str:
        """Format as an SSE data line (JSON payload)."""
        import json

        data = {
            "id": self.id,
            "event_type": self.event_type,
            "tool_name": self.tool_name,
            "call_id": self.call_id,
            "client_id": self.client_id,
            "timestamp": self.timestamp,
            "progress": self.progress,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "result_summary": self.result_summary,
        }
        # Strip None values for compact payloads
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data)


_MAX_HISTORY = 100
_MAX_QUEUE_SIZE = 256


class MCPActivityBroadcaster:
    """Module-level singleton that fans out MCP events to SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[MCPActivityEvent]] = set()
        self._history: list[MCPActivityEvent] = []
        self._active_calls: dict[str, MCPActivityEvent] = {}
        self._session_count: int = 0

    def publish(self, event: MCPActivityEvent) -> None:
        """Record event and fan out to all subscribers."""
        # Update history
        self._history.append(event)
        if len(self._history) > _MAX_HISTORY:
            self._history = self._history[-_MAX_HISTORY:]

        # Update active calls / session tracking
        if event.event_type == MCPEventType.tool_start and event.call_id:
            self._active_calls[event.call_id] = event
        elif event.event_type == MCPEventType.tool_progress and event.call_id:
            if event.call_id in self._active_calls:
                self._active_calls[event.call_id] = event
        elif event.event_type in (MCPEventType.tool_complete, MCPEventType.tool_error):
            if event.call_id:
                self._active_calls.pop(event.call_id, None)
        elif event.event_type == MCPEventType.session_connect:
            self._session_count += 1
        elif event.event_type == MCPEventType.session_disconnect:
            self._session_count = max(0, self._session_count - 1)

        # Fan out to all subscriber queues
        stale: list[asyncio.Queue] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Slow client — evict
                stale.append(queue)

        for queue in stale:
            self._subscribers.discard(queue)
            logger.warning("Evicted slow MCP activity SSE subscriber")

    def subscribe(self) -> asyncio.Queue[MCPActivityEvent]:
        """Create a new subscriber queue. Caller must call unsubscribe() on cleanup."""
        queue: asyncio.Queue[MCPActivityEvent] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[MCPActivityEvent]) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(queue)

    @property
    def recent_history(self) -> list[MCPActivityEvent]:
        """Last 20 events for SSE connect snapshot."""
        return self._history[-20:]

    def get_history_after(self, event_id: str) -> list[MCPActivityEvent]:
        """Return events published after the given event ID.

        Used for Last-Event-ID SSE reconnection. If the ID is not found
        (aged out of the 100-event history buffer), falls back to
        recent_history (same as a fresh connect).
        """
        for i, event in enumerate(self._history):
            if event.id == event_id:
                return self._history[i + 1 :]
        return self.recent_history

    def get_status(self) -> dict:
        """Current status for REST endpoint and SSE snapshot."""
        return {
            "subscriber_count": len(self._subscribers),
            "active_calls": [
                {
                    "call_id": e.call_id,
                    "tool_name": e.tool_name,
                    "client_id": e.client_id,
                    "timestamp": e.timestamp,
                    "progress": e.progress,
                    "message": e.message,
                }
                for e in self._active_calls.values()
            ],
            "session_count": self._session_count,
            "total_events": len(self._history),
        }


# Module-level singleton
mcp_activity = MCPActivityBroadcaster()
