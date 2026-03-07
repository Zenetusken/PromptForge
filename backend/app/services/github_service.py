"""GitHub integration service.

Handles token retrieval/decryption, repository tree traversal, and file
content reading. All PyGithub calls are wrapped in anyio.to_thread.run_sync()
to avoid blocking the async event loop.

Token encryption and storage is owned by app.routers.github_auth.
"""

import base64
import logging
import os
from typing import Optional

import anyio
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.github import GitHubToken

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────
# Encryption helpers
# ───────────────────────────────────────────────────────────────────────

_fernet: Optional[Fernet] = None

# File extensions and directories to exclude when browsing repos
EXCLUDED_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".gz", ".tar", ".mp4", ".mp3",
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
    ".wasm", ".rdata", ".pdb", ".map",
})

EXCLUDED_DIRECTORIES = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "vendor",
})

MAX_FILE_SIZE_BYTES = 100 * 1024  # 100 KB


def _get_fernet() -> Fernet:
    """Return a Fernet instance, creating/loading the key as needed."""
    global _fernet
    if _fernet is not None:
        return _fernet

    key = settings.GITHUB_TOKEN_ENCRYPTION_KEY
    if key:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet

    # Auto-generate and persist a key if not configured
    key_path = os.path.join("data", ".github_encryption_key")
    os.makedirs("data", exist_ok=True)
    key_bytes: bytes
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key_bytes = f.read().strip()
    else:
        key_bytes = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key_bytes)
        logger.info("Generated new GitHub token encryption key at %s", key_path)

    _fernet = Fernet(key_bytes)
    return _fernet


def encrypt_token(token: str) -> bytes:
    """Encrypt a GitHub token using Fernet symmetric encryption.

    Args:
        token: The plaintext token string.

    Returns:
        The Fernet-encrypted token bytes.
    """
    return _get_fernet().encrypt(token.encode("utf-8"))


def decrypt_token(encrypted: bytes) -> str:
    """Decrypt a Fernet-encrypted GitHub token.

    Args:
        encrypted: The Fernet-encrypted token bytes.

    Returns:
        The plaintext token string.
    """
    return _get_fernet().decrypt(encrypted).decode("utf-8")


# ───────────────────────────────────────────────────────────────────────
# Token retrieval
# ───────────────────────────────────────────────────────────────────────

async def get_token_for_session(
    session: AsyncSession,
    session_id: str,
) -> Optional[str]:
    """Retrieve and decrypt the GitHub token for a session.

    Args:
        session: Async database session.
        session_id: Browser session identifier.

    Returns:
        Decrypted token string, or None if no token exists.
    """
    result = await session.execute(
        select(GitHubToken).where(GitHubToken.session_id == session_id)
    )
    db_token = result.scalar_one_or_none()
    if db_token is None:
        return None
    try:
        return decrypt_token(bytes(db_token.token_encrypted))
    except Exception as e:
        logger.error("Failed to decrypt token for session %s: %s", session_id, e)
        return None


# ───────────────────────────────────────────────────────────────────────
# GitHub API wrappers (PyGithub, async via anyio)
# ───────────────────────────────────────────────────────────────────────

def _is_excluded(path: str) -> bool:
    """Check if a file path should be excluded from tree results."""
    parts = path.split("/")
    for part in parts[:-1]:
        if part in EXCLUDED_DIRECTORIES:
            return True
    ext_lower = os.path.splitext(path)[1].lower()
    if ext_lower in EXCLUDED_EXTENSIONS:
        return True
    return False


async def validate_pat(token: str) -> Optional[dict]:
    """Validate a GitHub PAT by calling the /user endpoint.

    Args:
        token: The GitHub personal access token to validate.

    Returns:
        Dict with user info if valid, None if invalid.
    """
    def _sync():
        from github import Auth, Github
        g = Github(auth=Auth.Token(token))
        user = g.get_user()
        return {
            "login": user.login,
            "id": user.id,
            "avatar_url": user.avatar_url,
        }

    try:
        return await anyio.to_thread.run_sync(_sync)
    except Exception as e:
        logger.warning("GitHub PAT validation failed: %s", e)
        return None


async def get_user_repos(token: str) -> list[dict]:
    """List repositories accessible by the authenticated user.

    Args:
        token: Decrypted GitHub access token.

    Returns:
        List of repo info dicts.
    """
    def _sync():
        from github import Auth, Github
        g = Github(auth=Auth.Token(token))
        repos = []
        for repo in g.get_user().get_repos(sort="updated"):
            repos.append({
                "full_name": repo.full_name,
                "name": repo.name,
                "private": repo.private,
                "default_branch": repo.default_branch,
                "description": repo.description,
                "language": repo.language,
                "size_kb": repo.size,
            })
            if len(repos) >= 100:
                break
        return repos

    try:
        return await anyio.to_thread.run_sync(_sync)
    except Exception as e:
        logger.error("Failed to list repos: %s", e)
        return []


