"""Application configuration via pydantic-settings."""

import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Provider ---
    ANTHROPIC_API_KEY: str = ""

    # --- GitHub OAuth ---
    GITHUB_OAUTH_CLIENT_ID: str = ""
    GITHUB_OAUTH_CLIENT_SECRET: str = ""

    # --- Security ---
    SECRET_KEY: str = ""

    # --- Embedding ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- Rate Limiting ---
    OPTIMIZE_RATE_LIMIT: str = "10/minute"
    REFINE_RATE_LIMIT: str = "10/minute"
    FEEDBACK_RATE_LIMIT: str = "30/minute"
    DEFAULT_RATE_LIMIT: str = "60/minute"

    # --- Passthrough ---
    BIAS_CORRECTION_FACTOR: float = 0.85

    # --- Context Budget ---
    MAX_CONTEXT_TOKENS: int = 80000
    MAX_RAW_PROMPT_CHARS: int = 200000
    MAX_GUIDANCE_CHARS: int = 20000
    MAX_CODEBASE_CONTEXT_CHARS: int = 100000
    MAX_ADAPTATION_CHARS: int = 5000
    EXPLORE_MAX_PROMPT_CHARS: int = 20000
    EXPLORE_MAX_CONTEXT_CHARS: int = 700000
    EXPLORE_MAX_FILES: int = 40
    EXPLORE_TOTAL_LINE_BUDGET: int = 15000

    # --- Network ---
    TRUSTED_PROXIES: str = "127.0.0.1"
    FRONTEND_URL: str = "http://localhost:5199"

    # --- Traces ---
    TRACE_RETENTION_DAYS: int = 30

    # --- Database ---
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'synthesis.db'}"

    def resolve_secret_key(self) -> str:
        """Auto-generate SECRET_KEY if not set, persist to data/.app_secrets."""
        if self.SECRET_KEY:
            return self.SECRET_KEY
        secrets_file = DATA_DIR / ".app_secrets"
        if secrets_file.exists():
            return secrets_file.read_text().strip()
        key = secrets.token_urlsafe(64)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text(key)
        secrets_file.chmod(0o600)
        return key


settings = Settings()
