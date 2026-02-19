"""Audit logging middleware for state-changing requests.

Logs POST, PUT, DELETE requests with:
- HTTP method and path
- Response status code
- Client IP address
- Provider name (from X-LLM-Provider header, if present)

Never logs API keys or Authorization tokens.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.middleware import get_client_ip

logger = logging.getLogger("promptforge.audit")

_AUDITED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Log state-changing requests for audit trail."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method not in _AUDITED_METHODS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        provider = request.headers.get("x-llm-provider", "-")
        logger.info(
            "AUDIT %s %s status=%d ip=%s provider=%s duration=%.0fms",
            request.method,
            request.url.path,
            response.status_code,
            get_client_ip(request),
            provider,
            duration_ms,
        )
        return response
