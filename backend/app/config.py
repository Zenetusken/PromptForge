"""Application configuration settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Base directory is the project root (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'promptforge.db'}",
)

# Frontend
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5199")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("BACKEND_PORT", "8000"))
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

# Application
APP_VERSION = "0.2.0"
APP_TITLE = "PromptForge API"
APP_DESCRIPTION = "AI-powered prompt optimization pipeline"

# Security
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")  # empty = auth disabled
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")  # empty = MCP auth disabled
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
RATE_LIMIT_OPTIMIZE_RPM = int(os.getenv("RATE_LIMIT_OPTIMIZE_RPM", "10"))

# MCP Server
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")

# Backend host (used by MCP server to reach the backend webhook in Docker)
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")  # auto-detect when empty
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# GitHub OAuth
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv(
    "GITHUB_REDIRECT_URI", "http://localhost:8000/api/apps/promptforge/github/callback"
)
GITHUB_SCOPE = os.getenv("GITHUB_SCOPE", "repo")

# Encryption (Fernet symmetric key for token storage)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")


def _data_dir_from_db_url() -> Path:
    """Derive the data directory from DATABASE_URL (works in both local and Docker)."""
    if ":///" in DATABASE_URL:
        return Path(DATABASE_URL.split(":///", 1)[1]).parent
    return BASE_DIR / "data"


def _resolve_webhook_secret() -> str:
    """Resolve the internal webhook secret.

    Priority: env var > file > auto-generate.
    Parallels the ENCRYPTION_KEY auto-generation pattern.
    Falls back to an ephemeral in-memory secret when the filesystem is
    read-only (e.g. Docker containers without a data volume).
    """
    secret = os.getenv("INTERNAL_WEBHOOK_SECRET", "")
    if secret:
        return secret
    secret_file = _data_dir_from_db_url() / ".webhook_secret"
    try:
        if secret_file.exists():
            return secret_file.read_text().strip()
    except OSError:
        pass
    # Auto-generate and try to persist
    import secrets as _secrets

    secret = _secrets.token_hex(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(secret)
        os.chmod(secret_file, 0o600)
    except OSError:
        pass  # read-only FS — secret lives only in memory for this process
    return secret


INTERNAL_WEBHOOK_SECRET = _resolve_webhook_secret()
