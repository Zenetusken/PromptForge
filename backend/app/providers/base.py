"""Abstract base class for LLM providers with shared JSON extraction logic."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from app.providers.errors import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderError,
    ProviderPermissionError,
    RateLimitError,
)
from app.providers.types import CompletionRequest, CompletionResponse, StreamChunk

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# ---------------------------------------------------------------------------
# shutil.which("claude") cache — avoids repeated PATH scans (120s TTL).
# Lives here rather than in __init__.py so claude_cli.py can use it without
# a circular import.
# ---------------------------------------------------------------------------
_which_cache: tuple[bool, float] | None = None
_WHICH_TTL = 120.0


def which_claude_cached() -> bool:
    """Return whether ``claude`` is on PATH, with 120-second caching."""
    global _which_cache  # noqa: PLW0603
    now = time.monotonic()
    if _which_cache is not None and now - _which_cache[1] < _WHICH_TTL:
        return _which_cache[0]
    result = shutil.which("claude") is not None
    _which_cache = (result, now)
    return result


def invalidate_which_cache() -> None:
    """Clear the cached ``shutil.which("claude")`` result."""
    global _which_cache  # noqa: PLW0603
    _which_cache = None


def _extract_first_json_object(text: str) -> str | None:
    """Extract the first balanced JSON object from *text*.

    Counts brace depth while skipping characters inside JSON string literals,
    so embedded braces in string values don't break extraction.  Returns None
    if no balanced object is found.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


# ---------------------------------------------------------------------------
# Retry helper for transient errors
# ---------------------------------------------------------------------------


