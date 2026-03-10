"""Tests for the RedisService.

Run: cd backend && source .venv/bin/activate && pytest tests/test_redis_service.py -v
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

from app.services.redis_service import _RECONNECT_COOLDOWN, RedisService

# ── Test: graceful degradation on connect failure ─────────────────────────


async def test_graceful_degradation_on_connect_failure():
    """RedisService.connect() should return False and not crash when Redis is down."""
    svc = RedisService(host="nonexistent-host", port=9999, db=0, password="")

    # Mock the redis.asyncio module to simulate connection failure
    with patch("app.services.redis_service.aioredis") as mock_aioredis:
        mock_pool = AsyncMock()
        mock_aioredis.ConnectionPool.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_aioredis.Redis.return_value = mock_client

        result = await svc.connect()

    assert result is False
    assert svc.is_available is False


# ── Test: health check when disconnected ──────────────────────────────────


async def test_health_check_when_disconnected():
    """health_check should return False when Redis is not connected and unavailable."""
    svc = RedisService(host="nonexistent-host", port=9999, db=0, password="")
    # Never connected — _available is False, _client is None

    # Mock connect() to simulate Redis being unreachable
    with patch("app.services.redis_service.aioredis") as mock_aioredis:
        mock_pool = AsyncMock()
        mock_aioredis.ConnectionPool.return_value = mock_pool
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_aioredis.Redis.return_value = mock_client

        result = await svc.health_check()

    assert result is False
    assert svc.is_available is False


# ── Test: is_available property ───────────────────────────────────────────


def test_is_available_false_by_default():
    """is_available should be False before connect() is called."""
    svc = RedisService()
    assert svc.is_available is False


def test_client_returns_none_when_unavailable():
    """client property should return None when Redis is unavailable."""
    svc = RedisService()
    assert svc.client is None


def test_is_ready_false_when_unavailable():
    """is_ready should be False when Redis is not connected."""
    svc = RedisService()
    assert svc.is_ready is False


def test_is_ready_true_when_connected():
    """is_ready should be True when _available and _client are set."""
    svc = RedisService()
    svc._available = True
    svc._client = AsyncMock()  # non-None sentinel
    assert svc.is_ready is True


def test_is_ready_false_when_available_but_no_client():
    """is_ready should be False when _available=True but _client=None."""
    svc = RedisService()
    svc._available = True
    svc._client = None
    assert svc.is_ready is False


# ── Test: close is safe when not connected ────────────────────────────────


async def test_close_safe_when_not_connected():
    """close() should not raise when called without a prior connect()."""
    svc = RedisService()
    # Should not raise
    await svc.close()
    assert svc.is_available is False


# ── Test: reconnection on health check ────────────────────────────────


async def test_health_check_reconnects_after_cooldown():
    """health_check should attempt reconnection after the cooldown elapses."""
    svc = RedisService()
    # Simulate: was connected, then failed → _available=False but _client exists
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    svc._client = mock_client
    svc._available = False
    # Backdate the last attempt so cooldown has elapsed
    svc._last_reconnect_attempt = time.time() - _RECONNECT_COOLDOWN - 1

    result = await svc.health_check()

    assert result is True
    assert svc.is_available is True
    mock_client.ping.assert_awaited_once()


async def test_health_check_respects_cooldown():
    """health_check should NOT attempt reconnection within the cooldown window."""
    svc = RedisService()
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    svc._client = mock_client
    svc._available = False
    # Set last attempt to now — within cooldown
    svc._last_reconnect_attempt = time.time()

    result = await svc.health_check()

    assert result is False
    assert svc.is_available is False
    mock_client.ping.assert_not_awaited()


async def test_health_check_full_reconnect_when_client_none():
    """health_check should call connect() when _client was torn down."""
    svc = RedisService()
    svc._available = False
    svc._client = None
    svc._last_reconnect_attempt = time.time() - _RECONNECT_COOLDOWN - 1

    with patch("app.services.redis_service.aioredis") as mock_aioredis:
        mock_pool = AsyncMock()
        mock_aioredis.ConnectionPool.return_value = mock_pool
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_aioredis.Redis.return_value = mock_client

        result = await svc.health_check()

    assert result is True
    assert svc.is_available is True


async def test_health_check_marks_unavailable_on_ping_failure():
    """health_check should set _available=False when a connected client fails PING."""
    svc = RedisService()
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(side_effect=ConnectionError("lost"))
    svc._client = mock_client
    svc._available = True

    result = await svc.health_check()

    assert result is False
    assert svc.is_available is False
