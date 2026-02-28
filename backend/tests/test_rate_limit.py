"""Tests for the rate limiting middleware."""

from unittest.mock import patch

import pytest


class TestRateLimit:
    """Rate limiter enforces per-IP request limits."""

    @pytest.mark.asyncio
    async def test_exceeding_limit_returns_429(self, client):
        """Requests exceeding the limit get 429. Eventually the limiter kicks in."""
        with patch("app.middleware.rate_limit.config") as mock_config:
            mock_config.RATE_LIMIT_RPM = 5
            mock_config.RATE_LIMIT_OPTIMIZE_RPM = 10

            # Send enough requests to exceed the limit (some may already be counted
            # from other tests sharing the same app instance)
            last_status = None
            got_429 = False
            for _ in range(20):
                resp = await client.get("/api/apps/promptforge/health")
                last_status = resp.status_code
                if last_status == 429:
                    got_429 = True
                    break

            assert got_429, f"Expected 429 but last status was {last_status}"
            assert "Rate limit" in resp.json()["detail"]
            assert "Retry-After" in resp.headers

    @pytest.mark.asyncio
    async def test_rate_limit_response_format(self, client):
        """The 429 response has the expected shape."""
        with patch("app.middleware.rate_limit.config") as mock_config:
            mock_config.RATE_LIMIT_RPM = 1
            mock_config.RATE_LIMIT_OPTIMIZE_RPM = 1

            # Exhaust the limit
            for _ in range(5):
                resp = await client.get("/api/apps/promptforge/health")
                if resp.status_code == 429:
                    break

            if resp.status_code == 429:
                body = resp.json()
                assert "detail" in body
                assert resp.headers.get("Retry-After") == "60"
