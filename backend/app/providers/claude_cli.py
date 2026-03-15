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
            "--max-tokens",
            str(max_tokens),
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
        result = output_format.model_validate(raw)

        logger.info("claude_cli complete_parsed model=%s returncode=0", model)
        return result
