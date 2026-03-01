"""Event contracts for PromptForge — typed schemas for inter-app communication."""

from __future__ import annotations

from pydantic import BaseModel

from kernel.bus.contracts import EventContract


class OptimizationStartedPayload(BaseModel):
    """Payload for promptforge:optimization.started."""

    optimization_id: str
    raw_prompt: str
    project: str | None = None
    strategy: str | None = None


class OptimizationCompletedPayload(BaseModel):
    """Payload for promptforge:optimization.completed."""

    optimization_id: str
    overall_score: float | None = None
    strategy: str | None = None
    project: str | None = None
    duration_ms: int | None = None


class PromptCreatedPayload(BaseModel):
    """Payload for promptforge:prompt.created."""

    prompt_id: str
    project_id: str | None = None
    content_preview: str = ""


class PromptUpdatedPayload(BaseModel):
    """Payload for promptforge:prompt.updated."""

    prompt_id: str
    project_id: str | None = None
    version: int = 1


PROMPTFORGE_CONTRACTS: list[EventContract] = [
    EventContract(
        event_type="promptforge:optimization.started",
        source_app="promptforge",
        payload_schema=OptimizationStartedPayload,
    ),
    EventContract(
        event_type="promptforge:optimization.completed",
        source_app="promptforge",
        payload_schema=OptimizationCompletedPayload,
    ),
    EventContract(
        event_type="promptforge:prompt.created",
        source_app="promptforge",
        payload_schema=PromptCreatedPayload,
    ),
    EventContract(
        event_type="promptforge:prompt.updated",
        source_app="promptforge",
        payload_schema=PromptUpdatedPayload,
    ),
]
