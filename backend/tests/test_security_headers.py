"""Tests for the security headers middleware."""

import pytest


class TestSecurityHeaders:
    """All responses should include protective security headers."""

    @pytest.mark.asyncio
    async def test_headers_present_on_health(self, client):
        """Security headers are present on the health endpoint."""
        resp = await client.get("/api/apps/promptforge/health")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers["Permissions-Policy"]
        assert "default-src 'self'" in resp.headers["Content-Security-Policy"]

    @pytest.mark.asyncio
    async def test_headers_present_on_root(self, client):
        """Security headers are present on the root endpoint."""
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_headers_present_on_404(self, client):
        """Security headers are present even on error responses."""
        resp = await client.get("/api/nonexistent")
        assert resp.status_code in (404, 405)
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
