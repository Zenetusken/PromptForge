"""Tests for the CSRF protection middleware."""

import pytest


class TestCSRFProtection:
    """Origin-based CSRF validation for state-changing requests."""

    @pytest.mark.asyncio
    async def test_get_request_no_origin_passes(self, client):
        """GET requests are never blocked by CSRF."""
        resp = await client.get("/api/apps/promptforge/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_post_without_origin_passes(self, client):
        """POST without Origin header is allowed (non-browser request)."""
        resp = await client.delete(
            "/api/apps/promptforge/history/all",
            headers={"X-Confirm-Delete": "yes"},
        )
        # Should pass CSRF (may be 200 for empty history)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_post_with_allowed_origin_passes(self, client):
        """POST with matching frontend origin passes CSRF."""
        resp = await client.delete(
            "/api/apps/promptforge/history/all",
            headers={
                "Origin": "http://localhost:5199",
                "X-Confirm-Delete": "yes",
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_post_with_disallowed_origin_rejected(self, client):
        """POST with unknown origin is rejected with 403."""
        resp = await client.delete(
            "/api/apps/promptforge/history/all",
            headers={
                "Origin": "http://evil.example.com",
                "X-Confirm-Delete": "yes",
            },
        )
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_post_with_backend_origin_passes(self, client):
        """POST from backend's own origin (API docs) passes CSRF."""
        resp = await client.delete(
            "/api/apps/promptforge/history/all",
            headers={
                "Origin": "http://localhost:8000",
                "X-Confirm-Delete": "yes",
            },
        )
        assert resp.status_code == 200
