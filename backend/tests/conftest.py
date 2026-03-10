"""Shared pytest fixtures for backend tests.

Autouse fixtures applied to ALL tests in this directory.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _bypass_rate_limiter():
    """Disable rate limiting in unit tests.

    Patches the module-level _limiter in rate_limit.py so that every
    call to RateLimit.__call__ sees a limiter that always allows requests.

    Uses MagicMock (not AsyncMock) because the test path always hits the
    synchronous branch (_is_async=False when init_rate_limiter was never
    called).  An AsyncMock.hit() would return a coroutine instead of a
    bool, producing "coroutine was never awaited" RuntimeWarnings.
    """
    mock_limiter = MagicMock()
    mock_limiter.hit.return_value = True

    with patch("app.dependencies.rate_limit._limiter", mock_limiter):
        yield
