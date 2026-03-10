import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_user
from app.models.auth import User
from app.models.github import GitHubToken, LinkedRepo
from app.schemas.auth import AuthenticatedUser
from app.schemas.github import LinkRepoRequest
from app.services import github_service
from app.services.cache_service import get_cache
from app.services.repo_index_service import get_repo_index_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["github-repos"])

_REPO_CACHE_TTL = 300  # 5 minutes


async def evict_repo_cache(session_id: str) -> None:
    """Remove cached repo list for a session (call on logout/disconnect)."""
    cache = get_cache()
    if cache:
        await cache.delete(cache.make_key("repos", session_id))


async def _get_github_token(
    request: Request,
    session: AsyncSession,
    current_user: AuthenticatedUser,
) -> str:
    """Retrieve and decrypt the GitHub token for the current session.

    Cross-validates that the JWT-authenticated user matches the GitHub user
    who stored the token in this session.
    """
    session_id = request.session.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated with GitHub")

    # Fetch the stored token record for this session
    gh_result = await session.execute(
        select(GitHubToken).where(GitHubToken.session_id == session_id)
    )
    gh_record = gh_result.scalar_one_or_none()
    if not gh_record:
        raise HTTPException(status_code=401, detail="No GitHub token found. Connect GitHub first.")

    # Cross-validate: JWT user must match the GitHub user who stored this token
    user_result = await session.execute(
        select(User).where(User.id == current_user.id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or user.github_user_id != gh_record.github_user_id:
        raise HTTPException(
            status_code=403,
            detail="GitHub token does not belong to the authenticated user",
        )

    # Pass gh_record to skip the redundant DB round-trip — it was already fetched above.
    token = await github_service.get_token_for_session(session, session_id, db_token=gh_record)
    if not token:
        raise HTTPException(status_code=401, detail="GitHub token could not be decrypted.")
    return token


@router.get("/api/github/repos")
async def list_repos(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List repositories accessible with the user's GitHub token."""
    token = await _get_github_token(request, session, current_user)

    # Check cache
    cache = get_cache()
    cache_key = cache.make_key("repos", request.session.get("session_id", "")) if cache else None
    if cache:
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    # Fetch from GitHub via service layer
    try:
        repos = await github_service.get_user_repos(token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch repos: {e}")

    if cache:
        await cache.set(cache_key, repos, ttl_seconds=_REPO_CACHE_TTL)
    return repos


@router.get("/api/github/repos/{owner}/{repo}/branches")
async def list_branches(
    owner: str,
    repo: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List branches for a repository (max 50)."""
    token = await _get_github_token(request, session, current_user)
    branches = await github_service.get_repo_branches(token, f"{owner}/{repo}")
    return branches


@router.post("/api/github/repos/link")
async def link_repo(
    body: LinkRepoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Link a GitHub repository for codebase-aware optimization."""
    token = await _get_github_token(request, session, current_user)
    session_id = request.session.get("session_id", "")

    # Validate repo access via service layer
    repo_data = await github_service.get_repo_info(token, body.full_name)
    if repo_data is None:
        raise HTTPException(status_code=404, detail="Repository not found or not accessible")

    branch = body.branch or repo_data.get("default_branch", "main")

    # Remove any existing linked repo for this session
    await session.execute(
        delete(LinkedRepo).where(LinkedRepo.session_id == session_id)
    )

    linked = LinkedRepo(
        session_id=session_id,
        full_name=body.full_name,
        branch=branch,
        default_branch=repo_data.get("default_branch"),
        language=repo_data.get("language"),
    )
    session.add(linked)
    await session.commit()

    # Trigger background embedding index build for the linked repo.
    # This runs asynchronously — the response returns immediately.
    try:
        index_svc = get_repo_index_service()
        asyncio.create_task(
            index_svc.build_index(token, body.full_name, branch)
        )
        logger.info("Background index build triggered for %s@%s", body.full_name, branch)
    except Exception as e:
        logger.warning("Failed to trigger background indexing: %s", e)

    return {
        "id": linked.id,
        "full_name": linked.full_name,
        "branch": linked.branch,
        "default_branch": linked.default_branch,
        "language": linked.language,
    }


@router.get("/api/github/repos/linked")
async def get_linked_repo(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get the currently linked repository for this session."""
    session_id = request.session.get("session_id")
    if not session_id:
        return None

    result = await session.execute(
        select(LinkedRepo).where(LinkedRepo.session_id == session_id)
    )
    linked = result.scalar_one_or_none()
    if not linked:
        return None

    return {
        "id": linked.id,
        "full_name": linked.full_name,
        "branch": linked.branch,
        "default_branch": linked.default_branch,
        "language": linked.language,
        "linked_at": linked.linked_at.isoformat() if linked.linked_at else None,
    }


@router.post("/api/github/repos/{owner}/{repo}/reindex")
async def reindex_repo(
    owner: str,
    repo: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Manually trigger re-indexing of a repository's embedding index.

    Invalidates the existing index and rebuilds from scratch.
    """
    token = await _get_github_token(request, session, current_user)
    full_name = f"{owner}/{repo}"

    # Look up the linked repo to get branch
    session_id = request.session.get("session_id", "")
    result = await session.execute(
        select(LinkedRepo).where(
            LinkedRepo.session_id == session_id,
            LinkedRepo.full_name == full_name,
        )
    )
    linked = result.scalar_one_or_none()
    branch = linked.branch if linked else "main"

    index_svc = get_repo_index_service()
    await index_svc.invalidate_index(full_name, branch)
    asyncio.create_task(index_svc.build_index(token, full_name, branch))

    return {"status": "reindexing", "repo": full_name, "branch": branch}


@router.delete("/api/github/repos/unlink")
async def unlink_repo(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Unlink the currently linked repository."""
    session_id = request.session.get("session_id")
    if not session_id:
        return {"unlinked": False, "reason": "No session"}

    await session.execute(
        delete(LinkedRepo).where(LinkedRepo.session_id == session_id)
    )
    await session.commit()

    return {"unlinked": True}
