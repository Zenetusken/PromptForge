"""Tests for the LLMProvider base class and JSON extraction logic."""

from unittest.mock import patch

import pytest

from app.providers.base import (
    LLMProvider,
    _extract_first_json_object,
    _retry_transient,
    classify_error,
    friendly_error,
)
from app.providers.errors import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderError,
    ProviderPermissionError,
    RateLimitError,
)
from app.providers.types import CompletionRequest


def _fast_retry_patch():
    """Create a patched _retry_transient with fast delays for tests."""
    _real = _retry_transient

    async def _fast(fn, **kwargs):
        kwargs.setdefault("base_delay", 0.01)
        kwargs.setdefault("rate_limit_base_delay", 0.01)
        return await _real(fn, **kwargs)

    return patch("app.providers.base._retry_transient", new=_fast)

# --- _extract_first_json_object tests ---


class TestExtractFirstJsonObject:
    def test_simple_object(self):
        assert _extract_first_json_object('{"key": "value"}') == '{"key": "value"}'

    def test_nested_object(self):
        text = '{"a": {"b": 1}}'
        assert _extract_first_json_object(text) == text

    def test_with_surrounding_text(self):
        text = 'Here is the result: {"key": 42} and more text'
        assert _extract_first_json_object(text) == '{"key": 42}'

    def test_braces_in_strings(self):
        text = '{"msg": "use {braces} here"}'
        assert _extract_first_json_object(text) == text

    def test_escaped_quotes(self):
        text = r'{"msg": "a \"quoted\" word"}'
        assert _extract_first_json_object(text) == text

    def test_no_object(self):
        assert _extract_first_json_object("no json here") is None

    def test_unbalanced_braces(self):
        assert _extract_first_json_object("{unbalanced") is None

    def test_empty_string(self):
        assert _extract_first_json_object("") is None


# --- Concrete test provider for base class tests ---


