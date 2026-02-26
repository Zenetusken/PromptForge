"""GitHub OAuth and REST API client.

Uses direct httpx calls — no heavy SDK. GitHub OAuth is 2 HTTP calls;
GitHub REST API is standard REST with Bearer token auth.
Token encryption uses Fernet symmetric encryption at rest.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app import config

logger = logging.getLogger(__name__)

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create the Fernet encryption instance.

    Auto-generates a key on first call if ENCRYPTION_KEY is not set,
    and writes it to a local keyfile for persistence across restarts.
    """
    global _fernet
    if _fernet is not None:
        return _fernet

    key = config.ENCRYPTION_KEY
    if not key:
        # Try to load from keyfile
        keyfile = config.BASE_DIR / "data" / ".encryption_key"
        if keyfile.exists():
            key = keyfile.read_text().strip()
        else:
            key = Fernet.generate_key().decode()
            keyfile.parent.mkdir(parents=True, exist_ok=True)
            keyfile.write_text(key)
            os.chmod(keyfile, 0o600)
            logger.info("Generated new encryption key at %s", keyfile)

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)

    # Validate the key works by round-tripping a test string.
    # Detects key replacement or corruption before real decrypt calls fail.
    try:
        _fernet.decrypt(_fernet.encrypt(b"promptforge-key-check"))
    except Exception:
        logger.critical(
            "ENCRYPTION KEY MISMATCH: The encryption key at %s cannot "
            "decrypt data it just encrypted. If you replaced or regenerated "
            "the key file, previously encrypted GitHub tokens will be "
            "unrecoverable. Delete data/.encryption_key and stored GitHub "
            "connections to start fresh.",
            config.BASE_DIR / "data" / ".encryption_key",
        )

    return _fernet


def encrypt_token(token: str) -> str:
    """Encrypt an access token for storage."""
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str | None:
    """Decrypt a stored token. Returns None on failure."""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        logger.warning("Token decryption failed: invalid or corrupted token")
        return None
    except Exception as exc:
        logger.warning("Token decryption failed: %s", exc)
        return None


# --- OAuth CSRF State Management ---
# In-memory store: state_token -> expiry_timestamp (TTL 10 min)
_oauth_states: dict[str, float] = {}


def create_oauth_state() -> str:
    """Generate a CSRF state token for OAuth and store it with a 10-min TTL."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time() + 600  # 10 min TTL
    # Prune expired entries
    now = time.time()
    expired = [k for k, v in _oauth_states.items() if v < now]
    for k in expired:
        del _oauth_states[k]
    return state


def validate_oauth_state(state: str) -> bool:
    """Validate and consume a one-time OAuth CSRF state token."""
    if not state or state not in _oauth_states:
        return False
    if time.time() > _oauth_states[state]:
        del _oauth_states[state]
        return False
    del _oauth_states[state]  # one-time use
    return True


# --- Config Resolution ---

async def resolve_github_config(
    session: AsyncSession,
) -> tuple[str, str, str, str] | None:
    """Resolve GitHub OAuth config: DB record > env vars.

    Returns (client_id, client_secret, redirect_uri, scope) or None.
    """
    from sqlalchemy import select

    from app.models.workspace import GitHubOAuthConfig

    try:
        result = await session.execute(select(GitHubOAuthConfig).limit(1))
        cfg = result.scalar_one_or_none()
        if cfg:
            secret = decrypt_token(cfg.client_secret_encrypted)
            if secret:
                return cfg.client_id, secret, cfg.redirect_uri, cfg.scope
            logger.warning("Stored GitHub OAuth config decryption failed; trying env fallback")
    except Exception as exc:
        logger.warning("Failed to read GitHub OAuth config from DB: %s", type(exc).__name__)

    # Fall back to env vars
    if config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET:
        return (
            config.GITHUB_CLIENT_ID,
            config.GITHUB_CLIENT_SECRET,
            config.GITHUB_REDIRECT_URI,
            config.GITHUB_SCOPE,
        )
    return None


def get_oauth_authorize_url(
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str | None = None,
) -> dict:
    """Build the GitHub OAuth authorization URL.

    Returns dict with url and state (for CSRF verification).
    """
    if state is None:
        state = create_oauth_state()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return {
        "url": f"{GITHUB_OAUTH_AUTHORIZE_URL}?{query}",
        "state": state,
    }


async def exchange_code_for_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange an OAuth authorization code for an access token.

    Returns dict with access_token, token_type, scope.
    Raises httpx.HTTPStatusError on failure.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GITHUB_OAUTH_TOKEN_URL,
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise ValueError(f"GitHub OAuth error: {data['error_description']}")

    return {
        "access_token": data["access_token"],
        "token_type": data.get("token_type", "bearer"),
        "scope": data.get("scope", ""),
    }


async def revoke_token(
    access_token: str,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> bool:
    """Revoke a GitHub OAuth token. Returns True if successful."""
    cid = client_id or config.GITHUB_CLIENT_ID
    csecret = client_secret or config.GITHUB_CLIENT_SECRET
    if not cid or not csecret:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{GITHUB_API_BASE}/applications/{cid}/token",
                auth=(cid, csecret),
                json={"access_token": access_token},
            )
            return resp.status_code == 204
    except Exception as exc:
        logger.warning("Token revocation failed: %s", exc)
        return False


class GitHubAPI:
    """Lightweight GitHub REST API client."""

    def __init__(self, access_token: str):
        self._token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_user(self) -> dict:
        """GET /user — authenticated user info."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/user", headers=self._headers
            )
            resp.raise_for_status()
            return resp.json()

    async def list_repos(
        self, per_page: int = 30, page: int = 1, sort: str = "updated",
    ) -> list[dict]:
        """GET /user/repos — list repos for authenticated user."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/user/repos",
                headers=self._headers,
                params={"sort": sort, "per_page": per_page, "page": page},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_repo(self, owner: str, repo: str) -> dict:
        """GET /repos/{owner}/{repo} — repo metadata."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_file_tree(
        self, owner: str, repo: str, sha: str = "HEAD",
    ) -> list[dict]:
        """GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1 — file tree."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{sha}",
                headers=self._headers,
                params={"recursive": "1"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("tree", [])

    async def get_file_content(self, owner: str, repo: str, path: str) -> str | None:
        """GET /repos/{owner}/{repo}/contents/{path} — file content (base64 decoded).

        Returns decoded UTF-8 content or None on error.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
                headers=self._headers,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("encoding") == "base64" and data.get("content"):
                try:
                    return base64.b64decode(data["content"]).decode("utf-8")
                except Exception:
                    return None
            return None

    async def get_rate_limit(self) -> dict:
        """GET /rate_limit — API rate limit info."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/rate_limit", headers=self._headers
            )
            resp.raise_for_status()
            return resp.json()

    async def check_token_valid(self) -> bool:
        """Quick check if the token is still valid."""
        try:
            await self.get_user()
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return False
            raise
