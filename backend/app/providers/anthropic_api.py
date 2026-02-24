"""Anthropic API provider — uses the anthropic Python SDK directly."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from app import config
from app.providers.base import LLMProvider, classify_error, run_connection_test
from app.providers.errors import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderError,
    ProviderPermissionError,
    RateLimitError,
)
from app.providers.types import CompletionRequest, CompletionResponse, StreamChunk, TokenUsage

logger = logging.getLogger(__name__)

_CACHE_CONTROL = {"type": "ephemeral"}


def _classify_anthropic_error(exc: Exception, *, provider: str = "") -> ProviderError:
    """Classify an Anthropic SDK exception using its typed exception hierarchy.

    Falls back to the generic string-matching ``classify_error`` for
    exceptions that don't match any known Anthropic SDK type.
    """
    try:
        import anthropic as _anthropic
    except ImportError:
        return classify_error(exc, provider=provider)

    if isinstance(exc, _anthropic.AuthenticationError):
        return AuthenticationError("Invalid API key", provider=provider, original=exc)
    if isinstance(exc, _anthropic.PermissionDeniedError):
        return ProviderPermissionError(
            "API key lacks required permissions", provider=provider, original=exc,
        )
    if isinstance(exc, _anthropic.RateLimitError):
        retry_after: float | None = None
        if hasattr(exc, "response") and exc.response is not None:
            raw = exc.response.headers.get("retry-after")
            if raw is not None:
                try:
                    retry_after = float(raw)
                except (ValueError, TypeError):
                    pass
        return RateLimitError(
            "Rate limit exceeded", provider=provider, original=exc, retry_after=retry_after,
        )
    if isinstance(exc, _anthropic.NotFoundError):
        return ModelNotFoundError(
            "Model not found — check model name", provider=provider, original=exc,
        )
    if isinstance(exc, (_anthropic.APITimeoutError, _anthropic.APIConnectionError)):
        return ProviderConnectionError(
            str(exc)[:200], provider=provider, original=exc,
        )

    return classify_error(exc, provider=provider)


@dataclass
class AnthropicAPIProvider(LLMProvider):
    """LLM provider using the Anthropic Messages API.

    Requires ``ANTHROPIC_API_KEY`` to be set. Install with::

        pip install promptforge-backend[anthropic]
    """

    model: str = field(default_factory=lambda: config.CLAUDE_MODEL)
    # Read at instantiation time (not import time) so env patches in tests work
    # and runtime key rotation is supported.
    api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    max_tokens: int = 4096
    _client: object = field(default=None, init=False, repr=False)

    def _get_client(self):
        """Return a cached AsyncAnthropic client, creating one on first use."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def send_message(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Send a message via the Anthropic API and return the text response."""
        try:
            client = self._get_client()
            response = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                cache_control=_CACHE_CONTROL,
            )
            return response.content[0].text
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_anthropic_error(exc, provider=self.provider_name) from exc

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def test_connection(self, timeout: float = 10.0) -> tuple[bool, str | None]:
        """Test connectivity with a minimal 1-token request."""

        async def _ping():
            client = self._get_client()
            await client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
                cache_control=_CACHE_CONTROL,
            )

        return await run_connection_test(_ping, timeout=timeout)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a completion with token usage tracking."""
        try:
            client = self._get_client()
            kwargs: dict = {
                "model": self.model,
                "max_tokens": request.max_tokens or self.max_tokens,
                "system": request.system_prompt,
                "messages": [{"role": "user", "content": request.user_message}],
                "cache_control": _CACHE_CONTROL,
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            response = await client.messages.create(**kwargs)
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_creation_input_tokens=getattr(
                    response.usage, "cache_creation_input_tokens", None,
                ),
                cache_read_input_tokens=getattr(
                    response.usage, "cache_read_input_tokens", None,
                ),
            )
            return CompletionResponse(
                text=response.content[0].text,
                model=response.model,
                provider=self.provider_name,
                usage=usage,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_anthropic_error(exc, provider=self.provider_name) from exc

    def supports_streaming(self) -> bool:
        return True

    async def stream(self, request: CompletionRequest):
        """Stream text chunks via the Anthropic Messages API."""
        try:
            client = self._get_client()
            kwargs: dict = {
                "model": self.model,
                "max_tokens": request.max_tokens or self.max_tokens,
                "system": request.system_prompt,
                "messages": [{"role": "user", "content": request.user_message}],
                "cache_control": _CACHE_CONTROL,
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature

            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(text=text)
                # get_final_message() must be called inside the async with block
                msg = await stream.get_final_message()
            usage = TokenUsage(
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens,
                cache_creation_input_tokens=getattr(
                    msg.usage, "cache_creation_input_tokens", None,
                ),
                cache_read_input_tokens=getattr(
                    msg.usage, "cache_read_input_tokens", None,
                ),
            )
            yield StreamChunk(text="", done=True, usage=usage)
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_anthropic_error(exc, provider=self.provider_name) from exc

    async def count_tokens(self, text: str) -> int | None:
        """Count tokens using the Anthropic SDK's count_tokens endpoint.

        Falls back to a ~4 chars/token heuristic if the SDK call fails.
        """
        try:
            client = self._get_client()
            result = await client.messages.count_tokens(
                model=self.model,
                messages=[{"role": "user", "content": text}],
            )
            return result.input_tokens
        except Exception:
            logger.debug("count_tokens SDK call failed, falling back to heuristic")
            try:
                return len(text) // 4
            except Exception:
                return None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "Anthropic API"
