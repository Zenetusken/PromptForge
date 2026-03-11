"""Auth service: JWT pair issuance and cookie helpers shared across auth routers."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

from fastapi import Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.auth import RefreshToken, User
from app.utils.jwt import hash_token, sign_access_token, sign_refresh_token


def set_refresh_cookie(response: Response | RedirectResponse, raw_refresh: str) -> None:
    """Set the httponly refresh token cookie on any response type.

    Centralised here to avoid duplicating cookie parameters across routers.
    Both the OAuth callback (github_auth) and the refresh endpoint (auth)
    call this function.
    """
    response.set_cookie(
        key="jwt_refresh_token",
        value=raw_refresh,
        httponly=True,
        samesite="strict",
        path="/auth/jwt/refresh",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        secure=settings.JWT_COOKIE_SECURE,
    )


async def issue_jwt_pair(
    session: AsyncSession,
    user: User,
    device_id: str | None = None,
) -> tuple[str, str]:
    """Persist a new RefreshToken row and return ``(access_token, raw_refresh_token)``.

    The caller is responsible for committing the session.  ``session.flush()``
    is *not* called here — the caller must ensure ``user.id`` is populated
    before calling this function (use ``session.flush()`` after adding a new
    User row).

    Args:
        session: async DB session (caller commits).
        user: User record (must already be flushed — user.id must be populated).
        device_id: Optional per-device identifier. Generated if not provided.

    Returns:
        (access_token, raw_refresh_token) where ``raw_refresh_token`` is the
        plaintext token to be placed in the httponly cookie.  Only its SHA-256
        hash is stored in the database.
    """
    if device_id is None:
        device_id = str(_uuid.uuid4())

    raw_refresh = sign_refresh_token(user.id)
    token_hash = hash_token(raw_refresh)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        revoked=False,
        device_id=device_id,
    )
    session.add(refresh_record)

    access_token = sign_access_token(user.id, user.github_login, [user.role.value], device_id=device_id)
    return access_token, raw_refresh
