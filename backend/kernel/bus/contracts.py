"""Event contracts — typed schemas for inter-app communication.

Apps register contracts during startup. The bus validates published
events against registered contracts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventContract:
    """A typed event contract defining the shape of events.

    Parameters
    ----------
    event_type:
        Unique event type string (e.g. ``"prompt:optimized"``).
    source_app:
        App ID that publishes this event.
    payload_schema:
        Pydantic model for the event payload.
    response_schema:
        Optional Pydantic model for request/response events.
    """

    event_type: str
    source_app: str
    payload_schema: type[BaseModel]
    response_schema: type[BaseModel] | None = None


class ContractRegistry:
    """Registry of typed event contracts for validation and introspection."""

    def __init__(self) -> None:
        self._contracts: dict[str, EventContract] = {}

    def register(self, contract: EventContract) -> None:
        """Register an event contract."""
        if contract.event_type in self._contracts:
            logger.warning(
                "Overwriting contract for %r (was from %s, now from %s)",
                contract.event_type,
                self._contracts[contract.event_type].source_app,
                contract.source_app,
            )
        self._contracts[contract.event_type] = contract
        logger.debug(
            "Registered contract: %r from %s", contract.event_type, contract.source_app
        )

    def validate_publish(self, event_type: str, data: dict) -> None:
        """Validate event data against the registered contract.

        Raises
        ------
        ValueError
            If no contract is registered for the event type.
        ValidationError
            If the data doesn't match the payload schema.
        """
        contract = self._contracts.get(event_type)
        if not contract:
            raise ValueError(f"No contract registered for event type {event_type!r}")
        contract.payload_schema(**data)

    def get_contract(self, event_type: str) -> EventContract | None:
        """Get a contract by event type."""
        return self._contracts.get(event_type)

    def get_contracts(self) -> list[EventContract]:
        """List all registered contracts."""
        return list(self._contracts.values())

    def to_json(self) -> list[dict]:
        """Serialize all contracts for API responses."""
        return [
            {
                "event_type": c.event_type,
                "source_app": c.source_app,
                "payload_schema": c.payload_schema.model_json_schema(),
                "response_schema": (
                    c.response_schema.model_json_schema() if c.response_schema else None
                ),
            }
            for c in self._contracts.values()
        ]
