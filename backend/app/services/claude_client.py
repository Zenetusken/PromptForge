"""Backward-compatibility wrapper — use app.providers instead.

This module is kept so existing imports continue to work.
New code should use ``from app.providers import get_provider``
or ``from app.providers.claude_cli import ClaudeCLIProvider``.
"""

from app.providers.claude_cli import ClaudeCLIProvider


class ClaudeClient(ClaudeCLIProvider):
    """Deprecated: use ClaudeCLIProvider or get_provider()."""

    pass
