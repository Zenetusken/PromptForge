"""EventBus — backend event bus for inter-app communication.

Supports publish/subscribe and request/response patterns with
app-scoped subscriptions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from kernel.bus.contracts import ContractRegistry

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    """A registered event subscription."""

    id: str
    event_type: str
    handler: Callable
    app_id: str | None = None


class EventBus:
    """Async event bus supporting publish/subscribe and request/response.

    Thread-safe for concurrent async operations within a single event loop.
    """

    def __init__(self, contract_registry: ContractRegistry | None = None) -> None:
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._all_subscriptions: dict[str, Subscription] = {}
        self._contract_registry = contract_registry

    def subscribe(
        self,
        event_type: str,
        handler: Callable,
        app_id: str | None = None,
    ) -> str:
        """Register a handler for an event type.

        Parameters
        ----------
        event_type:
            The event type to subscribe to (e.g. ``"prompt:optimized"``).
        handler:
            Async callable ``(data: dict, source_app: str) -> Any``.
        app_id:
            Optional app ID for the subscription owner (for introspection).

        Returns
        -------
        str
            Subscription ID for later unsubscription.
        """
        sub_id = str(uuid.uuid4())
        sub = Subscription(id=sub_id, event_type=event_type, handler=handler, app_id=app_id)
        self._subscriptions[event_type].append(sub)
        self._all_subscriptions[sub_id] = sub
        logger.debug("Subscribed %s to %r (app=%s)", sub_id[:8], event_type, app_id)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription by ID."""
        sub = self._all_subscriptions.pop(subscription_id, None)
        if sub:
            subs = self._subscriptions.get(sub.event_type, [])
            self._subscriptions[sub.event_type] = [s for s in subs if s.id != subscription_id]
            logger.debug("Unsubscribed %s from %r", subscription_id[:8], sub.event_type)

    # Internal channel used by the SSE bridge to relay all published events.
    SSE_RELAY_CHANNEL = "__sse_relay__"

    def publish(self, event_type: str, data: dict, source_app: str) -> None:
        """Publish an event to all subscribers (fire-and-forget).

        If a ContractRegistry is set and has a contract for this event type,
        the payload is validated before dispatch. Invalid payloads are blocked.
        Events without contracts publish with a debug-level warning.

        Handlers are scheduled as asyncio tasks. Exceptions are logged
        but do not propagate. Events are also forwarded to the SSE relay
        channel so the frontend bridge receives them.
        """
        # Contract validation
        if self._contract_registry and event_type != self.SSE_RELAY_CHANNEL:
            contract = self._contract_registry.get_contract(event_type)
            if contract:
                try:
                    self._contract_registry.validate_publish(event_type, data)
                except Exception:
                    logger.error(
                        "Event %r from %r blocked: payload failed contract validation",
                        event_type, source_app, exc_info=True,
                    )
                    return
            else:
                logger.debug(
                    "Event %r from %r has no registered contract — publishing unvalidated",
                    event_type, source_app,
                )

        subs = self._subscriptions.get(event_type, [])
        for sub in subs:
            asyncio.create_task(
                self._safe_invoke(sub, data, source_app),
                name=f"bus:{event_type}:{sub.id[:8]}",
            )

        # Relay to SSE bridge subscribers (skip if this *is* the relay channel)
        if event_type != self.SSE_RELAY_CHANNEL:
            relay_data = {"event_type": event_type, **data}
            for sub in self._subscriptions.get(self.SSE_RELAY_CHANNEL, []):
                asyncio.create_task(
                    self._safe_invoke(sub, relay_data, source_app),
                    name=f"bus:sse_relay:{sub.id[:8]}",
                )

    async def request(
        self,
        event_type: str,
        data: dict,
        source_app: str,
        timeout: float = 5.0,
    ) -> dict:
        """Send a request and wait for the first handler to respond.

        Parameters
        ----------
        event_type:
            The event type to request.
        data:
            Request payload.
        source_app:
            ID of the app making the request.
        timeout:
            Max seconds to wait for a response.

        Returns
        -------
        dict
            Response from the first handler.

        Raises
        ------
        TimeoutError
            If no handler responds within the timeout.
        ValueError
            If no handlers are subscribed.
        """
        subs = self._subscriptions.get(event_type, [])
        if not subs:
            raise ValueError(f"No handlers subscribed for {event_type!r}")

        handler = subs[0].handler
        try:
            result = await asyncio.wait_for(handler(data, source_app), timeout=timeout)
            return result if isinstance(result, dict) else {"result": result}
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Request to {event_type!r} from {source_app!r} timed out after {timeout}s"
            )

    def list_subscriptions(self) -> list[dict]:
        """List all active subscriptions for introspection."""
        return [
            {
                "id": sub.id,
                "event_type": sub.event_type,
                "app_id": sub.app_id,
            }
            for sub in self._all_subscriptions.values()
        ]

    async def _safe_invoke(self, sub: Subscription, data: dict, source_app: str) -> None:
        """Invoke a handler, catching and logging any errors."""
        try:
            await sub.handler(data, source_app)
        except Exception:
            logger.exception(
                "Handler %s for %r (app=%s) raised an error",
                sub.id[:8], sub.event_type, sub.app_id,
            )
