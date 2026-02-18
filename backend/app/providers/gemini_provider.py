"""Google Gemini provider — uses the google-genai Python SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app import config
from app.providers.base import LLMProvider, classify_error, run_connection_test
from app.providers.errors import ProviderError
from app.providers.types import CompletionRequest, CompletionResponse, TokenUsage


@dataclass
class GeminiProvider(LLMProvider):
    """LLM provider using the Google Gemini API.

    Requires ``GEMINI_API_KEY`` to be set. Install with::

        pip install promptforge-backend[gemini]
    """

    model: str = field(default_factory=lambda: config.GEMINI_MODEL)
    # Read at instantiation time (not import time) so env patches in tests work
    # and runtime key rotation is supported.
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    _client: object = field(default=None, init=False, repr=False)

    def _get_client(self):
        """Return a cached genai.Client, creating one on first use."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def send_message(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Send a message via the Gemini API and return the text response."""
        from google.genai.types import GenerateContentConfig

        try:
            client = self._get_client()
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=user_message,
                config=GenerateContentConfig(system_instruction=system_prompt),
            )
            return response.text or ""
        except ProviderError:
            raise
        except Exception as exc:
            raise classify_error(exc, provider=self.provider_name) from exc

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def test_connection(self, timeout: float = 10.0) -> tuple[bool, str | None]:
        """Test connectivity with a minimal request."""
        from google.genai.types import GenerateContentConfig

        async def _ping():
            client = self._get_client()
            await client.aio.models.generate_content(
                model=self.model,
                contents="hi",
                config=GenerateContentConfig(max_output_tokens=1),
            )

        return await run_connection_test(_ping, timeout=timeout)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a completion with token usage tracking."""
        from google.genai.types import GenerateContentConfig

        try:
            client = self._get_client()
            config_kwargs: dict = {"system_instruction": request.system_prompt}
            if request.temperature is not None:
                config_kwargs["temperature"] = request.temperature
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=request.user_message,
                config=GenerateContentConfig(**config_kwargs),
            )
            usage = None
            if response.usage_metadata:
                usage = TokenUsage(
                    input_tokens=response.usage_metadata.prompt_token_count,
                    output_tokens=response.usage_metadata.candidates_token_count,
                )
            return CompletionResponse(
                text=response.text or "",
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise classify_error(exc, provider=self.provider_name) from exc

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "Gemini"
