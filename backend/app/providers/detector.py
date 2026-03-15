"""Provider auto-detection: CLI first, then API key, then None."""

from __future__ import annotations

import shutil

from app.config import settings
from app.providers.base import LLMProvider


def detect_provider() -> LLMProvider | None:
    """Return the best available LLM provider, or None if none is configured.

    Detection order:
    1. claude CLI on PATH → ClaudeCLIProvider (Max subscription, zero marginal cost)
    2. ANTHROPIC_API_KEY set → AnthropicAPIProvider
    3. Neither available → None
    """
    if shutil.which("claude"):
        from app.providers.claude_cli import ClaudeCLIProvider

        return ClaudeCLIProvider()

    if settings.ANTHROPIC_API_KEY:
        from app.providers.anthropic_api import AnthropicAPIProvider

        return AnthropicAPIProvider(api_key=settings.ANTHROPIC_API_KEY)

    return None
