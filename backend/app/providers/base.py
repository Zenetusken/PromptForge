from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Awaitable, Callable


def parse_json_robust(text: str) -> dict:
    """3-strategy JSON parsing used by all providers and the explore stage.

    Claude models often wrap JSON in markdown code blocks. This handles all
    common output formats without losing structured data.

    1. Direct parse — model returned bare JSON
    2. Extract ```json ... ``` or ``` ... ``` code block, then parse
    3. Extract first { ... } substring via regex, then parse
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            pass

    raise ValueError(f"Could not parse JSON from response: {text[:200]}...")


MODEL_ROUTING = {
    "explore": "claude-haiku-4-5",
    "analyze": "claude-sonnet-4-6",
    "strategy": "claude-opus-4-6",
    "optimize": "claude-opus-4-6",
    "validate": "claude-sonnet-4-6",
}


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Awaitable[str]]


@dataclass
class AgenticResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    output: dict | None = None  # Structured output captured via submit_result tool or SDK output_format


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...

    @abstractmethod
    async def complete(self, system: str, user: str, model: str) -> str:
        """Single-shot completion. Returns full response text."""
        ...

    @abstractmethod
    def stream(self, system: str, user: str, model: str) -> AsyncGenerator[str, None]:
        """Streaming completion. Yields text chunks as they arrive."""
        ...

    @abstractmethod
    async def complete_json(
        self,
        system: str,
        user: str,
        model: str,
        schema: dict | None = None,
    ) -> dict:
        """Structured JSON output.

        When ``schema`` is provided (a JSON Schema dict with
        ``additionalProperties: false`` on all objects), providers MUST use
        native schema enforcement (API output_config.format or SDK equivalent).

        When ``schema`` is None, falls back to 3-strategy text parsing:
        1. Parse raw response as JSON
        2. Extract first ```json ... ``` code block, parse it
        3. Extract first { ... } substring via regex, parse it
        """
        ...

    @abstractmethod
    async def complete_agentic(
        self,
        system: str,
        user: str,
        model: str,
        tools: list[ToolDefinition],
        max_turns: int = 20,
        on_tool_call: Callable[[str, dict], None] | None = None,
        output_schema: dict | None = None,
    ) -> AgenticResult:
        """Agentic tool-calling loop.

        If output_schema is provided, a reserved 'submit_result' tool is injected
        automatically. When the model calls it, its input (matching the schema) is
        returned as AgenticResult.output — no text parsing required. This is the
        canonical Anthropic pattern for structured output from agentic loops.
        """
        ...
