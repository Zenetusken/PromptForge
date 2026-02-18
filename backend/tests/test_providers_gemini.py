"""Tests for the Google Gemini provider."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers import invalidate_detect_cache
from app.providers.gemini_provider import GeminiProvider


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    """Clear module-level caches before each test."""
    invalidate_detect_cache()
    yield
    invalidate_detect_cache()


class TestGeminiProvider:
    def test_is_available_with_key(self):
        provider = GeminiProvider(api_key="test-key")
        assert provider.is_available() is True

    def test_is_not_available_without_key(self):
        provider = GeminiProvider(api_key="")
        assert provider.is_available() is False

    def test_model_name(self):
        provider = GeminiProvider(model="gemini-2.0-flash")
        assert provider.model_name == "gemini-2.0-flash"

    def test_provider_name(self):
        provider = GeminiProvider()
        assert provider.provider_name == "Gemini"

    @pytest.mark.asyncio
    async def test_send_message(self):
        provider = GeminiProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini"

        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        # Build mock google.genai and google.genai.types modules
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_config_instance = MagicMock()
        mock_types = MagicMock()
        mock_types.GenerateContentConfig.return_value = mock_config_instance

        mock_google = ModuleType("google")
        mock_google.genai = mock_genai  # type: ignore[attr-defined]

        with patch.dict(
            sys.modules,
            {
                "google": mock_google,
                "google.genai": mock_genai,
                "google.genai.types": mock_types,
            },
        ):
            result = await provider.send_message("system prompt", "user message")

        assert result == "Hello from Gemini"
        mock_aio_models.generate_content.assert_awaited_once()
        call_kwargs = mock_aio_models.generate_content.await_args
        assert call_kwargs.kwargs["model"] == provider.model
        assert call_kwargs.kwargs["contents"] == "user message"

    def _build_gemini_mocks(self, *, generate_side_effect=None):
        """Helper to create mock google.genai module hierarchy."""
        mock_response = MagicMock()
        mock_response.text = "hi"

        mock_aio_models = AsyncMock()
        if generate_side_effect:
            mock_aio_models.generate_content = AsyncMock(side_effect=generate_side_effect)
        else:
            mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_types = MagicMock()
        mock_google = ModuleType("google")
        mock_google.genai = mock_genai  # type: ignore[attr-defined]

        modules = {
            "google": mock_google,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        }
        return modules, mock_aio_models

    @pytest.mark.asyncio
    async def test_connection_success(self):
        provider = GeminiProvider(api_key="test-key")
        modules, mock_aio_models = self._build_gemini_mocks()

        with patch.dict(sys.modules, modules):
            ok, error = await provider.test_connection()

        assert ok is True
        assert error is None
        # Verify max_output_tokens=1 was used
        call_kwargs = mock_aio_models.generate_content.call_args
        config_arg = call_kwargs.kwargs["config"]
        assert config_arg is not None

    @pytest.mark.asyncio
    async def test_connection_auth_failure(self):
        provider = GeminiProvider(api_key="bad-key")
        modules, _ = self._build_gemini_mocks(
            generate_side_effect=Exception("401 Unauthorized: invalid API key"),
        )

        with patch.dict(sys.modules, modules):
            ok, error = await provider.test_connection()

        assert ok is False
        assert error == "Invalid API key"
