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
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("BACKEND_PORT", "8000"))

# Application
APP_VERSION = "0.1.0"
APP_TITLE = "PromptForge API"
APP_DESCRIPTION = "AI-powered prompt optimization pipeline"

# Claude API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
