"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    name: str

    @abstractmethod
    async def complete_parsed(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        output_format: type[T],
        max_tokens: int = 16384,
        effort: str | None = None,
    ) -> T:
        """Make an LLM call and return a parsed Pydantic model."""
        ...

    @staticmethod
    def thinking_config(model: str) -> dict:
        """Return thinking configuration based on model.
        Opus/Sonnet: adaptive thinking. Haiku: disabled.
        """
        if "haiku" in model.lower():
            return {"type": "disabled"}
        return {"type": "adaptive"}
