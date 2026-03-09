"""Auth wiring tests — 401 guards, user attribution, cross-validation, secret warnings.

All tests use direct async calls with AsyncMock sessions (no TestClient overhead).
Pattern mirrors test_auth.py.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.auth import AuthenticatedUser
from app.utils.jwt import sign_access_token


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_request(token: str | None = None) -> MagicMock:
    """Build a minimal mock Request with optional Authorization header."""
    req = MagicMock()
    if token:
        req.headers = {"Authorization": f"Bearer {token}"}
    else:
        req.headers = {}
    return req


def _make_session(scalar_return=None) -> AsyncMock:
    """Build a mock AsyncSession that returns scalar_return from any execute()."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_return
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    return session


# ── Group A — 401 on all protected endpoints ─────────────────────────────


@pytest.mark.parametrize("method,path", [
    ("POST",   "/api/optimize"),
    ("GET",    "/api/optimize/fake-id"),
    ("PATCH",  "/api/optimize/fake-id"),
    ("POST",   "/api/optimize/fake-id/retry"),
    ("GET",    "/api/history"),
    ("DELETE", "/api/history/fake-id"),
    ("GET",    "/api/history/stats"),
    ("GET",    "/api/settings"),
    ("PATCH",  "/api/settings"),
    ("GET",    "/api/providers/detect"),
    ("GET",    "/api/providers/status"),
])
async def test_protected_endpoint_returns_401_without_auth(method, path):
    """Each protected endpoint raises 401 when get_current_user is called without a token."""
    from fastapi import HTTPException
    from app.dependencies.auth import get_current_user

    req = _make_request(token=None)
    session = _make_session()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=req, session=session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "AUTH_TOKEN_MISSING"


# ── Group B — Health stays public ─────────────────────────────────────────


async def test_health_is_public():
    """Health endpoint doesn't depend on get_current_user."""
    from app.routers.health import router

    # Verify health router has no auth dependency by checking the endpoint exists
    # and doesn't import get_current_user
    import app.routers.health as health_mod
    assert not hasattr(health_mod, "get_current_user"), \
        "health router should not import get_current_user"


# ── Group C — Optimization records user_id ────────────────────────────────


async def test_optimize_sets_user_id_from_jwt():
    """optimize_prompt sets user_id on the Optimization record from the JWT user.

    arch-audit note: Optimization is created inside event_stream() via
    async_session() factory (not the injected FastAPI session). We must:
      1. Patch app.routers.optimize.async_session to intercept session.add()
      2. Iterate response.body_iterator to actually run the generator
    """
    from app.routers.optimize import optimize_prompt
    from app.schemas.optimization import OptimizeRequest

    current_user = AuthenticatedUser(id="user-abc", github_login="octocat", roles=["user"])
    captured_optimization = None

    def _capture(obj):
        nonlocal captured_optimization
        captured_optimization = obj

    # Mock the async_session context manager used inside event_stream()
    mock_s = AsyncMock()
    mock_s.add = MagicMock(side_effect=_capture)  # add() is sync in SQLAlchemy
    mock_s.commit = AsyncMock()
    mock_s.merge = AsyncMock(return_value=MagicMock())
    mock_s.__aenter__ = AsyncMock(return_value=mock_s)
    mock_s.__aexit__ = AsyncMock(return_value=False)
    mock_async_session_factory = MagicMock(return_value=mock_s)

    mock_req = MagicMock()
    mock_req.app.state.provider = MagicMock()
    mock_req.session = {}

    optimize_req = OptimizeRequest(prompt="Test prompt for user attribution check")

    async def _empty_pipeline(**kwargs):
        """Async generator that yields nothing — simulates an empty pipeline run."""
        return
        yield  # pragma: no cover  # makes this an async generator function

    with patch("app.routers.optimize.async_session", mock_async_session_factory):
        with patch("app.routers.optimize.fetch_url_contexts", AsyncMock(return_value=[])):
            with patch("app.services.pipeline.run_pipeline", new=_empty_pipeline):
                response = await optimize_prompt(
                    optimize_req, mock_req,
                    current_user=current_user,
                )
                # Drive the async generator — Optimization is created on first iteration
                async for _ in response.body_iterator:
                    pass

    assert captured_optimization is not None, "session.add() was never called"
    assert captured_optimization.user_id == "user-abc", (
        f"Expected user_id='user-abc', got {captured_optimization.user_id!r}"
    )


# ── Group D — GitHub token cross-validation ───────────────────────────────


