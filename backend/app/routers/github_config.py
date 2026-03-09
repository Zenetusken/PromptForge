"""GitHub App credential configuration endpoints.

GET  /api/github/app-config  — always public; returns masked credential status.
PATCH /api/github/app-config — unauthenticated when no credentials are configured
                               (bootstrap path); JWT-required once credentials exist.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_user
from app.services.github_credentials_service import get_config_status, save_credentials

logger = logging.getLogger(__name__)
router = APIRouter(tags=["github-config"])


class UpdateGitHubConfigRequest(BaseModel):
    client_id: str
    client_secret: str

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("client_id must not be empty")
        if len(v) < 10:
            raise ValueError("client_id must be at least 10 characters")
        return v

    @field_validator("client_secret")
    @classmethod
    def validate_client_secret(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("client_secret must not be empty")
        if len(v) < 16:
            raise ValueError("client_secret must be at least 16 characters")
        return v


@router.get("/api/github/app-config")
async def get_github_app_config() -> dict:
    """Return masked credential status. Always public — used by AuthGate on load."""
    return get_config_status()


@router.patch("/api/github/app-config")
async def update_github_app_config(
    body: UpdateGitHubConfigRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Save GitHub App credentials and hot-reload the settings singleton.

    Bootstrap mode (no credentials configured): allowed without authentication.
    Update mode (credentials already exist): a valid JWT is required. The
    get_current_user dependency raises naturally with structured error codes
    (AUTH_TOKEN_MISSING / AUTH_TOKEN_EXPIRED / AUTH_TOKEN_INVALID) so callers
    can distinguish the failure reason.
    """
    if get_config_status()["configured"]:
        # Credentials exist — require JWT. Let get_current_user raise naturally;
        # do NOT catch HTTPException so structured detail codes are preserved.
        await get_current_user(request, session)

    save_credentials(body.client_id, body.client_secret)
    logger.info("GitHub App credentials updated via API")
    return {"ok": True, **get_config_status()}
