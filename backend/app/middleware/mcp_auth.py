"""MCP server authentication middleware.

Bearer token authentication for the MCP server. When MCP_AUTH_TOKEN is set,
all requests except /health must include `Authorization: Bearer <token>`.
When MCP_AUTH_TOKEN is empty, auth is disabled (development mode).
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """Bearer token authentication for the MCP Starlette app."""

    def __init__(self, app, token: str = ""):
        super().__init__(app)
        self._token = token

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        # Skip auth when token is not configured (development mode)
        if not self._token:
            return await call_next(request)

        # /health is always open for probes
        if request.url.path == "/health":
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Missing or invalid Authorization header"},
                status_code=401,
            )

        provided = auth_header[7:]  # strip "Bearer "
        if not hmac.compare_digest(provided, self._token):
            return JSONResponse(
                {"error": "Invalid authentication token"},
                status_code=401,
            )

        return await call_next(request)
