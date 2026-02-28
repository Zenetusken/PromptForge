"""Tests for health check endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.promptforge.routers.health import _probe_mcp


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/apps/promptforge/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "db_connected" in data
    assert "version" in data
    # Provider-agnostic fields
    assert "llm_available" in data
    assert "llm_provider" in data
    assert "llm_model" in data
    # Backward compat
    assert "claude_available" in data
    assert data["claude_available"] == data["llm_available"]


@pytest.mark.asyncio
async def test_health_includes_mcp_connected(client):
    """Health response includes mcp_connected field as a boolean."""
    with patch("apps.promptforge.routers.health._probe_mcp", return_value=False):
        response = await client.get("/api/apps/promptforge/health")
    data = response.json()
    assert "mcp_connected" in data
    assert isinstance(data["mcp_connected"], bool)


@pytest.mark.asyncio
async def test_health_no_provider_available(client):
    """When no LLM provider is available, health still returns ok."""
    with patch("apps.promptforge.routers.health.get_provider", side_effect=RuntimeError("No provider")):
        response = await client.get("/api/apps/promptforge/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["llm_available"] is False
    assert data["llm_provider"] == "none"
    assert data["llm_model"] == ""


@pytest.mark.asyncio
async def test_health_provider_unavailable(client):
    """When provider exists but is_available() returns False."""
    mock_provider = MagicMock()
    mock_provider.is_available.return_value = False
    mock_provider.provider_name = "Test Provider"
    mock_provider.model_name = "test-model"
    with patch("apps.promptforge.routers.health.get_provider", return_value=mock_provider):
        response = await client.get("/api/apps/promptforge/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["llm_available"] is False
    assert data["llm_provider"] == "Test Provider"
    assert data["llm_model"] == "test-model"


@pytest.mark.asyncio
async def test_health_db_failure(client):
    """When DB query fails, db_connected=False but status still ok."""
    from sqlalchemy.exc import SQLAlchemyError

    with patch("apps.promptforge.routers.health.text", side_effect=SQLAlchemyError("DB down")):
        response = await client.get("/api/apps/promptforge/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["db_connected"] is False


@pytest.mark.asyncio
async def test_health_head_request(client):
    """HEAD request returns 200."""
    response = await client.head("/api/apps/promptforge/health")
    assert response.status_code == 200


# --- MCP probe tests ---


class TestHealthMcpConnected:
    """Tests for MCP connectivity probe in the health endpoint."""

    @pytest.mark.asyncio
    async def test_health_mcp_connected(self, client):
        """When MCP server is up, mcp_connected=True."""
        with patch("apps.promptforge.routers.health._probe_mcp", return_value=True):
            response = await client.get("/api/apps/promptforge/health")
        data = response.json()
        assert data["status"] == "ok"
        assert data["mcp_connected"] is True

    @pytest.mark.asyncio
    async def test_health_mcp_disconnected_does_not_degrade(self, client):
        """When MCP is down, status is still 'ok' — MCP is optional."""
        with patch("apps.promptforge.routers.health._probe_mcp", return_value=False):
            response = await client.get("/api/apps/promptforge/health")
        data = response.json()
        assert data["status"] == "ok"
        assert data["mcp_connected"] is False


class TestProbeMcp:
    """Unit tests for the _probe_mcp helper function."""

    @pytest.mark.asyncio
    async def test_probe_mcp_success(self):
        """Returns True when MCP responds with status ok."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "server": "promptforge_mcp"}

        with patch("apps.promptforge.routers.health._mcp_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await _probe_mcp()
        assert result is True

    @pytest.mark.asyncio
    async def test_probe_mcp_connection_refused(self):
        """Returns False when MCP server is not running."""
        with patch("apps.promptforge.routers.health._mcp_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            result = await _probe_mcp()
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_mcp_timeout(self):
        """Returns False when MCP server times out."""
        with patch("apps.promptforge.routers.health._mcp_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("Timeout"))
            result = await _probe_mcp()
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_mcp_bad_response(self):
        """Returns False when MCP responds with unexpected status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "error"}

        with patch("apps.promptforge.routers.health._mcp_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await _probe_mcp()
        assert result is False
