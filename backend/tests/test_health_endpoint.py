"""Tests for health check endpoints."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/health")
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
async def test_health_alias(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_no_provider_available(client):
    """When no LLM provider is available, health still returns ok."""
    with patch("app.routers.health.get_provider", side_effect=RuntimeError("No provider")):
        response = await client.get("/api/health")
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
    with patch("app.routers.health.get_provider", return_value=mock_provider):
        response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["llm_available"] is False
    assert data["llm_provider"] == "Test Provider"
    assert data["llm_model"] == "test-model"


@pytest.mark.asyncio
async def test_health_db_failure(client):
    """When DB query fails, db_connected=False but status still ok."""
    from sqlalchemy.exc import SQLAlchemyError

    with patch("app.routers.health.text", side_effect=SQLAlchemyError("DB down")):
        response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["db_connected"] is False


@pytest.mark.asyncio
async def test_health_head_request(client):
    """HEAD request returns 200."""
    response = await client.head("/api/health")
    assert response.status_code == 200
