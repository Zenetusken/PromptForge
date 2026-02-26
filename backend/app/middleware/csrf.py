"""Origin-based CSRF protection middleware.

Validates the ``Origin`` header on state-changing requests (POST, PUT, DELETE)
to prevent cross-site request forgery. Requests without an ``Origin`` header
(e.g., curl, server-to-server) are allowed through — this is a defense-in-depth
measure, not the sole security boundary.
"""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app import config

_STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def _allowed_origins() -> set[str]:
    """Build a set of allowed origin strings from the configured FRONTEND_URL."""
    origins = set()
    for url in config.FRONTEND_URL.split(","):
        url = url.strip()
        if url:
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            origins.add(origin)
    # Also allow the backend's own origin for API docs
    origins.add(f"http://localhost:{config.PORT}")
    origins.add(f"http://127.0.0.1:{config.PORT}")
    return origins


class CSRFMiddleware(BaseHTTPMiddleware):
    """Origin-based CSRF protection for state-changing requests."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        # Internal endpoints (MCP webhook) are secured by X-Webhook-Secret
        if request.url.path.startswith("/internal/"):
            return await call_next(request)

        if request.method not in _STATE_CHANGING_METHODS:
            return await call_next(request)

        origin = request.headers.get("origin")
        if not origin:
            # No Origin header — non-browser request (curl, etc.)
            return await call_next(request)

        if origin not in _allowed_origins():
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: origin not allowed"},
            )

        return await call_next(request)
