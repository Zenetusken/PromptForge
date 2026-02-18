"""Tests for the OpenAI provider."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers import invalidate_detect_cache
from app.providers.openai_provider import OpenAIProvider


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    """Clear module-level caches before each test."""
    invalidate_detect_cache()
    yield
    invalidate_detect_cache()


class TestOpenAIProvider:
    def test_is_available_with_key(self):
        provider = OpenAIProvider(api_key="sk-test")
        assert provider.is_available() is True

    def test_is_not_available_without_key(self):
        provider = OpenAIProvider(api_key="")
        assert provider.is_available() is False

    def test_model_name(self):
        provider = OpenAIProvider(model="gpt-4o-mini")
        assert provider.model_name == "gpt-4o-mini"

    def test_provider_name(self):
        provider = OpenAIProvider()
        assert provider.provider_name == "OpenAI"

    @pytest.mark.asyncio
    async def test_send_message(self):
        provider = OpenAIProvider(api_key="sk-test")

        mock_message = MagicMock()
        mock_message.content = "Hello from OpenAI"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_module = MagicMock()
        mock_module.AsyncOpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_module}):
            result = await provider.send_message("system prompt", "user message")

        assert result == "Hello from OpenAI"
        mock_client.chat.completions.create.assert_awaited_once_with(
            model=provider.model,
            max_tokens=provider.max_tokens,
            messages=[
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user message"},
            ],
        )

    @pytest.mark.asyncio
    async def test_connection_success(self):
        provider = OpenAIProvider(api_key="sk-test")

        mock_message = MagicMock()
        mock_message.content = "hi"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_module = MagicMock()
        mock_module.AsyncOpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_module}):
            ok, error = await provider.test_connection()

        assert ok is True
        assert error is None
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == 1

    @pytest.mark.asyncio
    async def test_connection_auth_failure(self):
        provider = OpenAIProvider(api_key="bad-key")

        mock_module = MagicMock()
        mock_module.AsyncOpenAI.return_value.chat.completions.create = AsyncMock(
            side_effect=Exception("401 Unauthorized: invalid API key"),
        )
        with patch.dict(sys.modules, {"openai": mock_module}):
            ok, error = await provider.test_connection()

        assert ok is False
        assert error == "Invalid API key"
