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

# Application
APP_VERSION = "0.2.0"
APP_TITLE = "PromptForge API"
APP_DESCRIPTION = "AI-powered prompt optimization pipeline"

# Security
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")  # empty = auth disabled
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
RATE_LIMIT_OPTIMIZE_RPM = int(os.getenv("RATE_LIMIT_OPTIMIZE_RPM", "10"))

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")  # auto-detect when empty
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
