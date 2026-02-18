"""Optional integration tests — only run when real API keys are set.

These tests make actual API calls and are gated by environment variables.
They never run during normal ``pytest`` — only when explicitly enabled:

    ANTHROPIC_API_KEY=sk-... pytest tests/test_providers_integration.py -v
    OPENAI_API_KEY=sk-...   pytest tests/test_providers_integration.py -v
    GEMINI_API_KEY=...      pytest tests/test_providers_integration.py -v
"""

import os

import pytest

from app.providers import invalidate_detect_cache


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    invalidate_detect_cache()
    yield
    invalidate_detect_cache()


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="No ANTHROPIC_API_KEY set — skipping Anthropic integration test",
)
class TestAnthropicIntegration:
    @pytest.mark.asyncio
    async def test_send_message(self):
        from app.providers.anthropic_api import AnthropicAPIProvider

        provider = AnthropicAPIProvider()
        result = await provider.send_message("Respond with OK", "ping")
        assert "ok" in result.lower()

    @pytest.mark.asyncio
    async def test_complete_with_usage(self):
        from app.providers.anthropic_api import AnthropicAPIProvider
        from app.providers.types import CompletionRequest

        provider = AnthropicAPIProvider()
        request = CompletionRequest(system_prompt="Respond with OK", user_message="ping")
        response = await provider.complete(request)
        assert response.usage is not None
        assert response.usage.input_tokens is not None
        assert response.usage.input_tokens > 0


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="No OPENAI_API_KEY set — skipping OpenAI integration test",
)
class TestOpenAIIntegration:
    @pytest.mark.asyncio
    async def test_send_message(self):
        from app.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        result = await provider.send_message("Respond with OK", "ping")
        assert "ok" in result.lower()

    @pytest.mark.asyncio
    async def test_complete_with_usage(self):
        from app.providers.openai_provider import OpenAIProvider
        from app.providers.types import CompletionRequest

        provider = OpenAIProvider()
        request = CompletionRequest(system_prompt="Respond with OK", user_message="ping")
        response = await provider.complete(request)
        assert response.usage is not None
        assert response.usage.input_tokens is not None
        assert response.usage.input_tokens > 0


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="No GEMINI_API_KEY set — skipping Gemini integration test",
)
class TestGeminiIntegration:
    @pytest.mark.asyncio
    async def test_send_message(self):
        from app.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        result = await provider.send_message("Respond with OK", "ping")
        assert "ok" in result.lower()

    @pytest.mark.asyncio
    async def test_complete_with_usage(self):
        from app.providers.gemini_provider import GeminiProvider
        from app.providers.types import CompletionRequest

        provider = GeminiProvider()
        request = CompletionRequest(system_prompt="Respond with OK", user_message="ping")
        response = await provider.complete(request)
        assert response.usage is not None
        assert response.usage.input_tokens is not None
        assert response.usage.input_tokens > 0
