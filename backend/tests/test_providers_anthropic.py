"""Tests for the Anthropic API provider."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers import invalidate_detect_cache
from app.providers.anthropic_api import AnthropicAPIProvider


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    """Clear module-level caches before each test."""
    invalidate_detect_cache()
    yield
    invalidate_detect_cache()


class TestAnthropicAPIProvider:
    def test_is_available_with_key(self):
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        assert provider.is_available() is True

    def test_is_not_available_without_key(self):
        provider = AnthropicAPIProvider(api_key="")
        assert provider.is_available() is False

    def test_model_name(self):
        provider = AnthropicAPIProvider(model="claude-sonnet-4-5-20250929")
        assert provider.model_name == "claude-sonnet-4-5-20250929"

    def test_provider_name(self):
        provider = AnthropicAPIProvider()
        assert provider.provider_name == "Anthropic API"

    @pytest.mark.asyncio
    async def test_send_message(self):
        provider = AnthropicAPIProvider(api_key="sk-ant-test")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # Patch the module that the lazy import resolves to
        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            result = await provider.send_message("system prompt", "user message")

        assert result == "Hello from Claude"
        mock_client.messages.create.assert_awaited_once_with(
            model=provider.model,
            max_tokens=provider.max_tokens,
            system="system prompt",
            messages=[{"role": "user", "content": "user message"}],
        )

    @pytest.mark.asyncio
    async def test_connection_success(self):
        provider = AnthropicAPIProvider(api_key="sk-ant-test")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="hi")]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            ok, error = await provider.test_connection()

        assert ok is True
        assert error is None
        # Verify it used max_tokens=1 (minimal request)
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == 1

    @pytest.mark.asyncio
    async def test_connection_auth_failure(self):
        provider = AnthropicAPIProvider(api_key="bad-key")

        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value.messages.create = AsyncMock(
            side_effect=Exception("401 Unauthorized: invalid API key"),
        )
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            ok, error = await provider.test_connection()

        assert ok is False
        assert error == "Invalid API key"