class FakeProvider(LLMProvider):
    """Minimal concrete provider for testing base class methods."""

    def __init__(self, response: str = ""):
        self._response = response

    async def send_message(self, system_prompt: str, user_message: str) -> str:
        return self._response

    def is_available(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return "fake-model"

    @property
    def provider_name(self) -> str:
        return "Fake"


# --- send_message_json tests ---


class TestSendMessageJson:
    @pytest.mark.asyncio
    async def test_direct_json(self):
        provider = FakeProvider('{"task_type": "code", "complexity": "high"}')
        result = await provider.send_message_json("system", "user")
        assert result == {"task_type": "code", "complexity": "high"}

    @pytest.mark.asyncio
    async def test_json_code_fence(self):
        provider = FakeProvider('Here is the analysis:\n```json\n{"key": "value"}\n```')
        result = await provider.send_message_json("system", "user")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_generic_code_fence(self):
        provider = FakeProvider("Result:\n```\n{\"key\": 123}\n```")
        result = await provider.send_message_json("system", "user")
        assert result == {"key": 123}

    @pytest.mark.asyncio
    async def test_brace_extraction_fallback(self):
        provider = FakeProvider('The result is {"key": "found"} as expected.')
        result = await provider.send_message_json("system", "user")
        assert result == {"key": "found"}

    @pytest.mark.asyncio
    async def test_no_json_raises(self):
        provider = FakeProvider("This is not JSON at all")
        with pytest.raises(ValueError, match="Failed to parse LLM response as JSON"):
            await provider.send_message_json("system", "user")

    @pytest.mark.asyncio
    async def test_whitespace_stripped(self):
        provider = FakeProvider('  \n  {"key": "value"}  \n  ')
        result = await provider.send_message_json("system", "user")
        assert result == {"key": "value"}


# --- test_connection tests ---


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_success(self):
        provider = FakeProvider("OK")
        ok, error = await provider.test_connection()
        assert ok is True
        assert error is None

    @pytest.mark.asyncio
    async def test_failure_returns_error(self):

        class FailingProvider(FakeProvider):
            async def send_message(self, system_prompt: str, user_message: str) -> str:
                raise RuntimeError("Something went wrong")

        provider = FailingProvider()
        ok, error = await provider.test_connection()
        assert ok is False
        assert error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_auth_error_friendly(self):

        class AuthFailProvider(FakeProvider):
            async def send_message(self, system_prompt: str, user_message: str) -> str:
                raise RuntimeError("Authentication failed: invalid API key")

        provider = AuthFailProvider()
        ok, error = await provider.test_connection()
        assert ok is False
        assert error == "Invalid API key"


# --- friendly_error tests ---


class TestFriendlyError:
    def test_auth_errors(self):
        assert friendly_error(Exception("authentication failed")) == "Invalid API key"
        assert friendly_error(Exception("invalid api key")) == "Invalid API key"
        assert friendly_error(Exception("401 Unauthorized")) == "Invalid API key"

    def test_permission_error(self):
        assert friendly_error(Exception("403 Forbidden")) == "API key lacks required permissions"

    def test_rate_limit(self):
        assert friendly_error(Exception("rate limit exceeded")) == "Rate limit exceeded"

    def test_not_found(self):
        assert friendly_error(Exception("model not found")) == "Model not found — check model name"

    def test_generic_error(self):
        assert friendly_error(Exception("some random error")) == "some random error"

    def test_long_error_truncated(self):
        long_msg = "x" * 300
        result = friendly_error(Exception(long_msg))
        assert len(result) == 200


# --- supports() capability tests ---


class TestSupports:
    def test_known_model_matching_capability(self):
        """Known model from catalog returns True for a capability it has."""

        class ClaudeProvider(FakeProvider):
            @property
            def model_name(self) -> str:
                return "claude-opus-4-6"

        provider = ClaudeProvider()
        assert provider.supports("text") is True
        assert provider.supports("vision") is True

    def test_known_model_missing_capability(self):
        """Known model returns False for a capability it doesn't have."""

        class ClaudeProvider(FakeProvider):
            @property
            def model_name(self) -> str:
                return "claude-opus-4-6"

        provider = ClaudeProvider()
        assert provider.supports("function_calling") is False

    def test_unknown_model_returns_false(self):
        """Unknown model not in catalog returns False for any capability."""
        provider = FakeProvider()  # model_name = "fake-model"
        assert provider.supports("text") is False
        assert provider.supports("vision") is False

    def test_openai_has_function_calling(self):
        """OpenAI models have function_calling capability."""

        class OpenAIModelProvider(FakeProvider):
            @property
            def model_name(self) -> str:
                return "gpt-4.1"

        provider = OpenAIModelProvider()
        assert provider.supports("function_calling") is True
        assert provider.supports("text") is True


# --- complete_json retry tests ---


class TestCompleteJsonRetry:
    """Tests for complete_json retry behavior.

    Uses _fast_retry_patch to avoid real 10s rate-limit backoff delays.
    """

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """complete_json retries on RateLimitError."""
        call_count = 0

        class RetryProvider(FakeProvider):
            async def complete(self, request):
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise RateLimitError("Rate limit exceeded", provider="test")
                return await super().complete(request)

        provider = RetryProvider('{"key": "value"}')
        with _fast_retry_patch():
            result, response = await provider.complete_json(
                CompletionRequest(system_prompt="s", user_message="u"),
            )
        assert result == {"key": "value"}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """complete_json retries on ProviderConnectionError."""
        call_count = 0

        class RetryProvider(FakeProvider):
            async def complete(self, request):
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ProviderConnectionError("Connection timed out", provider="test")
                return await super().complete(request)

        provider = RetryProvider('{"key": "value"}')
        with _fast_retry_patch():
            result, _ = await provider.complete_json(
                CompletionRequest(system_prompt="s", user_message="u"),
            )
        assert result == {"key": "value"}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self):
        """Non-transient errors are not retried."""
        from app.providers.errors import AuthenticationError

        class AuthFailProvider(FakeProvider):
            async def complete(self, request):
                raise AuthenticationError("Invalid key", provider="test")

        provider = AuthFailProvider()
        with _fast_retry_patch(), pytest.raises(AuthenticationError):
            await provider.complete_json(
                CompletionRequest(system_prompt="s", user_message="u"),
            )

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self):
        """After max retries, the last error is raised."""

        class AlwaysRateLimitProvider(FakeProvider):
            async def complete(self, request):
                raise RateLimitError("Rate limit exceeded", provider="test")

        provider = AlwaysRateLimitProvider()
        with _fast_retry_patch(), pytest.raises(RateLimitError):
            await provider.complete_json(
                CompletionRequest(system_prompt="s", user_message="u"),
            )


# --- _retry_transient standalone tests ---


