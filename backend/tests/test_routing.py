"""Tests for the routing decision engine.

Covers all 5 tiers of the priority chain:
  force passthrough > force sampling > internal provider > auto sampling > passthrough fallback
"""

from __future__ import annotations

from typing import Literal
from unittest.mock import MagicMock

import pytest

from app.services.routing import RoutingContext, RoutingState, resolve_route

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(
    *,
    provider_name: str | None = None,
    sampling_capable: bool | None = None,
    mcp_connected: bool = False,
) -> RoutingState:
    provider = MagicMock(name=provider_name) if provider_name else None
    return RoutingState(
        provider=provider,
        provider_name=provider_name,
        sampling_capable=sampling_capable,
        mcp_connected=mcp_connected,
    )


def _ctx(
    *,
    caller: Literal["rest", "mcp"] = "rest",
    force_passthrough: bool = False,
    force_sampling: bool = False,
) -> RoutingContext:
    return RoutingContext(
        caller=caller,
        preferences={
            "pipeline": {
                "force_passthrough": force_passthrough,
                "force_sampling": force_sampling,
            },
        },
    )


# ---------------------------------------------------------------------------
# Tier 1 — force_passthrough always wins
# ---------------------------------------------------------------------------


class TestForcePassthrough:
    """force_passthrough=True should always return tier='passthrough'."""

    def test_with_provider(self) -> None:
        state = _state(provider_name="claude-cli")
        ctx = _ctx(force_passthrough=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.reason
        assert decision.provider is None

    def test_without_provider(self) -> None:
        state = _state()
        ctx = _ctx(force_passthrough=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"

    def test_with_sampling_available(self) -> None:
        state = _state(sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="mcp", force_passthrough=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"


# ---------------------------------------------------------------------------
# Tier 2 — force_sampling (may degrade)
# ---------------------------------------------------------------------------


class TestForceSampling:
    """force_sampling=True should return sampling when possible, degrade otherwise."""

    def test_mcp_caller_with_sampling(self) -> None:
        state = _state(sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="mcp", force_sampling=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "sampling"
        assert decision.degraded_from is None

    def test_rest_caller_degrades_to_internal(self) -> None:
        state = _state(provider_name="anthropic-api", sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="rest", force_sampling=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "internal"
        assert decision.degraded_from == "sampling"

    def test_rest_caller_degrades_to_passthrough(self) -> None:
        state = _state(sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="rest", force_sampling=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.degraded_from == "sampling"

    def test_mcp_not_connected_degrades(self) -> None:
        state = _state(provider_name="claude-cli", sampling_capable=True, mcp_connected=False)
        ctx = _ctx(caller="mcp", force_sampling=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "internal"
        assert decision.degraded_from == "sampling"

    def test_sampling_none_degrades(self) -> None:
        state = _state(provider_name="claude-cli", sampling_capable=None, mcp_connected=True)
        ctx = _ctx(caller="mcp", force_sampling=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "internal"
        assert decision.degraded_from == "sampling"


# ---------------------------------------------------------------------------
# Tier 3 — internal provider
# ---------------------------------------------------------------------------


class TestInternalProvider:
    """When a provider exists and nothing is forced, use internal."""

    def test_cli_provider(self) -> None:
        state = _state(provider_name="claude-cli")
        ctx = _ctx()
        decision = resolve_route(state, ctx)
        assert decision.tier == "internal"
        assert decision.provider is not None
        assert decision.degraded_from is None

    def test_api_provider(self) -> None:
        state = _state(provider_name="anthropic-api")
        ctx = _ctx()
        decision = resolve_route(state, ctx)
        assert decision.tier == "internal"
        assert decision.provider is not None

    def test_provider_preferred_over_sampling(self) -> None:
        state = _state(provider_name="claude-cli", sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="mcp")
        decision = resolve_route(state, ctx)
        assert decision.tier == "internal"


# ---------------------------------------------------------------------------
# Tier 4 — auto sampling
# ---------------------------------------------------------------------------


class TestAutoSampling:
    """MCP caller with sampling available but no provider → auto sampling."""

    def test_mcp_no_provider_gets_sampling(self) -> None:
        state = _state(sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="mcp")
        decision = resolve_route(state, ctx)
        assert decision.tier == "sampling"
        assert decision.degraded_from == "internal"

    def test_rest_never_reaches_sampling(self) -> None:
        state = _state(sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="rest")
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.tier != "sampling"


# ---------------------------------------------------------------------------
# Tier 5 — passthrough fallback
# ---------------------------------------------------------------------------


class TestPassthroughFallback:
    """Nothing available → passthrough."""

    def test_nothing_available(self) -> None:
        state = _state()
        ctx = _ctx()
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.degraded_from == "internal"

    def test_sampling_not_connected(self) -> None:
        state = _state(sampling_capable=True, mcp_connected=False)
        ctx = _ctx(caller="mcp")
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.degraded_from == "internal"

    def test_sampling_none(self) -> None:
        state = _state(sampling_capable=None, mcp_connected=True)
        ctx = _ctx(caller="mcp")
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.degraded_from == "internal"


# ---------------------------------------------------------------------------
# Dataclass properties
# ---------------------------------------------------------------------------


class TestDecisionProperties:
    """Verify immutability of decision and state objects."""

    def test_decision_is_frozen(self) -> None:
        state = _state(provider_name="claude-cli")
        ctx = _ctx()
        decision = resolve_route(state, ctx)
        with pytest.raises(AttributeError):
            decision.tier = "passthrough"  # type: ignore[misc]

    def test_state_is_frozen(self) -> None:
        state = _state(provider_name="claude-cli")
        with pytest.raises(AttributeError):
            state.provider_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Additional edge-case scenarios."""

    def test_mcp_no_provider_not_connected_force_sampling(self) -> None:
        """force_sampling with sampling_capable but MCP disconnected and no provider → passthrough degraded."""
        state = _state(sampling_capable=True, mcp_connected=False)
        ctx = _ctx(caller="mcp", force_sampling=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.degraded_from == "sampling"

    def test_both_force_flags_passthrough_wins(self) -> None:
        """When both force flags are set, force_passthrough (tier 1) wins."""
        state = _state(provider_name="claude-cli", sampling_capable=True, mcp_connected=True)
        ctx = _ctx(caller="mcp", force_passthrough=True, force_sampling=True)
        decision = resolve_route(state, ctx)
        assert decision.tier == "passthrough"
        assert decision.degraded_from is None
