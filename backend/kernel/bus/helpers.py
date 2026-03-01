"""Publish helper — convenience wrapper for EventBus.publish().

Avoids boilerplate in every publish call site by resolving the bus
from the kernel registry and handling graceful fallback.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def publish_event(event_type: str, data: dict, source_app: str) -> None:
    """Publish an event to the kernel EventBus.

    Resolves the bus from the kernel registry. If the bus is unavailable
    (e.g. kernel not yet booted, tests without full setup), logs a debug
    message and returns silently.

    Parameters
    ----------
    event_type:
        Event type string (e.g. ``"promptforge:optimization.completed"``).
    data:
        Event payload dict matching the registered contract schema.
    source_app:
        App ID of the publisher.
    """
    try:
        from kernel.registry.app_registry import get_app_registry

        registry = get_app_registry()
        kernel = registry.kernel
        if kernel is None or not hasattr(kernel, "services"):
            logger.debug("publish_event: kernel not available, skipping %r", event_type)
            return

        bus = kernel.services.get("bus")
        if bus is None:
            logger.debug("publish_event: EventBus not registered, skipping %r", event_type)
            return

        bus.publish(event_type, data, source_app)
    except Exception:
        logger.debug("publish_event: failed to publish %r", event_type, exc_info=True)


async def kernel_audit_log(
    app_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Log an audit entry for any app and publish a bus event.

    Opens its own DB session (fire-and-forget). Never raises — audit failures
    are logged at debug level so they never block the caller's request.
    """
    try:
        from app.database import async_session_factory
        from kernel.repositories.audit import AuditRepository

        async with async_session_factory() as session:
            repo = AuditRepository(session)
            await repo.log_action(
                app_id,
                action,
                resource_type,
                resource_id=resource_id,
                details=details,
            )
            await session.commit()

        publish_event(
            "kernel:audit.logged",
            {
                "app_id": app_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
            "kernel",
        )
    except Exception:
        logger.debug(
            "Audit log failed: app=%s action=%s resource_type=%s resource_id=%s",
            app_id,
            action,
            resource_type,
            resource_id,
            exc_info=True,
        )
