"""Event contracts for kernel Knowledge Base — typed schemas for knowledge changes."""

from __future__ import annotations

from pydantic import BaseModel

from kernel.bus.contracts import EventContract


class ProfileUpdatedPayload(BaseModel):
    """Payload for kernel:knowledge.profile_updated."""

    profile_id: str
    app_id: str
    entity_id: str
    changed_fields: list[str] = []


class SourceAddedPayload(BaseModel):
    """Payload for kernel:knowledge.source_added."""

    source_id: str
    profile_id: str
    title: str
    source_type: str = "document"


class SourceUpdatedPayload(BaseModel):
    """Payload for kernel:knowledge.source_updated."""

    source_id: str
    profile_id: str
    changed_fields: list[str] = []


class SourceRemovedPayload(BaseModel):
    """Payload for kernel:knowledge.source_removed."""

    source_id: str
    profile_id: str


KNOWLEDGE_CONTRACTS: list[EventContract] = [
    EventContract(
        event_type="kernel:knowledge.profile_updated",
        source_app="kernel",
        payload_schema=ProfileUpdatedPayload,
    ),
    EventContract(
        event_type="kernel:knowledge.source_added",
        source_app="kernel",
        payload_schema=SourceAddedPayload,
    ),
    EventContract(
        event_type="kernel:knowledge.source_updated",
        source_app="kernel",
        payload_schema=SourceUpdatedPayload,
    ),
    EventContract(
        event_type="kernel:knowledge.source_removed",
        source_app="kernel",
        payload_schema=SourceRemovedPayload,
    ),
]
