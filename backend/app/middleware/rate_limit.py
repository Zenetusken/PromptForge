"""In-memory sliding-window rate limiter.

Per-IP rate limiting with configurable requests-per-minute for general
endpoints and a stricter limit for the optimization endpoint.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app import config
from app.middleware import get_client_ip

# Window size in seconds
_WINDOW = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter.

    Limits are read from config at request time so env changes take effect
    without restart.
    """

    def __init__(self, app):
        super().__init__(app)
        # ip -> list of request timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)

    def reset(self) -> None:
        """Clear all tracked requests. Used in testing."""
        self._requests.clear()

    def _cleanup(self, ip: str, now: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - _WINDOW
        timestamps = self._requests[ip]
        # Find first index within window
        idx = 0
        while idx < len(timestamps) and timestamps[idx] < cutoff:
            idx += 1
        if idx > 0:
            self._requests[ip] = timestamps[idx:]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        ip = get_client_ip(request)
        now = time.monotonic()
        self._cleanup(ip, now)

        # Determine limit based on endpoint
        is_optimize = (
            request.method == "POST"
            and request.url.path.rstrip("/") in ("/api/optimize",)
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
