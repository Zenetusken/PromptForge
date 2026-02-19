"""Anthropic API provider — uses the anthropic Python SDK directly."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app import config
from app.providers.base import LLMProvider, classify_error, run_connection_test
from app.providers.errors import ProviderError
from app.providers.types import CompletionRequest, CompletionResponse, StreamChunk, TokenUsage


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
            )
            return response.content[0].text
        except ProviderError:
            raise
        except Exception as exc:
            raise classify_error(exc, provider=self.provider_name) from exc

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
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            response = await client.messages.create(**kwargs)
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
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
            raise classify_error(exc, provider=self.provider_name) from exc

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
            )
            yield StreamChunk(text="", done=True, usage=usage)
        except ProviderError:
            raise
        except Exception as exc:
            raise classify_error(exc, provider=self.provider_name) from exc

    def count_tokens(self, text: str) -> int | None:
        """Estimate token count for Anthropic models.

        Uses ~4 chars per token heuristic. The Anthropic SDK's count_tokens()
        is async on AsyncAnthropic and cannot be called from a sync method.
        """
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