class TestRetryTransient:
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        call_count = 0

        async def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await _retry_transient(fn, base_delay=0.01)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        call_count = 0

        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("rate limited", provider="test")
            return "ok"

        result = await _retry_transient(
            fn, max_retries=2, base_delay=0.01, rate_limit_base_delay=0.01,
        )
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_exhausted(self):
        async def fn():
            raise ProviderConnectionError("timeout", provider="test")

        with pytest.raises(ProviderConnectionError):
            await _retry_transient(fn, max_retries=1, base_delay=0.01)


# --- _parse_json edge cases ---


class TestParseJsonEdgeCases:
    @pytest.mark.asyncio
    async def test_json_array_top_level(self):
        """Top-level JSON arrays should parse via direct strategy."""
        provider = FakeProvider('[{"a": 1}, {"b": 2}]')
        result = await provider.send_message_json("system", "user")
        assert result == [{"a": 1}, {"b": 2}]

    @pytest.mark.asyncio
    async def test_multiple_json_objects_takes_first(self):
        """Brace extraction returns the first complete JSON object."""
        provider = FakeProvider('first: {"a": 1} second: {"b": 2}')
        result = await provider.send_message_json("system", "user")
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_invalid_json_in_fence_falls_through(self):
        """Invalid JSON inside a code fence falls through to brace extraction."""
        provider = FakeProvider('```json\nnot valid\n```\nBut also {"key": "val"}')
        result = await provider.send_message_json("system", "user")
        assert result == {"key": "val"}

    @pytest.mark.asyncio
    async def test_deeply_nested_json(self):
        """Deeply nested JSON objects parse correctly."""
        provider = FakeProvider('```json\n{"a": {"b": {"c": {"d": 42}}}}\n```')
        result = await provider.send_message_json("system", "user")
        assert result == {"a": {"b": {"c": {"d": 42}}}}

    @pytest.mark.asyncio
    async def test_unicode_in_json(self):
        """Unicode characters in JSON values are handled."""
        provider = FakeProvider('{"emoji": "\\u2764", "text": "héllo"}')
        result = await provider.send_message_json("system", "user")
        assert result["text"] == "héllo"


# --- classify_error tests ---


class TestClassifyError:
    def test_already_provider_error_passthrough(self):
        """ProviderError subclasses are returned as-is."""
        original = RateLimitError("rate limited", provider="test")
        result = classify_error(original)
        assert result is original

    def test_authentication_error(self):
        result = classify_error(Exception("authentication failed"), provider="test")
        assert isinstance(result, AuthenticationError)
        assert result.provider == "test"

    def test_api_key_error(self):
        result = classify_error(Exception("invalid api key"))
        assert isinstance(result, AuthenticationError)

    def test_unauthorized_401(self):
        result = classify_error(Exception("401 Unauthorized"))
        assert isinstance(result, AuthenticationError)

    def test_permission_403(self):
        result = classify_error(Exception("403 Forbidden"))
        assert isinstance(result, ProviderPermissionError)

    def test_permission_keyword(self):
        result = classify_error(Exception("permission denied"))
        assert isinstance(result, ProviderPermissionError)

    def test_rate_limit(self):
        result = classify_error(Exception("rate limit exceeded"))
        assert isinstance(result, RateLimitError)

    def test_not_found(self):
        result = classify_error(Exception("model not found"))
        assert isinstance(result, ModelNotFoundError)

    def test_404_error(self):
        result = classify_error(Exception("404 Not Found"))
        assert isinstance(result, ModelNotFoundError)

    def test_timeout_string(self):
        result = classify_error(Exception("request timed out"))
        assert isinstance(result, ProviderConnectionError)

    def test_timeout_exception_type(self):
        result = classify_error(TimeoutError("connection timeout"))
        assert isinstance(result, ProviderConnectionError)

    def test_connection_error_type(self):
        result = classify_error(ConnectionError("refused"))
        assert isinstance(result, ProviderConnectionError)

    def test_generic_fallback(self):
        result = classify_error(Exception("something unexpected"))
        assert isinstance(result, ProviderError)
        assert type(result) is ProviderError  # Not a subclass
        assert str(result) == "something unexpected"

    def test_generic_truncates_long_message(self):
        long_msg = "x" * 300
        result = classify_error(Exception(long_msg))
        assert len(str(result)) == 200

    def test_provider_name_propagated(self):
        result = classify_error(Exception("some error"), provider="openai")
        assert result.provider == "openai"

    def test_original_exception_stored(self):
        original = Exception("root cause")
        result = classify_error(original, provider="test")
        assert result.original is original
