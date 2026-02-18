"""Claude CLI provider — uses claude-agent-sdk subprocess (MAX subscription auth).

Migrated from claude-code-sdk v0.0.25 to claude-agent-sdk v0.1.37.
Key change: system_prompt is now ONLY the custom prompt — Claude Code's
built-in system prompt is no longer injected, eliminating ~30K tokens of
overhead per call that was causing rate-limit exhaustion on MAX subscriptions.
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field

from app import config
from app.providers.base import LLMProvider, classify_error, which_claude_cached
from app.providers.errors import ProviderError, RateLimitError

logger = logging.getLogger(__name__)

# Isolated working directory so the CLI subprocess doesn't detect a project
# context (git repo, CLAUDE.md, etc.) from the backend's CWD. Without this,
# the model responds as a coding agent instead of returning JSON.
_ISOLATED_CWD = tempfile.gettempdir()


def _get_sdk_env() -> dict[str, str]:
    """Return env overrides that allow the SDK to run in a nested context.

    The Claude CLI refuses to start inside an existing Claude Code session
    (detected via the CLAUDECODE env var). Since PromptForge's backend may
    run inside a Claude Code agent, we override that variable with an empty
    string so the SDK subprocess can start cleanly. The SDK merges
    {**os.environ, **options.env}, so our override takes precedence.
    """
    return {
        "CLAUDECODE": "",
        "CLAUDE_CODE_DISABLE_NONINTERACTIVE_TIPS": "1",
    }


def _format_reset_time(resets_at: int) -> str:
    """Format a Unix timestamp as a human-readable relative time."""
    remaining = resets_at - int(time.time())
    if remaining <= 0:
        return "now"
    if remaining < 60:
        return f"{remaining}s"
    minutes = remaining // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m" if mins else f"{hours}h"


def _handle_rate_limit_event(exc: Exception) -> RateLimitError:
    """Extract rate limit info from a MessageParseError containing rate_limit_event data.

    The Claude Code SDK (older versions) doesn't recognize the ``rate_limit_event``
    message type and throws ``MessageParseError``.  We extract the structured
    ``rate_limit_info`` from the exception's ``data`` attribute and surface a
    clear, actionable error.
    """
    data = getattr(exc, "data", {}) or {}
    info = data.get("rate_limit_info", {})
    resets_at = info.get("resetsAt")
    limit_type = info.get("rateLimitType", "")
    retry_after: float | None = None

    if resets_at:
        retry_after = max(0.0, resets_at - time.time())
        reset_str = _format_reset_time(resets_at)
        msg = f"Claude MAX rate limit reached ({limit_type or 'unknown'}), resets in {reset_str}"
    else:
        msg = "Claude MAX rate limit reached"

    logger.warning("Rate limit from CLI: %s (retry_after=%.0fs)", msg, retry_after or 0)
    return RateLimitError(msg, provider="Claude CLI", original=exc, retry_after=retry_after)


@dataclass
class ClaudeCLIProvider(LLMProvider):
    """LLM provider using the Claude Code CLI subprocess.

    No API key required — authenticates via MAX subscription.
    Uses claude-agent-sdk which sends ONLY our custom system prompt
    (no Claude Code built-in system prompt overhead).
    """

    model: str = field(default_factory=lambda: config.CLAUDE_MODEL)

    async def send_message(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Send a message to Claude via the CLI SDK and return the text response."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            query,
        )

        try:
            options = ClaudeAgentOptions(
                system_prompt=system_prompt,
                max_turns=1,
                model=self.model,
                cwd=_ISOLATED_CWD,
                env=_get_sdk_env(),
                tools=[],  # Strip ALL built-in tools — pure text completion only
            )

            response_text = ""
            async for msg in query(prompt=user_message, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text

            return response_text
        except ProviderError:
            raise
        except Exception as exc:
            # The SDK throws MessageParseError for rate_limit_event messages
            # it doesn't recognize. Extract structured info before falling
            # back to generic classify_error.
            if "rate_limit_event" in str(exc):
                raise _handle_rate_limit_event(exc) from exc
            raise classify_error(exc, provider=self.provider_name) from exc

    def is_available(self) -> bool:
        """Check if the Claude CLI is available on PATH (cached)."""
        return which_claude_cached()

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "Claude CLI"