async def get_repo_tree(
    token: str,
    full_name: str,
    branch: str = "main",
) -> list[dict]:
    """Get the file tree for a repository branch.

    Args:
        token: Decrypted GitHub access token.
        full_name: Repository full name (owner/repo).
        branch: Branch name to read the tree from.

    Returns:
        List of dicts with path, sha, and size_bytes keys.
    """
    def _sync():
        from github import Auth, Github
        g = Github(auth=Auth.Token(token))
        repo = g.get_repo(full_name)
        b = repo.get_branch(branch)
        tree = repo.get_git_tree(b.commit.commit.tree.sha, recursive=True)
        entries = []
        for entry in tree.tree:
            if entry.type != "blob":
                continue
            if _is_excluded(entry.path):
                continue
            if entry.size and entry.size > MAX_FILE_SIZE_BYTES:
                continue
            entries.append({
                "path": entry.path,
                "sha": entry.sha,
                "size_bytes": entry.size or 0,
            })
        return entries

    try:
        return await anyio.to_thread.run_sync(_sync)
    except Exception as e:
        logger.error("Failed to get repo tree for %s@%s: %s", full_name, branch, e)
        return []


async def read_file_content(
    token: str,
    full_name: str,
    file_sha: str,
) -> Optional[str]:
    """Read the content of a single file by its blob SHA.

    Args:
        token: Decrypted GitHub access token.
        full_name: Repository full name (owner/repo).
        file_sha: Git blob SHA of the file.

    Returns:
        File content as a string, or None on failure.
    """
    def _sync():
        from github import Auth, Github
        g = Github(auth=Auth.Token(token))
        repo = g.get_repo(full_name)
        blob = repo.get_git_blob(file_sha)
        if blob.encoding == "base64":
            return base64.b64decode(blob.content).decode("utf-8", errors="replace")
        return blob.content

    try:
        return await anyio.to_thread.run_sync(_sync)
    except Exception as e:
        logger.error("Failed to read file %s from %s: %s", file_sha, full_name, e)
        return None


async def read_file_by_path(
    token: str,
    full_name: str,
    path: str,
    branch: str = "main",
) -> Optional[str]:
    """Read a file's content directly by path (no tree lookup needed).

    Args:
        token: Decrypted GitHub access token.
        full_name: Repository full name (owner/repo).
        path: File path within the repository.
        branch: Branch name to read from.

    Returns:
        File content as a string, or None on failure.
    """
    def _sync():
        from github import Auth, Github
        g = Github(auth=Auth.Token(token))
        repo = g.get_repo(full_name)
        content = repo.get_contents(path, ref=branch)
        if isinstance(content, list):
            raise ValueError(f"'{path}' is a directory, not a file")
        if content.encoding == "base64":
            return base64.b64decode(content.content).decode("utf-8", errors="replace")
        return content.decoded_content.decode("utf-8", errors="replace")

    try:
        return await anyio.to_thread.run_sync(_sync)
    except Exception as e:
        logger.error("Failed to read file '%s' from %s: %s", path, full_name, e)
        return None


async def get_repo_info(token: str, full_name: str) -> Optional[dict]:
    """Get metadata about a repository.

    Args:
        token: Decrypted GitHub access token.
        full_name: Repository full name (owner/repo).

    Returns:
        Dict with repo metadata or None on failure.
    """
    def _sync():
        from github import Auth, Github
        g = Github(auth=Auth.Token(token))
        repo = g.get_repo(full_name)
        return {
            "full_name": repo.full_name,
            "name": repo.name,
            "private": repo.private,
            "default_branch": repo.default_branch,
            "description": repo.description,
            "language": repo.language,
            "size_kb": repo.size,
        }

    try:
        return await anyio.to_thread.run_sync(_sync)
    except Exception as e:
        logger.error("Failed to get repo info for %s: %s", full_name, e)
        return None


async def get_default_branch(token: str, repo_full_name: str) -> str:
    """Return the default branch name for a GitHub repository.

    Args:
        token: Decrypted GitHub access token.
        repo_full_name: Repository full name (owner/repo).

    Returns:
        The default branch name (e.g. "main" or "master").

    Raises:
        Exception: If the repository cannot be reached or the token is invalid.
    """
    def _sync() -> str:
        from github import Auth, Github
        g = Github(auth=Auth.Token(token))
        return g.get_repo(repo_full_name).default_branch

    return await anyio.to_thread.run_sync(_sync)
