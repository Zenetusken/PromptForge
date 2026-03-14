from __future__ import annotations

import asyncio
import contextvars
import json as _json
import logging
import os
from typing import AsyncGenerator, Callable

from app.providers.base import (
    AgenticResult,
    CompletionUsage,
    LLMProvider,
    ToolDefinition,
    invoke_tool,
    parse_json_robust,
)

logger = logging.getLogger(__name__)

# Task-local usage tracking (estimated — CLI has no real token data).
_usage_var: contextvars.ContextVar[CompletionUsage | None] = contextvars.ContextVar(
    "_cli_usage", default=None,
)

# The SDK's default stream-close timeout is 60 s — far too short for
# the Explore stage which runs up to 25 tool turns with network I/O.
# After 60 s, wait_for_result_and_end_input() closes stdin even while
# the CLI is still mid-conversation, causing the next transport.write()
# to raise CLIConnectionError("ProcessTransport is not ready for writing").
# Set the timeout to 10 minutes so stdin stays open for the full run.
os.environ.setdefault("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT", "600000")


class ClaudeCLIProvider(LLMProvider):
    """LLM provider using Claude Code CLI via claude-agent-sdk.

    Uses Max subscription via CLI for zero API cost.
    init.sh unsets CLAUDECODE before launching the backend so nested-session
    issues never arise in normal operation.
    """

    def __init__(self):
        try:
            from claude_agent_sdk import query
            self._query = query
        except ImportError:
            raise ImportError(
                "claude-agent-sdk is required for ClaudeCLIProvider. "
                "Install it with: pip install claude-agent-sdk"
            )

    @property
    def name(self) -> str:
        return "claude_cli"

    def get_last_usage(self) -> CompletionUsage | None:
        """Return estimated token usage from the most recent CLI call (task-local)."""
        return _usage_var.get(None)

    def _set_estimated_usage(self, system: str, user: str, output: str, model: str) -> None:
        """Set estimated usage using the ~4 chars/token heuristic."""
        _usage_var.set(CompletionUsage(
            input_tokens=max(1, (len(system) + len(user)) // 4),
            output_tokens=max(1, len(output) // 4),
            is_estimated=True,
            model=model,
        ))

    async def complete(self, system: str, user: str, model: str) -> str:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock

        options = ClaudeAgentOptions(
            system_prompt=system,
            model=model,
            max_turns=1,
        )
        full_text = ""
        async for msg in self._query(prompt=user, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        full_text += block.text
        self._set_estimated_usage(system, user, full_text, model)
        return full_text

    async def stream(self, system: str, user: str, model: str) -> AsyncGenerator[str, None]:
        """Stream LLM output via claude CLI subprocess with true token-level streaming.

        Uses --output-format stream-json --include-partial-messages to get raw
        Anthropic API streaming events (content_block_delta / text_delta) directly
        from the CLI, bypassing the Agent SDK's message-level buffering.
        """
        # Build environment: unset CLAUDECODE to avoid nested-session error
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        cmd = [
            "claude", "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--no-session-persistence",
            "--system-prompt", system,
            "--model", model,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Write prompt to stdin and close.  drain() flushes the write buffer
        # so large prompts (>64 KB pipe buffer) don't silently truncate.
        assert proc.stdin is not None
        proc.stdin.write(user.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()

        # Parse streaming JSON events from stdout.  The try/finally ensures
        # the subprocess is always cleaned up — even when the optimizer's
        # timeout cancels the consuming task mid-stream.
        assert proc.stdout is not None
        _output_chars = 0
        try:
            async for line_bytes in proc.stdout:
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    event = _json.loads(line)
                except _json.JSONDecodeError:
                    continue

                # Only yield text content deltas; skip thinking, signatures, etc.
                if event.get("type") != "stream_event":
                    continue
                inner = event.get("event", {})
                if inner.get("type") != "content_block_delta":
                    continue
                delta = inner.get("delta", {})
                if delta.get("type") == "text_delta" and delta.get("text"):
                    _output_chars += len(delta["text"])
                    yield delta["text"]
        finally:
            # Set estimated usage before cleanup
            _usage_var.set(CompletionUsage(
                input_tokens=max(1, (len(system) + len(user)) // 4),
                output_tokens=max(1, _output_chars // 4),
                is_estimated=True,
                model=model,
            ))
            # Kill the subprocess if it's still running (e.g. generator cancelled)
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass  # Already exited between our check and kill
            await proc.wait()
            if proc.returncode and proc.returncode != 0:
                stderr_output = ""
                if proc.stderr:
                    stderr_bytes = await proc.stderr.read()
                    stderr_output = stderr_bytes.decode("utf-8", errors="replace")[:500]
                logger.warning(
                    "claude CLI stream exited with code %d: %s",
                    proc.returncode, stderr_output,
                )

    async def complete_json(
        self,
        system: str,
        user: str,
        model: str,
        schema: dict | None = None,
    ) -> dict:
        """Structured JSON output via CLI provider.

        The Claude CLI does not support ``output_config.format`` (API-only feature),
        so native schema enforcement is unavailable.  When ``schema`` is provided:

        1. Injects a JSON-schema instruction block into the system prompt so the
           model is aware of the expected shape.
        2. Falls back to ``parse_json_robust()`` 3-strategy extraction.

        This is best-effort — callers that require guaranteed schema compliance
        should prefer AnthropicAPIProvider.
        """
        if schema is not None:
            logger.debug(
                "ClaudeCLIProvider.complete_json: schema provided but native "
                "schema enforcement is unavailable (CLI limitation). "
                "Injecting schema instruction into system prompt."
            )
            import json as _json_mod
            schema_instruction = (
                "\n\nIMPORTANT: You MUST respond with valid JSON that strictly "
                "conforms to this JSON schema:\n"
                f"```json\n{_json_mod.dumps(schema, indent=2)}\n```\n"
                "Output ONLY the JSON object. No markdown fences, no commentary."
            )
            system = system + schema_instruction
        raw = await self.complete(system, user, model)
        return parse_json_robust(raw)

    async def complete_agentic(
        self,
        system: str,
        user: str,
        model: str,
        tools: list[ToolDefinition],
        max_turns: int = 20,
        on_tool_call: Callable[[str, dict], None] | None = None,
        on_agent_text: Callable[[str], None] | None = None,
        output_schema: dict | None = None,
        resume_session_id: str | None = None,
    ) -> AgenticResult:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            create_sdk_mcp_server,
            tool,
        )

        # tool_calls must be declared before the loop so _tool_fn closures
        # can reference it via default argument capture.
        tool_calls: list[dict] = []
        sdk_tools = []
        for td in tools:
            handler = td.handler
            name = td.name

            @tool(td.name, td.description, td.input_schema)
            async def _tool_fn(
                args: dict,
                _handler=handler,
                _name=name,
                _on=on_tool_call,
                _calls=tool_calls,
            ) -> dict:
                result_str, _ = await invoke_tool(_name, args, _handler, _calls, _on)
                return {"content": [{"type": "text", "text": result_str}]}

            sdk_tools.append(_tool_fn)

        # Inject submit_result MCP tool for structured output (universal fallback).
        # The closure captures the output so we can read it after the loop.
        captured_output: dict = {}
        if output_schema:
            @tool(
                "submit_result",
                (
                    "Submit your final structured result. Call this tool exactly once "
                    "when you have finished all exploration and are ready to return your "
                    "complete findings. Do not call any other tools after this."
                ),
                output_schema,
            )
            async def _submit_tool(
                args: dict,
                _cap=captured_output,
                _on=on_tool_call,
            ) -> dict:
                if not _cap:
                    _cap.update(args)
                if _on:
                    try:
                        _on("submit_result", args)
                    except Exception as _cb_err:
                        logger.warning("on_tool_call callback raised: %s", _cb_err)
                return {"content": [{"type": "text", "text": "Result submitted. Exploration complete."}]}

            sdk_tools.append(_submit_tool)

        mcp_server = create_sdk_mcp_server(
            name="pf-tools", version="1.0.0", tools=sdk_tools
        )
        allowed = [f"mcp__pf-tools__{td.name}" for td in tools]
        if output_schema:
            allowed.append("mcp__pf-tools__submit_result")

        # Do NOT set output_format in ClaudeAgentOptions.  When output_format is
        # set, the SDK may surface structured output via ResultMessage.structured_output
        # without the model having called any exploration tools — the model fills
        # the schema from training knowledge rather than actual repository reads.
        # submit_result MCP tool is the canonical structured-output mechanism and is
        # enforced by the explore system prompt ("you MUST call the submit_result tool").
        opts_kwargs: dict = dict(
            system_prompt=system,
            model=model,
            max_turns=max_turns,
            mcp_servers={"pf-tools": mcp_server},
            allowed_tools=allowed,
        )
        if resume_session_id:
            opts_kwargs["resume"] = resume_session_id
        options = ClaudeAgentOptions(**opts_kwargs)

        full_text = ""
        sdk_structured_output: dict | None = None
        captured_session_id: str | None = None

        # Use AsyncIterable[dict] prompt — query() signature: str | AsyncIterable[dict].
        # SDK >=0.1.46 fixed the string-prompt race (PR #630: stdin was closed before MCP
        # server initialization completed). The async-generator path has been safe since
        # 0.1.45: stream_input() detects sdk_mcp_servers and calls
        # wait_for_result_and_end_input() (waits for _first_result_event before closing
        # stdin), keeping stdin open for the full MCP tool-calling loop.
        async def _prompt_stream():
            yield {
                "type": "user",
                "session_id": "",
                "message": {"role": "user", "content": user},
                "parent_tool_use_id": None,
            }

        try:
            async for msg in self._query(prompt=_prompt_stream(), options=options):
                if isinstance(msg, AssistantMessage):
                    # Fire on_agent_text once per TextBlock (not once per
                    # AssistantMessage) to match AnthropicAPIProvider granularity
                    # and give downstream consumers finer-grained streaming.
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            if on_agent_text:
                                try:
                                    on_agent_text(block.text)
                                except Exception:
                                    pass
                    full_text = "".join(
                        block.text for block in msg.content if isinstance(block, TextBlock)
                    ) or full_text
                else:
                    # Check for ResultMessage with structured_output (SDK output_format support)
                    structured = getattr(msg, "structured_output", None)
                    if structured:
                        sdk_structured_output = structured
                    # H3: Capture session_id for resume support
                    sid = getattr(msg, "session_id", None)
                    if sid:
                        captured_session_id = sid
        except BaseException as e:
            # Unwrap anyio ExceptionGroup to expose the actual sub-exception.
            # The SDK wraps errors in ExceptionGroup; unwrapping surfaces the
            # real cause for better diagnostics and stack traces.
            if isinstance(e, BaseExceptionGroup) or (
                hasattr(e, "exceptions") and isinstance(getattr(e, "exceptions", None), (list, tuple))
            ):
                actual = e.exceptions[0]
                logger.error(
                    "ClaudeCLIProvider agentic loop failed (unwrapped from %s): %s: %s",
                    type(e).__name__, type(actual).__name__, actual,
                )
                raise actual from e
            logger.error(
                "ClaudeCLIProvider agentic loop failed: %s: %s",
                type(e).__name__, e,
            )
            raise

        # Set estimated usage for the full agentic session
        self._set_estimated_usage(system, user, full_text, model)

        # Prefer SDK-level structured output, then submit_result capture, then text
        final_output = sdk_structured_output or (captured_output if captured_output else None)
        return AgenticResult(
            text=full_text, tool_calls=tool_calls, output=final_output,
            session_id=captured_session_id,
        )
