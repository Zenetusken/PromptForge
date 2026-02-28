"""Tests for the bearer token authentication middleware."""

from unittest.mock import patch

import pytest


@pytest.fixture()
def auth_client(client):
    """Return the test client with AUTH_TOKEN set."""
    return client


class TestAuthDisabled:
    """When AUTH_TOKEN is empty, all requests pass through."""

    @pytest.mark.asyncio
    async def test_no_auth_required_when_token_empty(self, client):
        """Requests succeed without Authorization header when AUTH_TOKEN is empty."""
        with patch("app.middleware.auth.config") as mock_config:
            mock_config.AUTH_TOKEN = ""
            resp = await client.get("/api/apps/promptforge/health")
            assert resp.status_code == 200


class TestAuthEnabled:
    """When AUTH_TOKEN is set, non-exempt endpoints require valid bearer token."""

    @pytest.mark.asyncio
    async def test_health_exempt(self, client):
        """Health endpoint is always accessible without auth."""
        with patch("app.middleware.auth.config") as mock_config:
            mock_config.AUTH_TOKEN = "secret123"
            resp = await client.get("/api/apps/promptforge/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_root_exempt(self, client):
        """Root endpoint is always accessible without auth."""
        with patch("app.middleware.auth.config") as mock_config:
            mock_config.AUTH_TOKEN = "secret123"
            resp = await client.get("/")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_auth_header(self, client):
        """Returns 401 when Authorization header is missing."""
        with patch("app.middleware.auth.config") as mock_config:
            mock_config.AUTH_TOKEN = "secret123"
            resp = await client.get("/api/apps/promptforge/history")
            assert resp.status_code == 401
            assert "Missing" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_token(self, client):
        """Returns 401 when token doesn't match."""
        with patch("app.middleware.auth.config") as mock_config:
            mock_config.AUTH_TOKEN = "secret123"
            resp = await client.get(
                "/api/apps/promptforge/history",
                headers={"Authorization": "Bearer wrongtoken"},
            )
            assert resp.status_code == 401
            assert "Invalid" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_valid_token(self, client):
        """Returns success when token matches."""
        with patch("app.middleware.auth.config") as mock_config:
            mock_config.AUTH_TOKEN = "secret123"
            resp = await client.get(
                "/api/apps/promptforge/history",
                headers={"Authorization": "Bearer secret123"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_wrong_auth_scheme(self, client):
        """Returns 401 when using non-Bearer scheme."""
        with patch("app.middleware.auth.config") as mock_config:
            mock_config.AUTH_TOKEN = "secret123"
            resp = await client.get(
                "/api/apps/promptforge/history",
                headers={"Authorization": "Basic dXNlcjpwYXNz"},
            )
            assert resp.status_code == 401