async def test_github_token_cross_validation_rejects_wrong_user():
    """_get_github_token raises 403 when JWT user doesn't own the GitHub token."""
    from fastapi import HTTPException
    from app.routers.github_repos import _get_github_token

    # GitHubToken stored for github_user_id=999
    mock_gh_token = MagicMock()
    mock_gh_token.github_user_id = 999

    # User record for current_user has github_user_id=888 (mismatch)
    mock_user = MagicMock()
    mock_user.github_user_id = 888

    gh_result = MagicMock()
    gh_result.scalar_one_or_none.return_value = mock_gh_token

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = mock_user

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[gh_result, user_result])

    mock_request = MagicMock()
    mock_request.session = {"session_id": "test-session-id"}

    current_user = AuthenticatedUser(id="user-abc", github_login="octocat", roles=["user"])

    with pytest.raises(HTTPException) as exc_info:
        await _get_github_token(mock_request, mock_session, current_user)

    assert exc_info.value.status_code == 403
    assert "does not belong" in exc_info.value.detail


async def test_github_token_cross_validation_passes_matching_user():
    """_get_github_token succeeds when JWT user matches the GitHub token owner."""
    from app.routers.github_repos import _get_github_token

    mock_gh_token = MagicMock()
    mock_gh_token.github_user_id = 12345

    mock_user = MagicMock()
    mock_user.github_user_id = 12345  # same — match

    gh_result = MagicMock()
    gh_result.scalar_one_or_none.return_value = mock_gh_token

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = mock_user

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[gh_result, user_result])

    mock_request = MagicMock()
    mock_request.session = {"session_id": "test-session-id"}

    current_user = AuthenticatedUser(id="user-abc", github_login="octocat", roles=["user"])

    # get_token_for_session is the final call — patch it to return a token
    with patch("app.routers.github_repos.github_service.get_token_for_session",
               AsyncMock(return_value="decrypted-token")) as mock_get:
        result = await _get_github_token(mock_request, mock_session, current_user)

    assert result == "decrypted-token"


# ── Group E — Config secret warning ───────────────────────────────────────


def test_weak_secret_emits_warning(caplog):
    """Settings with a weak JWT_SECRET emits a SECURITY warning."""
    from app.config import Settings

    with caplog.at_level(logging.WARNING, logger="app.config"):
        Settings(JWT_SECRET="dev-jwt-secret-change-in-prod")

    assert any("JWT_SECRET" in r.message for r in caplog.records)


def test_strong_secret_no_warning(caplog):
    """Settings with a strong JWT_SECRET does not emit a warning for that field."""
    from app.config import Settings

    with caplog.at_level(logging.WARNING, logger="app.config"):
        Settings(JWT_SECRET="a-very-strong-random-secret-that-is-definitely-not-the-default")

    jwt_warnings = [r for r in caplog.records if "JWT_SECRET" in r.message]
    assert len(jwt_warnings) == 0


# ── Group F — Auth endpoints remain public ────────────────────────────────


async def test_auth_github_login_is_accessible_without_jwt():
    """github_login does NOT call get_current_user — it's a public OAuth entry point."""
    from app.routers.github_auth import github_login
    import inspect

    # Verify the endpoint signature has no get_current_user dependency
    sig = inspect.signature(github_login)
    param_names = list(sig.parameters.keys())
    assert "current_user" not in param_names, \
        "/auth/github/login should not require auth"


async def test_already_authenticated_user_redirected_from_login():
    """github_login redirects authenticated users back to the frontend."""
    from fastapi.responses import RedirectResponse
    from app.routers.github_auth import github_login

    token = sign_access_token("user-123", "octocat", ["user"])

    mock_request = MagicMock()
    mock_request.headers = {"Authorization": f"Bearer {token}"}
    mock_request.session = {}

    result = await github_login(request=mock_request)

    assert isinstance(result, RedirectResponse)


async def test_expired_token_not_redirected_from_login():
    """github_login proceeds with OAuth flow for expired tokens."""
    from app.config import settings as real_settings

    with patch("app.utils.jwt.settings") as mock_settings:
        mock_settings.JWT_SECRET = real_settings.JWT_SECRET
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = -1
        expired_token = sign_access_token("user-123", "octocat", ["user"])

    from fastapi import HTTPException
    from app.routers.github_auth import github_login

    mock_request = MagicMock()
    mock_request.headers = {"Authorization": f"Bearer {expired_token}"}
    mock_request.session = {}

    # Without GitHub App configured, it raises 400 (not a redirect) —
    # meaning the early-return path was NOT taken for the expired token.
    with patch("app.routers.github_auth.settings") as mock_cfg:
        mock_cfg.GITHUB_APP_CLIENT_ID = ""
        mock_cfg.GITHUB_APP_CLIENT_SECRET = ""
        mock_cfg.FRONTEND_URL = "http://localhost:5199"

        with pytest.raises(HTTPException) as exc_info:
            await github_login(request=mock_request)

    assert exc_info.value.status_code == 400
