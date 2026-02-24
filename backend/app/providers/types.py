"""Unified request/response models for the provider abstraction layer.

These frozen dataclasses provide a provider-agnostic interface for LLM
completions.  ``complete`` / ``complete_json`` are the primary entry
points used by pipeline services; ``send_message`` / ``send_message_json``
are retained for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompletionRequest:
    """Provider-agnostic completion request."""

    system_prompt: str
    user_message: str
    max_tokens: int | None = None  # None = provider default
    temperature: float | None = None


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption for a single completion."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None


@dataclass(frozen=True)
class CompletionResponse:
    """Provider-agnostic completion response."""

    text: str
    model: str
    provider: str
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class StreamChunk:
    """A single chunk from a streaming completion."""

    text: str
    done: bool = False
    usage: TokenUsage | None = None
