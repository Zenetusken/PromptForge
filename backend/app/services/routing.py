"""Centralized routing decision engine for the optimization pipeline.

Provides a pure function ``resolve_route()`` that maps system state and
request context to one of three execution tiers:

  internal   — use a locally detected LLM provider (CLI or API)
  sampling   — delegate to an MCP client via sampling/createMessage
  passthrough — return assembled prompt for external LLM processing

Priority chain (highest wins):
  1. force_passthrough  → passthrough (unconditional)
  2. force_sampling     → sampling (if eligible) or degrade
  3. internal provider  → internal
  4. auto sampling      → sampling (MCP caller only, degraded from internal)
  5. passthrough        → fallback (degraded from internal)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from app.providers.base import LLMProvider


# ---------------------------------------------------------------------------
# Data model — all frozen (immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingState:
    """Snapshot of the server's capability state at the time of a request.

    Attributes:
        provider: The detected LLM provider instance, or None.
        provider_name: Human-readable provider name (e.g. "claude-cli").
        sampling_capable: Whether the MCP client supports sampling.
            ``None`` means unknown or stale — treated as ``False``.
        mcp_connected: Whether an MCP client is currently connected.
        last_capability_update: When sampling_capable was last refreshed.
        last_activity: When the MCP client last communicated.
    """

    provider: LLMProvider | None = None
    provider_name: str | None = None
    sampling_capable: bool | None = None
    mcp_connected: bool = False
    last_capability_update: datetime | None = None
    last_activity: datetime | None = None


@dataclass(frozen=True)
class RoutingContext:
    """Per-request context that influences the routing decision.

    Attributes:
        preferences: User preference snapshot (may contain
            ``force_passthrough`` and ``force_sampling`` keys).
        caller: Where the request originated — ``"rest"`` for the HTTP API,
            ``"mcp"`` for an MCP tool invocation.
    """

    preferences: dict[str, Any] = field(default_factory=dict)
    caller: Literal["rest", "mcp"] = "rest"


@dataclass(frozen=True)
class RoutingDecision:
    """The resolved execution tier and associated metadata.

    Attributes:
        tier: The selected execution tier.
        provider: The LLM provider to use (only set for ``internal`` tier).
        provider_name: Name of the provider, if any.
        reason: Human-readable explanation of why this tier was chosen.
        degraded_from: If the decision was a fallback, the tier that was
            originally requested or expected.
    """

    tier: Literal["internal", "sampling", "passthrough"]
    provider: LLMProvider | None = None
    provider_name: str | None = None
    reason: str = ""
    degraded_from: str | None = None


# ---------------------------------------------------------------------------
# Pure resolver
# ---------------------------------------------------------------------------


def resolve_route(state: RoutingState, ctx: RoutingContext) -> RoutingDecision:
    """Determine the execution tier for a pipeline request.

    This is a **pure function** — no I/O, no logging, no side effects.
    All inputs are frozen dataclasses; the output is a frozen dataclass.
    """
    pipeline = ctx.preferences.get("pipeline", {})
    force_passthrough = bool(pipeline.get("force_passthrough"))
    force_sampling = bool(pipeline.get("force_sampling"))

    # Tier 1: force_passthrough always wins
    if force_passthrough:
        return RoutingDecision(
            tier="passthrough",
            reason="force_passthrough enabled",
        )

    # Tier 2: force_sampling — requires MCP caller + sampling capability
    if force_sampling:
        sampling_ok = (
            ctx.caller == "mcp"
            and state.sampling_capable is True
            and state.mcp_connected
        )
        if sampling_ok:
            return RoutingDecision(
                tier="sampling",
                reason="force_sampling enabled, MCP client supports sampling",
            )
        # Degrade: try internal, then passthrough
        if state.provider is not None:
            return RoutingDecision(
                tier="internal",
                provider=state.provider,
                provider_name=state.provider_name,
                reason="force_sampling degraded: sampling unavailable, using internal provider",
                degraded_from="sampling",
            )
        return RoutingDecision(
            tier="passthrough",
            reason="force_sampling degraded: sampling unavailable, no internal provider",
            degraded_from="sampling",
        )

    # Tier 3: internal provider available
    if state.provider is not None:
        return RoutingDecision(
            tier="internal",
            provider=state.provider,
            provider_name=state.provider_name,
            reason="internal provider available",
        )

    # Tier 4: auto sampling — MCP caller with sampling capability
    if (
        ctx.caller == "mcp"
        and state.sampling_capable is True
        and state.mcp_connected
    ):
        return RoutingDecision(
            tier="sampling",
            reason="no internal provider, MCP client supports sampling",
            degraded_from="internal",
        )

    # Tier 5: passthrough fallback
    return RoutingDecision(
        tier="passthrough",
        reason="no internal provider or sampling available",
        degraded_from="internal",
    )