async def _retry_transient(
    fn: Callable[[], Awaitable[_T]],
    *,
    max_retries: int = 2,
    base_delay: float = 1.0,
    rate_limit_base_delay: float = 10.0,
) -> _T:
    """Retry *fn* on rate-limit or connection errors with exponential backoff.

    Non-transient errors (auth, model-not-found, etc.) are raised immediately.
    Rate limits with a known ``retry_after`` exceeding 90 seconds are treated
    as non-retriable (e.g. a 5-hour MAX subscription window).
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except RateLimitError as exc:
            last_exc = exc
            # If the provider tells us the limit resets far in the future,
            # there's no point retrying — fail fast with the original message.
            if exc.retry_after is not None and exc.retry_after > 90:
                logger.warning(
                    "Rate limit with long retry_after (%.0fs), failing immediately: %s",
                    exc.retry_after, exc,
                )
                raise
            if attempt < max_retries:
                delay = min(rate_limit_base_delay * (2**attempt), 60)
                logger.warning(
                    "Rate limit hit (attempt %d/%d), retrying in %.0fs: %s",
                    attempt + 1, max_retries + 1, delay, exc,
                )
                await asyncio.sleep(delay)
        except ProviderConnectionError as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = min(base_delay * (2**attempt), 8)
                logger.warning(
                    "Connection error (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, max_retries + 1, delay, exc,
                )
                await asyncio.sleep(delay)

    assert last_exc is not None
    # Enrich the error message with retry context
    attempts = max_retries + 1
    if isinstance(last_exc, RateLimitError):
        raise RateLimitError(
            f"Rate limit exceeded after {attempts} attempts — try again in a minute",
            provider=last_exc.provider,
            original=last_exc.original,
            retry_after=last_exc.retry_after,
        ) from last_exc
    raise last_exc


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


def classify_error(exc: Exception, *, provider: str = "") -> ProviderError:
    """Convert a raw SDK exception into a typed ``ProviderError`` subclass.

    Uses the same pattern matching as the legacy ``friendly_error()`` but
    returns a structured exception instead of a plain string.
    """
    if isinstance(exc, ProviderError):
        return exc

    msg = str(exc).lower()
    if "authentication" in msg or "api key" in msg or "unauthorized" in msg or "401" in msg:
        return AuthenticationError(
            "Invalid API key", provider=provider, original=exc,
        )
    if "permission" in msg or "403" in msg:
        return ProviderPermissionError(
            "API key lacks required permissions", provider=provider, original=exc,
        )
    if "rate" in msg and "limit" in msg:
        return RateLimitError(
            "Rate limit exceeded", provider=provider, original=exc,
        )
    if "not found" in msg or "404" in msg:
        return ModelNotFoundError(
            "Model not found \u2014 check model name", provider=provider, original=exc,
        )
    if "timeout" in msg or "timed out" in msg or isinstance(exc, (TimeoutError, ConnectionError)):
        return ProviderConnectionError(
            str(exc)[:200], provider=provider, original=exc,
        )
    # Generic fallback
    text = str(exc)
    return ProviderError(
        text[:200] if len(text) > 200 else text,
        provider=provider,
        original=exc,
    )


def friendly_error(exc: Exception) -> str:
    """Convert common SDK exceptions into user-friendly messages.

    Thin wrapper around ``classify_error`` for backward compatibility.
    """
    return str(classify_error(exc))


# ---------------------------------------------------------------------------
# Shared JSON extraction (used by complete_json; send_message_json retained for compat)
# ---------------------------------------------------------------------------


def _parse_json(text: str) -> dict:
    """Parse LLM response text as JSON using a 4-strategy fallback.

    1. Direct parse of the full text
    2. Extract from ``\\`\\`\\`json ... \\`\\`\\`` code fence
    3. Extract from ``\\`\\`\\` ... \\`\\`\\`` code fence
    4. Find the first balanced ``{ ... }`` via brace counting
    """
    cleaned = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: ```json ... ``` code fence
    json_fence = re.search(r"```json\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if json_fence:
        try:
            return json.loads(json_fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: ``` ... ``` code fence
    fence = re.search(r"```\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 4: First balanced JSON object via brace counting
    json_obj = _extract_first_json_object(cleaned)
    if json_obj is not None:
        try:
            return json.loads(json_obj)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Failed to parse LLM response as JSON.\nRaw response: {text[:500]}"
    )


async def run_connection_test(
    fn: Callable[[], Awaitable[object]],
    timeout: float = 10.0,
) -> tuple[bool, str | None]:
    """Run an async callable with timeout and return ``(ok, error)``.

    Shared helper that eliminates duplicated try/except/timeout logic
    in per-provider ``test_connection`` overrides.
    """
    try:
        await asyncio.wait_for(fn(), timeout=timeout)
        return (True, None)
    except TimeoutError:
        return (False, "Connection timed out")
    except ProviderError as exc:
        return (False, str(exc))
    except Exception as exc:
        return (False, friendly_error(exc))


class LLMProvider(ABC):
    """Abstract base for all LLM providers.

    Subclasses implement ``send_message`` and availability checks.
    JSON extraction (``send_message_json``) is provider-independent and
    lives here as a concrete method.
    """

    @abstractmethod
    async def send_message(self, system_prompt: str, user_message: str) -> str:
        """Send a message and return the raw text response."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is ready to serve requests."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The model identifier in use (e.g. ``claude-opus-4-6``)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. ``Claude CLI``)."""

    # ------------------------------------------------------------------
    # Concrete — test_connection
    # ------------------------------------------------------------------

    async def test_connection(self, timeout: float = 10.0) -> tuple[bool, str | None]:
        """Test that the provider can actually serve requests.

        Returns ``(True, None)`` on success, or ``(False, error_message)``
        on failure.  The default implementation sends a trivial prompt
        wrapped in an ``asyncio.wait_for`` timeout.  API providers override
        with minimal-token calls.
        """
        return await run_connection_test(
            lambda: self.send_message("Respond with OK", "ping"),
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Concrete — shared JSON extraction
    # ------------------------------------------------------------------

    async def send_message_json(
        self,
        system_prompt: str,
        user_message: str,
    ) -> dict:
        """Send a message and parse the response as JSON.

        Uses a 4-strategy fallback:
        1. Direct parse of the full response text
        2. Extract from ``\\`\\`\\`json ... \\`\\`\\`` code fence
        3. Extract from ``\\`\\`\\` ... \\`\\`\\`` code fence
        4. Find the first balanced ``{ ... }`` via brace counting
        """
        text = await self.send_message(system_prompt, user_message)
        return _parse_json(text)

    # ------------------------------------------------------------------
    # Concrete — unified completion API
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a completion using the unified request/response model.

        The default implementation delegates to ``send_message()``.
        Concrete providers may override to populate ``TokenUsage``.
        """
        text = await self.send_message(request.system_prompt, request.user_message)
        return CompletionResponse(
            text=text,
            model=self.model_name,
            provider=self.provider_name,
        )

    async def complete_json(
        self, request: CompletionRequest,
    ) -> tuple[dict, CompletionResponse]:
        """Execute a completion and parse the response as JSON.

        Returns ``(parsed_dict, response)`` so callers get both the
        structured data and the full ``CompletionResponse`` metadata.

        Retries up to 2 times on rate-limit or connection errors with
        exponential backoff.
        """

        async def _attempt() -> tuple[dict, CompletionResponse]:
            response = await self.complete(request)
            parsed = _parse_json(response.text)
            return parsed, response

        return await _retry_transient(_attempt)

    # ------------------------------------------------------------------
    # Concrete — streaming
    # ------------------------------------------------------------------

    def supports_streaming(self) -> bool:
        """Return True if this provider supports the ``stream()`` method natively."""
        return False

    async def stream(
        self, request: CompletionRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Yield text chunks as they arrive from the LLM.

        The default implementation calls ``complete()`` and yields a single
        ``StreamChunk``.  Providers with native streaming override this.
        """
        response = await self.complete(request)
        yield StreamChunk(text=response.text, done=True, usage=response.usage)

    # ------------------------------------------------------------------
    # Concrete — token counting
    # ------------------------------------------------------------------

    def count_tokens(self, text: str) -> int | None:
        """Estimate token count for *text*.

        Returns ``None`` if the provider does not support token counting.
        """
        return None

    # ------------------------------------------------------------------
    # Concrete — capability check
    # ------------------------------------------------------------------

    def supports(self, capability: str) -> bool:
        """Check whether the current model supports a given capability.

        Looks up the model in ``MODEL_CATALOG``. Returns ``False`` if
        the model is not found in the catalog.
        """
        from app.providers.models import MODEL_CATALOG

        # Search all provider entries (the provider may be registered
        # under a different name than its provider_name).
        for models in MODEL_CATALOG.values():
            for info in models:
                if info.id == self.model_name:
                    return capability in info.capabilities
        return False
