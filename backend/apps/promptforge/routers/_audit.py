"""Shared audit logging helper for PromptForge routers."""

from kernel.bus.helpers import kernel_audit_log


async def audit_log(
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Log an audit entry for PromptForge. Delegates to kernel helper."""
    await kernel_audit_log("promptforge", action, resource_type, resource_id, details)
