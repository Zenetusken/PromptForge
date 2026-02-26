"""Tests for MCP server authentication middleware."""

from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.mcp_auth import MCPAuthMiddleware


def _make_app(token: str = "") -> Starlette:
    """Create a minimal Starlette app with MCPAuthMiddleware for testing."""

    async def health(request):
        return JSONResponse({"status": "ok"})

    async def tool_endpoint(request):
        return PlainTextResponse("tool response")

    app = Starlette(routes=[
        Route("/health", health),
        Route("/sse", tool_endpoint),
        Route("/messages", tool_endpoint, methods=["POST"]),
    ])
    app.add_middleware(MCPAuthMiddleware, token=token)
    return app


class TestMCPAuthDisabled:
    """When MCP_AUTH_TOKEN is empty, all requests pass through."""

    def test_health_accessible(self):
        client = TestClient(_make_app(token=""))
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_tool_accessible_without_token(self):
        client = TestClient(_make_app(token=""))
        resp = client.get("/sse")
        assert resp.status_code == 200
        assert resp.text == "tool response"

    def test_post_accessible_without_token(self):
        client = TestClient(_make_app(token=""))
        resp = client.post("/messages")
        assert resp.status_code == 200


class TestMCPAuthEnabled:
    """When MCP_AUTH_TOKEN is set, bearer token is required."""

    TOKEN = "test-secret-token-123"

    def test_health_no_auth_required(self):
        client = TestClient(_make_app(token=self.TOKEN))
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_tool_rejected_without_token(self):
        client = TestClient(_make_app(token=self.TOKEN))
        resp = client.get("/sse")
        assert resp.status_code == 401
        assert "Authorization" in resp.json()["error"]

    def test_tool_accepted_with_valid_token(self):
        client = TestClient(_make_app(token=self.TOKEN))
        resp = client.get("/sse", headers={"Authorization": f"Bearer {self.TOKEN}"})
        assert resp.status_code == 200
        assert resp.text == "tool response"

    def test_tool_rejected_with_wrong_token(self):
        client = TestClient(_make_app(token=self.TOKEN))
        resp = client.get("/sse", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["error"]

    def test_post_rejected_without_token(self):
        client = TestClient(_make_app(token=self.TOKEN))
        resp = client.post("/messages")
        assert resp.status_code == 401

    def test_post_accepted_with_valid_token(self):
        client = TestClient(_make_app(token=self.TOKEN))
        resp = client.post("/messages", headers={"Authorization": f"Bearer {self.TOKEN}"})
        assert resp.status_code == 200

    def test_rejected_with_basic_auth(self):
        """Only Bearer scheme is accepted."""
        client = TestClient(_make_app(token=self.TOKEN))
        resp = client.get("/sse", headers={"Authorization": f"Basic {self.TOKEN}"})
        assert resp.status_code == 401
