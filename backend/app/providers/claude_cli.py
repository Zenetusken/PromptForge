"""Claude CLI subprocess provider."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TypeVar

from pydantic import BaseModel

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ClaudeCLIProvider(LLMProvider):
    """LLM provider that calls the claude CLI subprocess."""

    name = "claude_cli"

    async def complete_parsed(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        output_format: type[T],
        max_tokens: int = 16384,
        effort: str | None = None,
    ) -> T:
        """Run claude CLI and parse JSON output as a Pydantic model.

        The JSON schema is embedded in the system prompt so the CLI produces
        structured output (the CLI does not natively support output_format).
        Raises RuntimeError on non-zero subprocess exit code.
        """
        schema = output_format.model_json_schema()
        augmented_system = (
            f"{system_prompt}\n\n"
            "IMPORTANT: Respond with a single valid JSON object that conforms "
            "exactly to the following JSON schema. Do not include any other text.\n"
            f"Schema:\n{json.dumps(schema, indent=2)}"
        )

        cmd = [
            "claude",
            "-p",
            user_message,
            "--model",
            model,
            "--system-prompt",
            augmented_system,
            "--output-format",
            "json",
        ]

        logger.debug("claude_cli executing model=%s", model)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {proc.returncode}: {stderr.decode(errors='replace')}"
            )

        raw = json.loads(stdout.decode())

        # The CLI --output-format json returns a wrapper: {"type":"result", "result":"...", ...}
        # Extract the actual content from the "result" field
        content = raw
        if isinstance(raw, dict) and "result" in raw and isinstance(raw["result"], str):
            content_str = raw["result"].strip()
            # Strip markdown code fencing if present
            if content_str.startswith("```"):
                # Remove opening fence (```json or ```)
                first_newline = content_str.find("\n")
                if first_newline != -1:
                    content_str = content_str[first_newline + 1:]
                # Remove closing fence
                if content_str.rstrip().endswith("```"):
                    content_str = content_str.rstrip()[:-3].rstrip()
            try:
                content = json.loads(content_str)
            except json.JSONDecodeError:
                logger.error("Failed to parse CLI result as JSON: %s", content_str[:200])
                raise RuntimeError(
                    f"Claude CLI returned invalid JSON in result field. "
                    f"First 200 chars: {content_str[:200]}"
                )

        result = output_format.model_validate(content)

        logger.info(
            "claude_cli complete_parsed model=%s duration_ms=%s",
            model,
            raw.get("duration_ms") if isinstance(raw, dict) else "?",
        )
        return result
