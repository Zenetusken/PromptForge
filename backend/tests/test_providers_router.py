"""Tests for the /api/providers endpoint."""

from unittest.mock import patch

import pytest

from app.providers import invalidate_detect_cache


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear provider caches between tests."""
    invalidate_detect_cache()
    import apps.promptforge.routers.providers as mod

    mod._cache = []
    mod._cache_time = 0
    yield
    invalidate_detect_cache()
    mod._cache = []
    mod._cache_time = 0


@pytest.mark.asyncio
async def test_providers_endpoint_returns_list(client):
    """The endpoint returns a list of provider info dicts."""
    response = await client.get("/api/apps/promptforge/providers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should contain at least the 4 registered providers
    assert len(data) >= 4
    for item in data:
        assert "name" in item
        assert "display_name" in item
        assert "model" in item
        assert "available" in item
        assert "is_default" in item
        assert isinstance(item["available"], bool)
        assert isinstance(item["is_default"], bool)


@pytest.mark.asyncio
async def test_providers_endpoint_contains_known_providers(client):
    """All four known provider names appear in the result."""
    response = await client.get("/api/apps/promptforge/providers")
    data = response.json()
    names = {p["name"] for p in data}
    assert "claude-cli" in names
    assert "anthropic" in names
    assert "openai" in names
    assert "gemini" in names


@pytest.mark.asyncio
async def test_providers_endpoint_with_no_available(client):
    """When no providers are available, all return available=False."""
    mock_providers = [
        {
            "name": "test",
            "display_name": "Test",
            "model": "",
            "available": False,
            "is_default": False,
        }
    ]
    with patch("apps.promptforge.routers.providers.list_all_providers", return_value=mock_providers):
        import apps.promptforge.routers.providers as mod

        mod._cache = []
        mod._cache_time = 0

        response = await client.get("/api/apps/promptforge/providers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["available"] is False


@pytest.mark.asyncio
async def test_validate_key_response_includes_provider_info(client):
    """Successful validation returns provider_name and model."""
    from app.providers.claude_cli import ClaudeCLIProvider

    async def mock_test_connection(timeout=10.0):
        return (True, None)

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch.object(ClaudeCLIProvider, "test_connection", mock_test_connection),
    ):
        response = await client.post(
            "/api/apps/promptforge/providers/validate-key",
            json={"provider": "claude-cli", "api_key": "unused"},
        )
    data = response.json()
    assert data["valid"] is True
    assert data["provider_name"] == "Claude CLI"
    assert "model" in data


@pytest.mark.asyncio
async def test_validate_key_failure_returns_error(client):
    """Failed validation returns valid=False with error message."""
    from app.providers.claude_cli import ClaudeCLIProvider

    async def mock_test_connection(timeout=10.0):
        return (False, "Invalid API key")

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch.object(ClaudeCLIProvider, "test_connection", mock_test_connection),
    ):
        response = await client.post(
            "/api/apps/promptforge/providers/validate-key",
            json={"provider": "claude-cli", "api_key": "bad-key"},
        )
    data = response.json()
    assert data["valid"] is False
    assert data["error"] == "Invalid API key"
    assert data["provider_name"] is None


@pytest.mark.asyncio
async def test_validate_key_unknown_provider(client):
    """Validating an unknown provider returns an error."""
    response = await client.post(
        "/api/apps/promptforge/providers/validate-key",
        json={"provider": "nonexistent", "api_key": "any"},
    )
    data = response.json()
    assert data["valid"] is False
    assert "Unknown LLM provider" in data["error"]


@pytest.mark.asyncio
async def test_validate_key_connection_timeout(client):
    """When test_connection times out, returns valid=False with timeout error."""
    from app.providers.claude_cli import ClaudeCLIProvider

    async def mock_test_connection(timeout=10.0):
        return (False, "Connection timed out")

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch.object(ClaudeCLIProvider, "test_connection", mock_test_connection),
    ):
        response = await client.post(
            "/api/apps/promptforge/providers/validate-key",
            json={"provider": "claude-cli", "api_key": "test-key"},
        )
    data = response.json()
    assert data["valid"] is False
    assert "timed out" in data["error"].lower()


@pytest.mark.asyncio
async def test_validate_key_missing_fields(client):
    """Missing required fields returns 422."""
    response = await client.post(
        "/api/apps/promptforge/providers/validate-key",
        json={"provider": "claude-cli"},  # missing api_key
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validate_key_empty_body(client):
    """Empty body returns 422."""
    response = await client.post(
        "/api/apps/promptforge/providers/validate-key",
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validate_key_import_error(client):
    """When provider requires uninstalled SDK, returns valid=False."""
    with patch(
        "apps.promptforge.routers.providers.get_provider",
        side_effect=ImportError("No module named 'openai'"),
    ):
        response = await client.post(
            "/api/apps/promptforge/providers/validate-key",
            json={"provider": "openai", "api_key": "sk-test"},
        )
    data = response.json()
    assert data["valid"] is False
    assert data["error"]


@pytest.mark.asyncio
async def test_providers_cache_hit(client):
    """Second request within TTL uses cached data."""
    # First request populates cache
    r1 = await client.get("/api/apps/promptforge/providers")
    assert r1.status_code == 200

    # Patch list_all_providers to detect if it's called again
    with patch("apps.promptforge.routers.providers.list_all_providers") as mock_list:
        r2 = await client.get("/api/apps/promptforge/providers")
        assert r2.status_code == 200
        # Should NOT have been called because cache is fresh
        mock_list.assert_not_called()
