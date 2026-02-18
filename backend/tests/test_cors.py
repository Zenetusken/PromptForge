"""Tests for CORS configuration including multi-origin support."""

import pytest

from app import config


class TestCORSOriginParsing:
    """Test the comma-separated origin parsing logic used in CORS setup."""

    def test_single_origin_parsed(self):
        """Single origin is parsed correctly."""
        origins = [o.strip() for o in "http://localhost:5199".split(",")]
        assert origins == ["http://localhost:5199"]

    def test_multi_origin_parsed(self):
        """Comma-separated origins are parsed and stripped."""
        origins = [o.strip() for o in "http://localhost:5199, http://localhost:3000".split(",")]
        assert origins == ["http://localhost:5199", "http://localhost:3000"]

    def test_whitespace_handling(self):
        """Extra whitespace around origins is stripped."""
        origins = [
            o.strip()
            for o in "  http://a.com ,  http://b.com  ,http://c.com".split(",")
        ]
        assert origins == ["http://a.com", "http://b.com", "http://c.com"]

    def test_default_frontend_url(self):
        """Default FRONTEND_URL produces expected origin."""
        origins = [o.strip() for o in config.FRONTEND_URL.split(",")]
        assert "http://localhost:5199" in origins


@pytest.mark.asyncio
async def test_cors_allows_configured_origin(client):
    """The app responds with CORS headers for the configured origin."""
    origins = [o.strip() for o in config.FRONTEND_URL.split(",")]
    response = await client.options(
        "/api/health",
        headers={
            "Origin": origins[0],
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS preflight should succeed
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origins[0]


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(client):
    """The app does not return CORS headers for an unknown origin."""
    response = await client.options(
        "/api/health",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Unknown origin should not get allow-origin header
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin != "http://evil.example.com"
