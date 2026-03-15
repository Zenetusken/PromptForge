"""Anthropic API provider — direct API with prompt caching."""

from __future__ import annotations

import logging
from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AnthropicAPIProvider(LLMProvider):
    """LLM provider that calls the Anthropic API directly."""

    name = "anthropic_api"

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()

    async def complete_parsed(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        output_format: type[T],
        max_tokens: int = 16384,
        effort: str | None = None,
    ) -> T:
        """Make an LLM call and return a parsed Pydantic model.

        System prompt is wrapped with cache_control: ephemeral for prompt caching.
        Thinking is adaptive for Opus/Sonnet, disabled for Haiku.
        Effort is only passed for non-Haiku models.
        """
        system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        thinking = self.thinking_config(model)

        output_config: dict | None = None
        is_haiku = "haiku" in model.lower()
        if effort is not None and not is_haiku:
            output_config = {"effort": effort}

        kwargs: dict = dict(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            thinking=thinking,
            output_format=output_format,
        )
        if output_config is not None:
            kwargs["output_config"] = output_config

        response = await self._client.messages.parse(**kwargs)

        logger.info(
            "anthropic_api complete_parsed model=%s input_tokens=%s output_tokens=%s",
            model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        return response.parsed_output
