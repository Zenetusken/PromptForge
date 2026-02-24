"""OpenAI API provider — uses the openai Python SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app import config
from app.providers.base import LLMProvider, classify_error, run_connection_test
from app.providers.errors import ProviderError
from app.providers.types import CompletionRequest, CompletionResponse, StreamChunk, TokenUsage


@dataclass
class OpenAIProvider(LLMProvider):
    """LLM provider using the OpenAI Chat Completions API.

    Requires ``OPENAI_API_KEY`` to be set. Install with::

        pip install promptforge-backend[openai]
    """

    model: str = field(default_factory=lambda: config.OPENAI_MODEL)
    # Read at instantiation time (not import time) so env patches in tests work
    # and runtime key rotation is supported.
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    max_tokens: int = 4096
    _client: object = field(default=None, init=False, repr=False)

    def _get_client(self):
        """Return a cached AsyncOpenAI client, creating one on first use."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def send_message(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Send a message via the OpenAI API and return the text response."""
        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            return response.choices[0].message.content or ""
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
            await client.chat.completions.create(
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
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_message},
                ],
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            response = await client.chat.completions.create(**kwargs)
            usage = None
            if response.usage:
                usage = TokenUsage(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                )
            return CompletionResponse(
                text=response.choices[0].message.content or "",
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
        """Stream text chunks via the OpenAI Chat Completions API."""
        try:
            client = self._get_client()
            kwargs: dict = {
                "model": self.model,
                "max_tokens": request.max_tokens or self.max_tokens,
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_message},
                ],
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature

            response = await client.chat.completions.create(**kwargs)
            sent_done = False
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(text=chunk.choices[0].delta.content)
                if chunk.usage:
                    sent_done = True
                    yield StreamChunk(
                        text="",
                        done=True,
                        usage=TokenUsage(
                            input_tokens=chunk.usage.prompt_tokens,
                            output_tokens=chunk.usage.completion_tokens,
                        ),
                    )
            if not sent_done:
                yield StreamChunk(text="", done=True)
        except ProviderError:
            raise
        except Exception as exc:
            raise classify_error(exc, provider=self.provider_name) from exc

    async def count_tokens(self, text: str) -> int | None:
        """Count tokens using tiktoken (if available)."""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(self.model)
            return len(enc.encode(text))
        except Exception:
            return None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "OpenAI"
