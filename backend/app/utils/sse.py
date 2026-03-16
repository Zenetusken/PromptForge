"""Shared SSE formatting utility."""
import json


def format_sse(event_type: str, data: dict) -> str:
    payload = json.dumps({"event": event_type, **data})
    return f"data: {payload}\n\n"
