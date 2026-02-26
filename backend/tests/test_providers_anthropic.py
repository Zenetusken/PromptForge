"""Tests for the Anthropic API provider."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers import invalidate_detect_cache
from app.providers.anthropic_api import (
    _CACHE_CONTROL,
    AnthropicAPIProvider,
    _classify_anthropic_error,
)
from app.providers.errors import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderPermissionError,
    RateLimitError,
)
from app.providers.types import CompletionRequest


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
            cache_control=_CACHE_CONTROL,
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
        # Verify it used max_tokens=1 and cache_control
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == 1
        assert call_kwargs.kwargs["cache_control"] == _CACHE_CONTROL

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


class TestCompleteTracksTokens:
    @pytest.mark.asyncio
    async def test_complete_tracks_cache_tokens(self):
        """complete() populates cache token fields from response.usage."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")

        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_usage.cache_creation_input_tokens = 80
        mock_usage.cache_read_input_tokens = 20

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="optimized prompt")]
        mock_response.model = "claude-opus-4-6"
        mock_response.usage = mock_usage

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            result = await provider.complete(
                CompletionRequest(system_prompt="sys", user_message="user"),
            )

        assert result.usage is not None
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 50
        assert result.usage.cache_creation_input_tokens == 80
        assert result.usage.cache_read_input_tokens == 20

    @pytest.mark.asyncio
    async def test_complete_cache_tokens_none_when_absent(self):
        """cache fields are None when the SDK response doesn't have them."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")

        # Simulate older SDK without cache token attrs
        mock_usage = MagicMock(spec=["input_tokens", "output_tokens"])
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="output")]
        mock_response.model = "claude-opus-4-6"
        mock_response.usage = mock_usage

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            result = await provider.complete(
                CompletionRequest(system_prompt="sys", user_message="user"),
            )

        assert result.usage is not None
        assert result.usage.cache_creation_input_tokens is None
        assert result.usage.cache_read_input_tokens is None


class TestCountTokens:
    @pytest.mark.asyncio
    async def test_count_tokens_uses_sdk(self):
        """count_tokens calls the SDK's count_tokens endpoint."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")

        mock_result = MagicMock()
        mock_result.input_tokens = 42

        mock_client = AsyncMock()
        mock_client.messages.count_tokens = AsyncMock(return_value=mock_result)

        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            count = await provider.count_tokens("Hello world, this is a test")

        assert count == 42
        mock_client.messages.count_tokens.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_count_tokens_falls_back_on_error(self):
        """count_tokens falls back to heuristic when SDK call fails."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")

        mock_client = AsyncMock()
        mock_client.messages.count_tokens = AsyncMock(
            side_effect=Exception("API error"),
        )

        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            text = "a" * 100
            count = await provider.count_tokens(text)

        # Heuristic: len(text) // 4 = 25
        assert count == 25


def _make_anthropic_module():
    """Build a mock anthropic module with all exception types as real classes.

    Every exception type must be a real ``type`` (not MagicMock) so that
    ``isinstance()`` calls in ``_classify_anthropic_error`` work correctly.
    """
    mod = MagicMock()
    mod.AuthenticationError = type("AuthenticationError", (Exception,), {})
    mod.PermissionDeniedError = type("PermissionDeniedError", (Exception,), {})
    mod.RateLimitError = type("RateLimitError", (Exception,), {})
    mod.NotFoundError = type("NotFoundError", (Exception,), {})
    mod.APITimeoutError = type("APITimeoutError", (Exception,), {})
    mod.APIConnectionError = type("APIConnectionError", (Exception,), {})
    return mod


class TestClassifyAnthropicError:
    def test_authentication_error(self):
        """SDK AuthenticationError maps to our AuthenticationError."""
        mod = _make_anthropic_module()
        exc = mod.AuthenticationError("invalid key")

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        assert isinstance(result, AuthenticationError)
        assert result.provider == "test"

    def test_permission_denied_error(self):
        mod = _make_anthropic_module()
        exc = mod.PermissionDeniedError("forbidden")

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        assert isinstance(result, ProviderPermissionError)

    def test_rate_limit_extracts_retry_after(self):
        """SDK RateLimitError extracts retry-after header."""
        mod = _make_anthropic_module()
        exc = mod.RateLimitError("rate limited")
        exc.response = MagicMock()
        exc.response.headers = {"retry-after": "30"}

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        assert isinstance(result, RateLimitError)
        assert result.retry_after == 30.0

    def test_rate_limit_no_retry_after(self):
        """RateLimitError without retry-after header sets retry_after=None."""
        mod = _make_anthropic_module()
        exc = mod.RateLimitError("rate limited")
        exc.response = MagicMock()
        exc.response.headers = {}

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        assert isinstance(result, RateLimitError)
        assert result.retry_after is None

    def test_not_found_error(self):
        mod = _make_anthropic_module()
        exc = mod.NotFoundError("model not found")

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        assert isinstance(result, ModelNotFoundError)

    def test_timeout_error(self):
        mod = _make_anthropic_module()
        exc = mod.APITimeoutError("timed out")

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        assert isinstance(result, ProviderConnectionError)

    def test_connection_error(self):
        mod = _make_anthropic_module()
        exc = mod.APIConnectionError("connection refused")

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        assert isinstance(result, ProviderConnectionError)

    def test_unknown_error_falls_through(self):
        """Unknown exceptions fall back to generic classify_error."""
        mod = _make_anthropic_module()
        exc = ValueError("something unexpected")

        with patch.dict(sys.modules, {"anthropic": mod}):
            result = _classify_anthropic_error(exc, provider="test")

        # Falls through to generic classify_error
        from app.providers.errors import ProviderError
        assert isinstance(result, ProviderError)
