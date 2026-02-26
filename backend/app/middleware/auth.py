"""Bearer token authentication middleware.

When ``AUTH_TOKEN`` is set, all requests (except exempt paths) must include
an ``Authorization: Bearer <token>`` header matching the configured value.
When ``AUTH_TOKEN`` is empty or unset, the middleware is a no-op for
backward compatibility.
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app import config

# Paths that never require authentication
_EXEMPT_PREFIXES = (
    "/api/health",
    "/api/github/callback",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/internal/",
)


def _is_exempt(path: str) -> bool:
    """Return True if the path is exempt from authentication."""
    if path == "/":
        return True
    return any(path.startswith(p) for p in _EXEMPT_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional bearer token authentication.

    Disabled when ``AUTH_TOKEN`` config is empty.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        token = config.AUTH_TOKEN
        if not token:
            return await call_next(request)

        if _is_exempt(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        provided = auth_header[7:]  # Strip "Bearer "
        if not hmac.compare_digest(provided, token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication token"},
            )

        return await call_next(request)
