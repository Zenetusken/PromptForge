"""Auth security hardening tests — 11 TDD cycles, RED-first.

Run: cd backend && source .venv/bin/activate && pytest tests/test_auth_security.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.auth import (
    ERR_TOKEN_EXPIRED,
    ERR_TOKEN_INVALID,
    ERR_TOKEN_MISSING,
    ERR_TOKEN_REVOKED,
)
from app.utils.jwt import sign_access_token, sign_refresh_token
from app.dependencies.auth import get_current_user
