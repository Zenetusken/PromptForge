"""Tests for LLM provider implementations (P2-P8, T1-T11)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# P-parse — parse_json_robust() three-strategy fallback
# ---------------------------------------------------------------------------

def test_parse_json_robust_direct_parse():
    from app.providers.base import parse_json_robust
    assert parse_json_robust('{"a": 1}') == {"a": 1}


def test_parse_json_robust_code_block():
    from app.providers.base import parse_json_robust
    text = 'Sure!\n```json\n{"b": 2}\n```\nDone.'
    assert parse_json_robust(text) == {"b": 2}


def test_parse_json_robust_regex_extract():
    from app.providers.base import parse_json_robust
    text = 'Here is the result: {"c": 3} — all done.'
    assert parse_json_robust(text) == {"c": 3}


# ---------------------------------------------------------------------------
# P-thinking — _make_extra() adaptive thinking behavior
# ---------------------------------------------------------------------------

def test_anthropic_thinking_enabled_for_opus():
    from app.providers.anthropic_api import AnthropicAPIProvider
    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    max_tok, extra = provider._make_extra("claude-opus-4-6")
    assert "thinking" in extra
    assert extra["thinking"]["type"] == "adaptive"
    assert max_tok == 16000


def test_anthropic_thinking_disabled_for_haiku():
    from app.providers.anthropic_api import AnthropicAPIProvider
    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    max_tok, extra = provider._make_extra("claude-haiku-4-5")
    assert "thinking" not in extra
    assert max_tok == 8192


def test_anthropic_thinking_disabled_warns_when_schema_provided(caplog):
    import logging
    from app.providers.anthropic_api import AnthropicAPIProvider
    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    with caplog.at_level(logging.WARNING, logger="app.providers.anthropic_api"):
        max_tok, extra = provider._make_extra("claude-opus-4-6", schema={"type": "object"})
    assert "thinking" not in extra
    assert any("thinking" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# P-agentic — complete_agentic() deeper behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ephemeral_caching_in_complete_agentic():
    """complete_agentic() must pass cache_control={"type":"ephemeral"} to the API."""
    from app.providers.anthropic_api import AnthropicAPIProvider

    end_response = MagicMock()
    end_response.stop_reason = "end_turn"
    end_response.content = [MagicMock(type="text", text="done")]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.get_final_message = AsyncMock(return_value=end_response)

    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.return_value = mock_stream

    await provider.complete_agentic("sys", "user", "claude-haiku-4-5", [])

    call_kwargs = provider._client.messages.stream.call_args.kwargs
    assert call_kwargs.get("cache_control") == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_agentic_result_output_from_submit_result():
    """When model calls submit_result tool, AgenticResult.output is populated."""
    from app.providers.anthropic_api import AnthropicAPIProvider
    from app.providers.base import AgenticResult

    submit_block = MagicMock()
    submit_block.type = "tool_use"
    submit_block.name = "submit_result"
    submit_block.id = "tu_submit"
    submit_block.input = {"summary": "found it", "files": ["a.py"]}

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [submit_block]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.get_final_message = AsyncMock(return_value=response)

    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.return_value = mock_stream

    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "files": {"type": "array", "items": {"type": "string"}},
        },
    }
    result = await provider.complete_agentic(
        "sys", "user", "claude-haiku-4-5", [], output_schema=output_schema
    )

    assert isinstance(result, AgenticResult)
    assert result.output == {"summary": "found it", "files": ["a.py"]}


@pytest.mark.asyncio
async def test_on_tool_call_callback_invoked_with_name_and_input():
    """on_tool_call(name, input) is called for each tool invocation."""
    from app.providers.anthropic_api import AnthropicAPIProvider
    from app.providers.base import ToolDefinition, AgenticResult

    calls: list[tuple] = []

    def track(name: str, inp: dict) -> None:
        calls.append((name, inp))

    async def noop_handler(args: dict) -> str:
        return "ok"

    tool = ToolDefinition(
        name="my_tool",
        description="test",
        input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        handler=noop_handler,
    )

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "my_tool"
    tool_block.id = "tu_1"
    tool_block.input = {"x": "val"}

    turn1 = MagicMock()
    turn1.stop_reason = "tool_use"
    turn1.content = [tool_block]

    turn2 = MagicMock()
    turn2.stop_reason = "end_turn"
    turn2.content = [MagicMock(type="text", text="done")]

    call_n = 0
    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)

    def side(*a, **kw):
        nonlocal call_n
        call_n += 1
        mock_stream.get_final_message = AsyncMock(
            return_value=turn1 if call_n == 1 else turn2
        )
        return mock_stream

    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.side_effect = side

    await provider.complete_agentic(
        "sys", "user", "claude-haiku-4-5", [tool], on_tool_call=track
    )

    assert calls == [("my_tool", {"x": "val"})]


@pytest.mark.asyncio
async def test_complete_agentic_stops_at_max_turns():
    """Loop exits with stop_reason='max_turns' when max_turns is exhausted."""
    from app.providers.anthropic_api import AnthropicAPIProvider
    from app.providers.base import ToolDefinition, AgenticResult

    async def noop(args: dict) -> str:
        return "x"

    tool = ToolDefinition(
        name="t", description="t",
        input_schema={"type": "object"}, handler=noop,
    )

    # Every response is tool_use, so loop never exits via end_turn
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "t"
    tool_block.id = "tu_x"
    tool_block.input = {}

    always_tool = MagicMock()
    always_tool.stop_reason = "tool_use"
    always_tool.content = [tool_block]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.get_final_message = AsyncMock(return_value=always_tool)
    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.return_value = mock_stream

    result = await provider.complete_agentic(
        "sys", "user", "claude-haiku-4-5", [tool], max_turns=2
    )

    assert isinstance(result, AgenticResult)
    assert result.stop_reason == "max_turns"
    assert provider._client.messages.stream.call_count == 2


@pytest.mark.asyncio
async def test_complete_returns_empty_string_on_no_content():
    """Both providers return '' when the response has no text blocks."""
    from app.providers.anthropic_api import AnthropicAPIProvider

    # AnthropicAPIProvider: response with only a non-text block (no .text attr)
    non_text_block = MagicMock(spec=[])  # spec=[] means no attributes at all
    response = MagicMock()
    response.content = [non_text_block]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.get_final_message = AsyncMock(return_value=response)

    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.return_value = mock_stream

    result = await provider.complete("sys", "user", "claude-haiku-4-5")
    assert result == ""

    # ClaudeCLIProvider: message with no content blocks
    from app.providers.claude_cli import ClaudeCLIProvider
    from claude_agent_sdk import AssistantMessage

    real_msg = MagicMock(spec=AssistantMessage)
    real_msg.content = []  # empty

    async def mock_query(prompt, options):
        yield real_msg

    cli_provider = ClaudeCLIProvider.__new__(ClaudeCLIProvider)
    cli_provider._query = mock_query
    cli_result = await cli_provider.complete("sys", "user", "claude-haiku-4-5")
    assert cli_result == ""


# ---------------------------------------------------------------------------
# P2 — AnthropicAPIProvider.complete_json() with schema uses output_config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_json_with_schema_uses_output_config():
    """When schema dict provided, API call must include output_config.format."""
    from app.providers.anthropic_api import AnthropicAPIProvider

    schema = {
        "type": "object",
        "properties": {"task_type": {"type": "string"}},
        "required": ["task_type"],
        "additionalProperties": False,
    }

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text='{"task_type": "coding"}')]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.get_final_message = AsyncMock(return_value=mock_response)

    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.return_value = mock_stream

    result = await provider.complete_json("sys", "user", "claude-haiku-4-5", schema=schema)

    assert result == {"task_type": "coding"}
    call_kwargs = provider._client.messages.stream.call_args.kwargs
    assert "output_config" in call_kwargs
    assert call_kwargs["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_complete_json_without_schema_uses_parse_json_robust():
    """When no schema, falls back to parse_json_robust on streamed text."""
    from app.providers.anthropic_api import AnthropicAPIProvider

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text='{"task_type": "general"}')]
    mock_response.stop_reason = "end_turn"

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.get_final_message = AsyncMock(return_value=mock_response)

    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.return_value = mock_stream

    result = await provider.complete_json("sys", "user", "claude-haiku-4-5")

    assert result == {"task_type": "general"}
    call_kwargs = provider._client.messages.stream.call_args.kwargs
    assert "output_config" not in call_kwargs


# ---------------------------------------------------------------------------
# P3 — ClaudeCLIProvider.complete_json() with schema uses parse_json_robust
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cli_complete_json_with_schema_uses_parse_json_robust():
    """ClaudeCLIProvider.complete_json(schema=...) calls complete() and
    parses with parse_json_robust — no API delegation."""
    from app.providers.claude_cli import ClaudeCLIProvider
    from claude_agent_sdk import AssistantMessage, TextBlock

    schema = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "additionalProperties": False,
    }

    real_msg = MagicMock(spec=AssistantMessage)
    real_block = MagicMock(spec=TextBlock)
    real_block.text = '{"x": "hello"}'
    real_msg.content = [real_block]

    async def mock_query(prompt, options):
        yield real_msg

    provider = ClaudeCLIProvider.__new__(ClaudeCLIProvider)
    provider._query = mock_query

    result = await provider.complete_json("sys", "user", "claude-haiku-4-5", schema=schema)
    assert result == {"x": "hello"}


# ---------------------------------------------------------------------------
# P4 — complete_agentic() tool handler error isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_agentic_tool_error_returns_error_to_model():
    """A tool handler exception must produce a tool_result error, not crash the loop."""
    from app.providers.anthropic_api import AnthropicAPIProvider
    from app.providers.base import ToolDefinition, AgenticResult

    async def failing_handler(args: dict) -> str:
        raise RuntimeError("disk full")

    tool = ToolDefinition(
        name="read_file",
        description="read",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        handler=failing_handler,
    )

    # Turn 1: model calls tool → handler raises
    # Turn 2: model receives error result → returns end_turn
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "read_file"
    tool_block.id = "tu_1"
    tool_block.input = {"path": "/etc/foo"}

    turn1_response = MagicMock()
    turn1_response.stop_reason = "tool_use"
    turn1_response.content = [tool_block]

    turn2_response = MagicMock()
    turn2_response.stop_reason = "end_turn"
    turn2_response.content = [MagicMock(type="text", text="Could not read file.")]

    call_count = 0
    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.get_final_message = AsyncMock(return_value=turn1_response)

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_stream.get_final_message = AsyncMock(
            return_value=turn1_response if call_count == 1 else turn2_response
        )
        return mock_stream

    provider = AnthropicAPIProvider.__new__(AnthropicAPIProvider)
    provider._client = MagicMock()
    provider._client.messages.stream.side_effect = side_effect

    result = await provider.complete_agentic("sys", "user", "claude-haiku-4-5", [tool])

    assert isinstance(result, AgenticResult)
    assert result.text == "Could not read file."
    # Verify tool_result with is_error was sent back on turn 2.
    # messages is mutated in place; by the time we assert, it contains:
    #   [user, assistant(turn1), user(tool_result), assistant(turn2)]
    # So the tool_result content is at [-2] (second to last entry).
    turn2_messages = provider._client.messages.stream.call_args_list[1].kwargs["messages"]
    # Find the tool_result entry (role=user, content is a list with type=tool_result)
    tool_result_entries = [
        m for m in turn2_messages
        if m.get("role") == "user" and isinstance(m.get("content"), list)
        and any(isinstance(r, dict) and r.get("type") == "tool_result" for r in m["content"])
    ]
    assert tool_result_entries, "No tool_result message found in turn 2 messages"
    tool_results = tool_result_entries[0]["content"]
    assert any(r.get("is_error") is True for r in tool_results if isinstance(r, dict))


# ---------------------------------------------------------------------------
# P5 — AgenticResult.stop_reason field
# ---------------------------------------------------------------------------

def test_agentic_result_has_stop_reason():
    from app.providers.base import AgenticResult
    r = AgenticResult(text="hi")
    assert r.stop_reason == "end_turn"  # default


def test_agentic_result_max_turns_stop_reason():
    from app.providers.base import AgenticResult
    r = AgenticResult(text="", stop_reason="max_turns")
    assert r.stop_reason == "max_turns"


# ---------------------------------------------------------------------------
# P6 — parse_json_robust() logs a warning on failure
# ---------------------------------------------------------------------------

def test_parse_json_robust_logs_warning_on_failure(caplog):
    import logging
    from app.providers.base import parse_json_robust
    with caplog.at_level(logging.WARNING, logger="app.providers.base"):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            parse_json_robust("this is definitely not json at all")
    assert any("parse_json_robust" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# P7 — ABC stream() is declared as async
# ---------------------------------------------------------------------------

def test_abc_stream_is_async():
    import inspect
    from app.providers.base import LLMProvider
    assert "stream" in LLMProvider.__abstractmethods__
    # Verify implementations are async generators (not sync)
    from app.providers.anthropic_api import AnthropicAPIProvider
    assert inspect.isasyncgenfunction(AnthropicAPIProvider.stream)


# ---------------------------------------------------------------------------
# P8 — ClaudeCLIProvider.stream() word-boundary chunking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cli_stream_yields_word_boundary_chunks():
    """Chunks should not split words mid-token."""
    from app.providers.claude_cli import ClaudeCLIProvider

    long_text = "hello world foo bar baz " * 100  # 2400 chars

    async def mock_query(prompt, options):
        msg = MagicMock()
        msg.__class__.__name__ = "AssistantMessage"
        block = MagicMock()
        block.__class__.__name__ = "TextBlock"
        block.text = long_text
        msg.content = [block]
        yield msg

    provider = ClaudeCLIProvider.__new__(ClaudeCLIProvider)
    provider._query = mock_query

    # Patch the isinstance checks by using actual classes
    from claude_agent_sdk import AssistantMessage, TextBlock

    real_msg = MagicMock(spec=AssistantMessage)
    real_block = MagicMock(spec=TextBlock)
    real_block.text = long_text
    real_msg.content = [real_block]

    async def mock_query_real(prompt, options):
        yield real_msg

    provider._query = mock_query_real

    with patch.dict("os.environ", {}, clear=True):
        chunks = []
        async for chunk in provider.stream("sys", "user", "claude-haiku-4-5"):
            chunks.append(chunk)

    full = "".join(chunks)
    assert full == long_text
    # Should produce multiple chunks for a 2400-char response
    assert len(chunks) > 1
