"""Event contracts for TextForge — typed schemas for inter-app communication."""

from __future__ import annotations

from pydantic import BaseModel

from kernel.bus.contracts import EventContract


class TransformCompletedPayload(BaseModel):
    """Payload for textforge:transform.completed."""

    transform_id: str
    transform_type: str
    input_length: int = 0
    output_length: int = 0


class AutoSimplifyCompletedPayload(BaseModel):
    """Payload for textforge:auto-simplify.completed."""

    optimization_id: str
    transform_id: str
    improvement_delta: float = 0.0


TEXTFORGE_CONTRACTS: list[EventContract] = [
    EventContract(
        event_type="textforge:transform.completed",
        source_app="textforge",
        payload_schema=TransformCompletedPayload,
    ),
    EventContract(
        event_type="textforge:auto-simplify.completed",
        source_app="textforge",
        payload_schema=AutoSimplifyCompletedPayload,
    ),
]
