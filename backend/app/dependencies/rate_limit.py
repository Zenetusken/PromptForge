"""FastAPI rate limiting dependency backed by the `limits` library.

Replaces slowapi with a direct `limits` integration. Supports Redis
(async MovingWindowRateLimiter) with automatic fallback to in-memory
(sync MemoryStorage) when Redis is unavailable.

Usage in routers::

    from app.dependencies.rate_limit import RateLimit

    @router.get("/api/example")
    async def example(
        request: Request,
        _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY)),
    ):
        ...
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Callable

from app.config import settings as _settings
from fastapi import HTTPException, Request
from limits import parse as limits_parse
from limits.storage import MemoryStorage

if TYPE_CHECKING:
    from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)

# Trusted proxy IPs — only trust X-Forwarded-For from these addresses
_trusted_proxy_set: set[str] = {
    ip.strip() for ip in _settings.TRUSTED_PROXIES.split(",") if ip.strip()
} if _settings.TRUSTED_PROXIES else {"127.0.0.1", "::1"}

# Module-level state — initialized once via init_rate_limiter()
_storage = None
_limiter = None
_is_async = False


@lru_cache(maxsize=32)
def _parse_rate(rate_string: str):
    """Parse and cache a rate limit string (e.g., '60/minute')."""
    return limits_parse(rate_string)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, using X-Forwarded-For only from trusted proxies.

    If the direct connection comes from a trusted proxy (configured via
    TRUSTED_PROXIES), the first IP in X-Forwarded-For is used. Otherwise,
    the direct client IP is returned to prevent rate-limit bypass via
    header spoofing.
    """
    direct_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded and direct_ip in _trusted_proxy_set:
        return forwarded.split(",")[0].strip()
    return direct_ip


async def init_rate_limiter(redis_service: "RedisService | None" = None) -> None:
    """Select Redis or in-memory storage based on availability.

    Called once from the FastAPI lifespan handler.
    """
    global _storage, _limiter, _is_async

    if redis_service and redis_service.is_available:
        try:
            from limits.aio.storage import RedisStorage
            from limits.aio.strategies import MovingWindowRateLimiter

            _storage = RedisStorage(redis_service.uri)
            _limiter = MovingWindowRateLimiter(_storage)
            _is_async = True
            logger.info("Rate limiter initialized with Redis storage (async moving window)")
            return
        except Exception as e:
            logger.warning("Failed to initialize Redis rate limiter: %s — falling back to memory", e)

    # Fallback: in-memory storage (sync, but safe in async context)
    from limits.strategies import MovingWindowRateLimiter as SyncMovingWindow

    _storage = MemoryStorage()
    _limiter = SyncMovingWindow(_storage)
    _is_async = False
    logger.info("Rate limiter initialized with in-memory storage (sync moving window)")


class RateLimit:
    """FastAPI dependency for rate limiting via the ``limits`` library.

    Usage::

        _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY))
    """

    def __init__(self, rate_string_fn: Callable[[], str]) -> None:
        self._rate_string_fn = rate_string_fn

    async def __call__(self, request: Request) -> None:
        if _limiter is None:
            # Rate limiter not initialized — allow request (startup race)
            return

        rate_string = self._rate_string_fn()
        parsed = _parse_rate(rate_string)
        client_ip = _get_client_ip(request)
        # Build a key that includes the endpoint path for isolation
        key = f"{request.url.path}:{client_ip}"

        if _is_async:
            allowed = await _limiter.hit(parsed, key)
        else:
            allowed = _limiter.hit(parsed, key)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Limit: {rate_string}",
                },
            )
