"""Tests for GET/PATCH /api/github/app-config.

Business logic verified:
  - GET is always public and returns masked status
  - PATCH allows unauthenticated access when no credentials exist (bootstrap)
  - PATCH raises 401 with structured error codes when credentials exist + no JWT
  - PATCH saves credentials with a valid JWT when credentials already exist
  - Pydantic validators enforce minimum length and strip whitespace
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.github_config import (
    UpdateGitHubConfigRequest,
    get_github_app_config,
    update_github_app_config,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_request(token: str | None = None) -> MagicMock:
    """Build a minimal mock Request with optional Authorization header."""
    req = MagicMock()
    req.headers = {"Authorization": f"Bearer {token}"} if token else {}
    return req


def _make_session(scalar_return=None) -> AsyncMock:
    """Build a mock AsyncSession that returns scalar_return from any execute()."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_return
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    return session


_UNCONFIGURED = {"configured": False, "client_id_masked": "", "has_secret": False}
_CONFIGURED = {"configured": True, "client_id_masked": "Iv1.abcd••••wxyz", "has_secret": True}


# ── A — GET is always public ──────────────────────────────────────────────


async def test_get_app_config_when_unconfigured():
    """GET returns configured=False when no credentials are set."""
    with patch("app.routers.github_config.get_config_status", return_value=_UNCONFIGURED):
        result = await get_github_app_config()

    assert result["configured"] is False
    assert result["client_id_masked"] == ""
    assert result["has_secret"] is False


async def test_get_app_config_when_configured():
    """GET returns configured=True with masked client_id when credentials exist."""
    with patch("app.routers.github_config.get_config_status", return_value=_CONFIGURED):
        result = await get_github_app_config()

    assert result["configured"] is True
    assert "••••" in result["client_id_masked"]
    assert result["has_secret"] is True


# ── B — PATCH bootstrap (unconfigured, no auth required) ──────────────────


async def test_patch_bootstrap_succeeds_without_auth():
    """Bootstrap path: PATCH saves credentials without a JWT when unconfigured."""
    body = UpdateGitHubConfigRequest(
        client_id="Iv1.testcredential",
        client_secret="abcdef1234567890xxxx",
    )
    req = _make_request(token=None)
    session = _make_session()

    # First call: auth check skipped (configured=False).
    # Second call: return value after save (configured=True).
    side_effects = [_UNCONFIGURED, _CONFIGURED]
    with patch("app.routers.github_config.get_config_status", side_effect=side_effects):
        with patch("app.routers.github_config.save_credentials") as mock_save:
            result = await update_github_app_config(body, req, session)

    mock_save.assert_called_once_with("Iv1.testcredential", "abcdef1234567890xxxx")
    assert result["ok"] is True
    assert result["configured"] is True


# ── C — PATCH update requires JWT when credentials exist ──────────────────


async def test_patch_update_raises_401_without_token():
    """PATCH raises 401 (AUTH_TOKEN_MISSING) when credentials exist and no JWT provided."""
    body = UpdateGitHubConfigRequest(
        client_id="Iv1.newcredential1",
        client_secret="newsecret1234567890x",
    )
    req = _make_request(token=None)
    session = _make_session()

    with patch("app.routers.github_config.get_config_status", return_value=_CONFIGURED):
        with pytest.raises(HTTPException) as exc_info:
            await update_github_app_config(body, req, session)

    assert exc_info.value.status_code == 401
    # Structured detail code must be preserved (not overwritten with a plain string).
    assert exc_info.value.detail["code"] == "AUTH_TOKEN_MISSING"


async def test_patch_update_raises_401_with_invalid_token():
    """PATCH raises 401 (AUTH_TOKEN_INVALID) with a tampered JWT."""
    body = UpdateGitHubConfigRequest(
        client_id="Iv1.newcredential1",
        client_secret="newsecret1234567890x",
    )
    req = _make_request(token="not.a.real.jwt.token")
    session = _make_session()

    with patch("app.routers.github_config.get_config_status", return_value=_CONFIGURED):
        with pytest.raises(HTTPException) as exc_info:
            await update_github_app_config(body, req, session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "AUTH_TOKEN_INVALID"


# ── D — PATCH update succeeds with a valid JWT ────────────────────────────


async def test_patch_update_succeeds_with_valid_jwt():
    """PATCH saves credentials when a valid JWT is supplied and credentials exist."""
    from app.utils.jwt import sign_access_token

    token = sign_access_token("user-123", "octocat", ["user"])
    body = UpdateGitHubConfigRequest(
        client_id="Iv1.newcredential1",
        client_secret="newsecret1234567890x",
    )
    req = _make_request(token=token)
    session = _make_session()  # no revoked refresh token

    side_effects = [_CONFIGURED, _CONFIGURED]
    with patch("app.routers.github_config.get_config_status", side_effect=side_effects):
        with patch("app.routers.github_config.save_credentials") as mock_save:
            result = await update_github_app_config(body, req, session)

    mock_save.assert_called_once_with("Iv1.newcredential1", "newsecret1234567890x")
    assert result["ok"] is True


# ── E — Pydantic field validators ─────────────────────────────────────────


def test_request_rejects_short_client_id():
    """client_id shorter than 10 chars after strip raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateGitHubConfigRequest(client_id="short", client_secret="abcdef1234567890")
    assert "client_id" in str(exc_info.value)


def test_request_rejects_short_client_secret():
    """client_secret shorter than 16 chars after strip raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateGitHubConfigRequest(client_id="Iv1.xxxxxxxxxxx", client_secret="tooshort")
    assert "client_secret" in str(exc_info.value)


def test_request_rejects_whitespace_only_client_id():
    """Whitespace-only client_id is rejected after stripping."""
    with pytest.raises(ValidationError):
        UpdateGitHubConfigRequest(client_id="          ", client_secret="abcdef1234567890")


def test_request_strips_whitespace_from_both_fields():
    """Leading/trailing whitespace is stripped from both fields before validation."""
    req = UpdateGitHubConfigRequest(
        client_id="  Iv1.xxxxxxxxxxx  ",
        client_secret="  abcdef1234567890  ",
    )
    assert req.client_id == "Iv1.xxxxxxxxxxx"
    assert req.client_secret == "abcdef1234567890"


def test_request_accepts_valid_credentials():
    """Valid client_id (≥10 chars) and client_secret (≥16 chars) are accepted."""
    req = UpdateGitHubConfigRequest(
        client_id="Iv1.xxxxxxxxxxx",
        client_secret="abcdef1234567890",
    )
    assert req.client_id == "Iv1.xxxxxxxxxxx"
    assert req.client_secret == "abcdef1234567890"
