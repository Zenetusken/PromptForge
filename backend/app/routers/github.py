"""GitHub OAuth and workspace management endpoints."""

import json
import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.database import get_db, get_db_readonly
from app.models.workspace import GitHubConnection, WorkspaceLink
from app.repositories.workspace import WorkspaceRepository
from app.schemas.context import context_to_dict
from app.services.github import (
    GitHubAPI,
    create_oauth_state,
    decrypt_token,
    encrypt_token,
    exchange_code_for_token,
    get_oauth_authorize_url,
    resolve_github_config,
    revoke_token,
    validate_oauth_state,
)
from app.services.workspace_sync import extract_context_from_repo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["github"])


def _require_token(conn: GitHubConnection) -> str:
    """Decrypt a connection's access token or raise 500."""
    token = decrypt_token(conn.access_token_encrypted)
    if not token:
        raise HTTPException(status_code=500, detail="Failed to decrypt access token")
    return token


# --- Request / Response Models ---

class LinkRepoRequest(BaseModel):
    project_id: str
    repo_full_name: str


class LinkRepoResponse(BaseModel):
    id: str
    project_id: str
    repo_full_name: str
    repo_url: str
    default_branch: str
    sync_status: str


class SaveGitHubConfigRequest(BaseModel):
    client_id: str
    client_secret: str


# --- OAuth Config Endpoints ---

def _client_id_hint(client_id: str) -> str:
    """Mask a client_id to a hint: first 4 + '****' + last 4 chars."""
    if len(client_id) <= 8:
        return client_id[:2] + "****"
    return client_id[:4] + "****" + client_id[-4:]


@router.get("/api/github/config")
async def get_github_config(db: AsyncSession = Depends(get_db_readonly)):
    """Check whether GitHub OAuth credentials are configured.

    Returns configured status and a masked hint of the client_id.
    Never returns the client_secret.
    """
    repo = WorkspaceRepository(db)
    cfg = await repo.get_oauth_config()

    if cfg:
        return {
            "configured": True,
            "client_id_hint": _client_id_hint(cfg.client_id),
            "source": "database",
        }

    if config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET:
        return {
            "configured": True,
            "client_id_hint": _client_id_hint(config.GITHUB_CLIENT_ID),
            "source": "environment",
        }

    return {"configured": False, "client_id_hint": "", "source": None}


