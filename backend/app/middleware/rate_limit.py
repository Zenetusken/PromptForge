"""In-memory sliding-window rate limiter.

Per-IP rate limiting with configurable requests-per-minute for general
endpoints and a stricter limit for the optimization endpoint.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app import config
from app.middleware import get_client_ip

# Window size in seconds
_WINDOW = 60.0

# Stale IP entries are pruned every 60 seconds
_PRUNE_INTERVAL = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter.

    Limits are read from config at request time so env changes take effect
    without restart.
    """

    def __init__(self, app):
        super().__init__(app)
        # ip -> deque of request timestamps (O(1) popleft vs list splice)
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._last_prune = 0.0

    def reset(self) -> None:
        """Clear all tracked requests. Used in testing."""
        self._requests.clear()
        self._last_prune = 0.0

    def _cleanup(self, ip: str, now: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - _WINDOW
        timestamps = self._requests[ip]
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    def _prune_stale_ips(self, now: float) -> None:
        """Periodically remove empty IP entries to prevent unbounded memory growth."""
        if now - self._last_prune < _PRUNE_INTERVAL:
            return
        self._last_prune = now
        stale = [ip for ip, ts in self._requests.items() if not ts]
        for ip in stale:
            del self._requests[ip]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        # Internal endpoints (MCP webhook) are exempt from rate limiting
        if request.url.path.startswith("/internal/"):
            return await call_next(request)

        ip = get_client_ip(request)
        now = time.monotonic()
        self._cleanup(ip, now)
        self._prune_stale_ips(now)

        # Determine limit based on endpoint
        is_optimize = (
            request.method == "POST"
            and request.url.path.rstrip("/") in ("/api/apps/promptforge/optimize",)
        )
        limit = config.RATE_LIMIT_OPTIMIZE_RPM if is_optimize else config.RATE_LIMIT_RPM

        if len(self._requests[ip]) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": "60"},
            )

        self._requests[ip].append(now)
        return await call_next(request)
