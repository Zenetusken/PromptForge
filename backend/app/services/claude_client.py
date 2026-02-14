"""Client for interacting with Claude via the Claude Code SDK."""

import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    TextBlock,
    query,
)

from app import config


def _get_sdk_env() -> dict[str, str]:
    """Return env overrides that allow the SDK to run in a nested context.

    The Claude CLI refuses to start inside an existing Claude Code session
    (detected via the CLAUDECODE env var). Since PromptForge's backend may
    run inside a Claude Code agent, we override that variable with an empty
    string so the SDK subprocess can start cleanly. The SDK merges
    {**os.environ, **options.env}, so our override takes precedence.
    """
    return {
        "CLAUDECODE": "",
        "CLAUDE_CODE_DISABLE_NONINTERACTIVE_TIPS": "1",
    }


def _extract_first_json_object(text: str) -> str | None:
    """Extract the first balanced JSON object from *text*.

    Counts brace depth while skipping characters inside JSON string literals,
    so embedded braces in string values don't break extraction.  Returns None
    if no balanced object is found.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


# Isolated working directory so the SDK subprocess doesn't pick up
# project-level CLAUDE.md, agent_scratchpad, or codebase context that
# cause the model to respond as a coding agent instead of returning JSON.
_ISOLATED_CWD = tempfile.gettempdir()


@dataclass
class ClaudeClient:
    """Wrapper around claude-code-sdk for sending prompts to Claude.

    Uses the Claude Code CLI subprocess with MAX subscription auth.
    No API key required.
    """

    model: str = field(default_factory=lambda: config.CLAUDE_MODEL)

    async def send_message(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Send a message to Claude via the SDK and return the text response.

        Args:
            system_prompt: The system prompt providing context and instructions.
            user_message: The user message to send.

        Returns:
            The text content of Claude's response.
        """
        options = ClaudeCodeOptions(
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",
            max_turns=1,
            model=self.model,
            cwd=_ISOLATED_CWD,
            env=_get_sdk_env(),
            allowed_tools=[],  # No tools — pure text response only
        )

        response_text = ""
        async for msg in query(prompt=user_message, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        return response_text

    async def send_message_json(
        self,
        system_prompt: str,
        user_message: str,
    ) -> dict:
        """Send a message to Claude and parse the response as JSON.

        The system prompt MUST instruct Claude to return valid JSON.
        The SDK has no native output_format field — JSON must be requested
        in the system prompt and parsed manually.

        Args:
            system_prompt: System prompt (must request JSON output).
            user_message: The user message to send.

        Returns:
            The parsed JSON response as a dictionary.
        """
        text = await self.send_message(system_prompt, user_message)

        # Try multiple strategies to extract JSON from the response:
        # 1. Try to parse the raw text directly (cleanest case)
        # 2. Extract JSON from ```json ... ``` code fences
        # 3. Extract JSON from ``` ... ``` code fences
        # 4. Find the first balanced { ... } JSON object in the text

        cleaned = text.strip()

        # Strategy 1: Direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from ```json ... ``` code fence
        json_fence = re.search(r"```json\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
        if json_fence:
            try:
                return json.loads(json_fence.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 3: Extract from ``` ... ``` code fence
        fence = re.search(r"```\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 4: Find first balanced JSON object via brace counting
        json_obj = _extract_first_json_object(cleaned)
        if json_obj is not None:
            try:
                return json.loads(json_obj)
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"Failed to parse Claude response as JSON.\nRaw response: {text[:500]}"
        )

    def is_available(self) -> bool:
        """Check if the Claude CLI is available on PATH."""
        return shutil.which("claude") is not None