@router.put("/api/github/config")
async def save_github_config(
    request: SaveGitHubConfigRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save GitHub OAuth App credentials (encrypted at rest).

    Validates format and stores client_secret Fernet-encrypted.
    Never echoes the secret back.
    """
    client_id = request.client_id.strip()
    client_secret = request.client_secret.strip()

    if not client_id:
        raise HTTPException(status_code=400, detail="Client ID must not be empty")
    if not client_secret:
        raise HTTPException(status_code=400, detail="Client secret must not be empty")
    if not re.match(r'^[A-Za-z0-9._-]+$', client_id):
        raise HTTPException(status_code=400, detail="Client ID contains invalid characters")

    repo = WorkspaceRepository(db)
    await repo.upsert_oauth_config(
        client_id=client_id,
        client_secret_encrypted=encrypt_token(client_secret),
    )

    return {"configured": True}


@router.delete("/api/github/config")
async def delete_github_config(db: AsyncSession = Depends(get_db)):
    """Remove stored GitHub OAuth credentials.

    Falls back to env vars if set.
    """
    repo = WorkspaceRepository(db)
    deleted = await repo.delete_oauth_config()
    if not deleted:
        raise HTTPException(status_code=404, detail="No stored GitHub OAuth config found")
    return {"status": "deleted"}


# --- OAuth Endpoints ---

@router.get("/api/github/authorize")
async def github_authorize(db: AsyncSession = Depends(get_db_readonly)):
    """Returns the GitHub OAuth authorization URL.

    Resolves credentials from DB first, then env vars.
    Frontend redirects the user to this URL to start the OAuth flow.
    """
    gh_config = await resolve_github_config(db)
    if not gh_config:
        raise HTTPException(
            status_code=501,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.",
        )

    client_id, _secret, redirect_uri, scope = gh_config
    state = create_oauth_state()
    auth_data = get_oauth_authorize_url(client_id, redirect_uri, scope, state)
    return {"url": auth_data["url"], "state": auth_data["state"]}


@router.get("/api/github/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """OAuth callback — validates CSRF state, exchanges code for token, stores connection.

    Redirects to frontend with status parameter.
    """
    # Validate CSRF state token
    if not validate_oauth_state(state):
        return RedirectResponse(
            f"{config.FRONTEND_URL}/github/callback?status=error&error=invalid_state"
        )

    # Resolve GitHub OAuth config (DB > env)
    gh_config = await resolve_github_config(db)
    if not gh_config:
        return RedirectResponse(
            f"{config.FRONTEND_URL}/github/callback?status=error&error=not_configured"
        )

    client_id, client_secret, redirect_uri, _scope = gh_config

    try:
        token_data = await exchange_code_for_token(code, client_id, client_secret, redirect_uri)
    except Exception as exc:
        logger.error("GitHub OAuth token exchange failed: %s", type(exc).__name__)
        return RedirectResponse(
            f"{config.FRONTEND_URL}/github/callback?status=error&error=token_exchange_failed"
        )

    access_token = token_data["access_token"]

    # Fetch user info
    try:
        api = GitHubAPI(access_token)
        user = await api.get_user()
    except Exception as exc:
        logger.error("GitHub user fetch failed: %s", type(exc).__name__)
        return RedirectResponse(
            f"{config.FRONTEND_URL}/github/callback?status=error&error=user_fetch_failed"
        )

    # Store encrypted connection
    repo = WorkspaceRepository(db)
    await repo.upsert_connection(
        github_user_id=str(user["id"]),
        github_username=user["login"],
        access_token_encrypted=encrypt_token(access_token),
        avatar_url=user.get("avatar_url"),
        scopes=token_data.get("scope"),
    )

    return RedirectResponse(
        f"{config.FRONTEND_URL}/github/callback?status=connected"
    )


@router.get("/api/github/status")
async def github_status(db: AsyncSession = Depends(get_db_readonly)):
    """Check GitHub connection status."""
    repo = WorkspaceRepository(db)
    conn = await repo.get_connection()

    if not conn:
        return {"connected": False}

    return {
        "connected": True,
        "username": conn.github_username,
        "avatar_url": conn.avatar_url,
        "scopes": conn.scopes,
        "token_valid": conn.token_valid,
        "connected_at": conn.created_at.isoformat(),
    }


@router.delete("/api/github/disconnect")
async def github_disconnect(db: AsyncSession = Depends(get_db)):
    """Disconnect GitHub — revoke token and delete connection."""
    repo = WorkspaceRepository(db)
    conn = await repo.get_connection()

    if not conn:
        raise HTTPException(status_code=404, detail="No GitHub connection found")

    # Attempt token revocation (best effort) — resolve config for app credentials
    token = decrypt_token(conn.access_token_encrypted)
    if token:
        gh_config = await resolve_github_config(db)
        if gh_config:
            await revoke_token(token, client_id=gh_config[0], client_secret=gh_config[1])

    await repo.delete_connection(conn.id)
    return {"status": "disconnected"}


@router.get("/api/github/repos")
async def github_repos(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db_readonly),
):
    """List repos from the connected GitHub account."""
    repo = WorkspaceRepository(db)
    conn = await repo.get_connection()

    if not conn or not conn.token_valid:
        raise HTTPException(status_code=401, detail="No valid GitHub connection")

    token = _require_token(conn)

    try:
        api = GitHubAPI(token)
        repos = await api.list_repos(per_page=per_page, page=page)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            await repo.mark_token_invalid(conn.id)
            raise HTTPException(status_code=401, detail="GitHub token expired")
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}")

    return [
        {
            "full_name": r["full_name"],
            "name": r["name"],
            "description": r.get("description"),
            "language": r.get("language"),
            "default_branch": r.get("default_branch", "main"),
            "html_url": r["html_url"],
            "private": r["private"],
            "updated_at": r.get("updated_at"),
        }
        for r in repos
    ]


# --- Workspace Link Endpoints ---

@router.post("/api/workspace/link")
async def link_repo(
    request: LinkRepoRequest,
    db: AsyncSession = Depends(get_db),
):
    """Link a GitHub repo to a project and trigger initial sync."""
    ws_repo = WorkspaceRepository(db)

    # Check for existing link
    existing = await ws_repo.get_link_by_project_id(request.project_id)
    if existing:
        raise HTTPException(
            status_code=409, detail="Project already has a workspace link"
        )

    # Get GitHub connection for repo metadata
    conn = await ws_repo.get_connection()
    if not conn or not conn.token_valid:
        raise HTTPException(status_code=401, detail="No valid GitHub connection")

    token = _require_token(conn)

    # Fetch repo metadata
    parts = request.repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid repo name format (expected owner/repo)",
        )

    owner, repo_name = parts
    try:
        api = GitHubAPI(token)
        repo_data = await api.get_repo(owner, repo_name)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch repo: {exc}")

    # Create workspace link
    link = await ws_repo.create_link(
        project_id=request.project_id,
        repo_full_name=request.repo_full_name,
        repo_url=repo_data.get("html_url", f"https://github.com/{request.repo_full_name}"),
        default_branch=repo_data.get("default_branch", "main"),
        github_connection_id=conn.id,
    )

    # Trigger initial sync (inline, not background — keeps it simple)
    try:
        await _sync_workspace_link(api, link, repo_data, ws_repo)
    except Exception as exc:
        logger.error("Initial workspace sync failed for %s: %s", link.id, exc)
        await ws_repo.update_sync_status(link, "error", error=str(exc))

    return {
        "id": link.id,
        "project_id": link.project_id,
        "repo_full_name": link.repo_full_name,
        "repo_url": link.repo_url,
        "default_branch": link.default_branch,
        "sync_status": link.sync_status,
    }


@router.delete("/api/workspace/{link_id}")
async def unlink_workspace(
    link_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Unlink a workspace from its project."""
    ws_repo = WorkspaceRepository(db)
    deleted = await ws_repo.delete_link(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace link not found")
    return {"status": "unlinked"}


@router.post("/api/workspace/{link_id}/sync")
async def sync_workspace(
    link_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a re-sync of workspace context."""
    ws_repo = WorkspaceRepository(db)
    link = await ws_repo.get_link_by_id(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Workspace link not found")

    # Get GitHub connection
    conn = await ws_repo.get_connection()
    if not conn or not conn.token_valid:
        raise HTTPException(status_code=401, detail="No valid GitHub connection")

    token = _require_token(conn)

    parts = link.repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid repo name on link")

    owner, repo_name = parts
    api = GitHubAPI(token)

    try:
        repo_data = await api.get_repo(owner, repo_name)
        await _sync_workspace_link(api, link, repo_data, ws_repo)
    except Exception as exc:
        logger.error("Workspace sync failed for %s: %s", link_id, exc)
        await ws_repo.update_sync_status(link, "error", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Sync failed: {exc}")

    return {
        "id": link.id,
        "sync_status": link.sync_status,
        "last_synced_at": link.last_synced_at.isoformat() if link.last_synced_at else None,
    }


@router.get("/api/workspace/status")
async def workspace_status(db: AsyncSession = Depends(get_db_readonly)):
    """Get all workspace link statuses."""
    ws_repo = WorkspaceRepository(db)
    return await ws_repo.get_all_workspace_statuses()


# --- Internal Sync Logic ---

async def _sync_workspace_link(
    api: GitHubAPI,
    link: WorkspaceLink,
    repo_data: dict,
    ws_repo: WorkspaceRepository,
) -> None:
    """Perform the actual workspace sync — fetch tree + marker files, extract context."""
    await ws_repo.update_sync_status(link, "syncing")

    owner, repo_name = link.repo_full_name.split("/")
    branch = repo_data.get("default_branch", link.default_branch)

    # Fetch file tree
    try:
        tree_items = await api.get_file_tree(owner, repo_name, branch)
    except Exception as exc:
        logger.warning("Failed to fetch file tree for %s: %s", link.repo_full_name, exc)
        tree_items = []

    file_paths = [item["path"] for item in tree_items if item.get("type") == "blob"]

    # Fetch key marker files
    marker_files = [
        "package.json", "pyproject.toml", "requirements.txt",
        "go.mod", "Cargo.toml", "Gemfile", "composer.json",
        "tsconfig.json",
    ]
    file_contents: dict[str, str] = {}
    for marker in marker_files:
        if marker in file_paths or any(f.endswith(f"/{marker}") for f in file_paths):
            content = await api.get_file_content(owner, repo_name, marker)
            if content:
                file_contents[marker] = content

    # Extract context
    context = extract_context_from_repo(
        repo_metadata=repo_data,
        file_tree=file_paths,
        file_contents=file_contents,
    )

    ctx_dict = context_to_dict(context)

    # Extract dependencies snapshot
    deps: dict = {}
    if "package.json" in file_contents:
        try:
            pkg = json.loads(file_contents["package.json"])
            deps.update(pkg.get("dependencies", {}))
        except json.JSONDecodeError:
            pass

    await ws_repo.update_sync_status(
        link,
        "synced",
        workspace_context=ctx_dict,
        dependencies_snapshot=deps or None,
        file_tree_snapshot=file_paths[:500],  # Cap stored paths
    )
