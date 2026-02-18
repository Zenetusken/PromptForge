"""Tests for the Claude CLI provider."""

import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from app.providers import invalidate_detect_cache
from app.providers.claude_cli import ClaudeCLIProvider, _get_sdk_env

# --- Lightweight stand-ins for SDK types ---
# Using real classes avoids MagicMock isinstance quirks.


@dataclass
class _TextBlock:
    text: str


@dataclass
class _ToolUseBlock:
    """Non-text block that should be ignored."""

    tool_name: str = "dummy"


@dataclass
class _AssistantMessage:
    content: list = field(default_factory=list)


@dataclass
class _UserMessage:
    """Non-assistant message that should be ignored."""

    content: list = field(default_factory=list)


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    """Clear module-level caches before each test."""
    invalidate_detect_cache()
    yield
    invalidate_detect_cache()


def _build_sdk_mock(query_fn):
    """Build a mock claude_agent_sdk module with real type classes."""
    mock_sdk = MagicMock()
    mock_sdk.query = query_fn
    mock_sdk.ClaudeAgentOptions = MagicMock()
    mock_sdk.AssistantMessage = _AssistantMessage
    mock_sdk.TextBlock = _TextBlock
    return mock_sdk


class TestClaudeCLIProvider:
    def test_model_name(self):
        provider = ClaudeCLIProvider(model="claude-opus-4-6")
        assert provider.model_name == "claude-opus-4-6"

    def test_provider_name(self):
        provider = ClaudeCLIProvider()
        assert provider.provider_name == "Claude CLI"

    def test_is_available_when_cli_present(self):
        with patch("app.providers.claude_cli.which_claude_cached", return_value=True):
            provider = ClaudeCLIProvider()
            assert provider.is_available() is True

    def test_is_not_available_when_cli_missing(self):
        with patch("app.providers.claude_cli.which_claude_cached", return_value=False):
            provider = ClaudeCLIProvider()
            assert provider.is_available() is False

    def test_get_sdk_env(self):
        env = _get_sdk_env()
        assert env["CLAUDECODE"] == ""
        assert env["CLAUDE_CODE_DISABLE_NONINTERACTIVE_TIPS"] == "1"

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test send_message collects text from AssistantMessage TextBlocks."""
        provider = ClaudeCLIProvider(model="claude-opus-4-6")

        msg = _AssistantMessage(content=[_TextBlock(text='{"result": "ok"}')])

        async def mock_query(**kwargs):
            yield msg

        with patch.dict(sys.modules, {"claude_agent_sdk": _build_sdk_mock(mock_query)}):
            result = await provider.send_message("system", "user")

        assert result == '{"result": "ok"}'

    @pytest.mark.asyncio
    async def test_send_message_multiple_blocks(self):
        """Test send_message concatenates text from multiple TextBlocks."""
        provider = ClaudeCLIProvider()

        msg = _AssistantMessage(content=[
            _TextBlock(text="Hello "),
            _TextBlock(text="World"),
        ])

        async def mock_query(**kwargs):
            yield msg

        with patch.dict(sys.modules, {"claude_agent_sdk": _build_sdk_mock(mock_query)}):
            result = await provider.send_message("system", "user")

        assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_send_message_ignores_non_text_blocks(self):
        """Non-TextBlock content is skipped."""
        provider = ClaudeCLIProvider()

        msg = _AssistantMessage(content=[
            _ToolUseBlock(tool_name="bash"),
            _TextBlock(text="only text"),
        ])

        async def mock_query(**kwargs):
            yield msg

        with patch.dict(sys.modules, {"claude_agent_sdk": _build_sdk_mock(mock_query)}):
            result = await provider.send_message("system", "user")

        assert result == "only text"

    @pytest.mark.asyncio
    async def test_send_message_ignores_non_assistant_messages(self):
        """Non-AssistantMessage messages are skipped."""
        provider = ClaudeCLIProvider()

        async def mock_query(**kwargs):
            yield _UserMessage(content=[_TextBlock(text="ignored")])
            yield _AssistantMessage(content=[_TextBlock(text="kept")])

        with patch.dict(sys.modules, {"claude_agent_sdk": _build_sdk_mock(mock_query)}):
            result = await provider.send_message("system", "user")

        assert result == "kept"

    @pytest.mark.asyncio
    async def test_send_message_error_classified(self):
        """Test that SDK errors are wrapped via classify_error."""
        from app.providers.errors import ProviderError

        provider = ClaudeCLIProvider()

        async def mock_query(**kwargs):
            raise RuntimeError("rate limit exceeded")
            yield  # pragma: no cover  # noqa: RET503 — makes this an async gen

        with patch.dict(sys.modules, {"claude_agent_sdk": _build_sdk_mock(mock_query)}):
            with pytest.raises(ProviderError, match="Rate limit exceeded"):
                await provider.send_message("system", "user")

    @pytest.mark.asyncio
    async def test_send_message_empty_response(self):
        """No messages yields empty string."""
        provider = ClaudeCLIProvider()

        async def mock_query(**kwargs):
            return
            yield  # pragma: no cover  # noqa: RET503 — makes this an async gen

        with patch.dict(sys.modules, {"claude_agent_sdk": _build_sdk_mock(mock_query)}):
            result = await provider.send_message("system", "user")

        assert result == ""
