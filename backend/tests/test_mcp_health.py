"""Tests for synthesis_health MCP tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp_server import synthesis_health
from app.schemas.mcp_models import HealthOutput

pytestmark = pytest.mark.asyncio


def _mock_routing(provider_name=None, sampling_capable=None, tiers=None):
    """Create a mock RoutingManager with configurable state."""
    state = MagicMock()
    state.provider_name = provider_name
    state.sampling_capable = sampling_capable

    rm = MagicMock()
    rm.state = state
    rm.available_tiers = tiers or ["passthrough"]
    return rm


async def test_health_with_provider():
    """Health returns 'healthy' when a provider is available."""
    with (
        patch("app.tools._shared._routing", _mock_routing(
            provider_name="claude_cli",
            sampling_capable=True,
            tiers=["internal", "sampling", "passthrough"],
        )),
        patch("app.tools.health.async_session_factory") as mock_factory,
        patch("app.tools.health.StrategyLoader") as mock_sl,
    ):
        mock_sl.return_value.list_strategies.return_value = ["auto", "chain-of-thought"]

        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock OptimizationService
        with patch("app.tools.health.OptimizationService") as mock_opt_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={"total": 42, "items": []})
            mock_svc.get_recent_error_counts = AsyncMock(return_value={"last_hour": 2, "last_24h": 5})
            mock_opt_svc_cls.return_value = mock_svc

            # Mock db.execute for avg score query AND total_24h count query
            mock_avg_scalar = MagicMock()
            mock_avg_scalar.scalar.return_value = 7.5
            mock_count_scalar = MagicMock()
            mock_count_scalar.scalar.return_value = 100
            mock_db.execute = AsyncMock(side_effect=[mock_avg_scalar, mock_count_scalar])

            result = await synthesis_health()

    assert isinstance(result, HealthOutput)
    assert result.status == "healthy"
    assert result.provider == "claude_cli"
    assert "internal" in result.available_tiers
    assert result.sampling_capable is True
    assert result.total_optimizations == 42
    assert "auto" in result.available_strategies
    assert "chain-of-thought" in result.available_strategies
    assert result.recent_error_rate == 0.05  # 5 failed / 100 total in 24h


async def test_health_degraded_no_provider():
    """Health returns 'degraded' when no provider is available."""
    with (
        patch("app.tools._shared._routing", _mock_routing(
            provider_name=None,
            sampling_capable=False,
            tiers=["passthrough"],
        )),
        patch("app.tools.health.async_session_factory") as mock_factory,
        patch("app.tools.health.StrategyLoader") as mock_sl,
    ):
        mock_sl.return_value.list_strategies.return_value = ["auto"]

        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tools.health.OptimizationService") as mock_opt_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={"total": 0, "items": []})
            mock_svc.get_recent_error_counts = AsyncMock(return_value={"last_hour": 0, "last_24h": 0})
            mock_opt_svc_cls.return_value = mock_svc

            result = await synthesis_health()

    assert result.status == "degraded"
    assert result.provider is None
    assert result.available_tiers == ["passthrough"]
    assert result.sampling_capable is False
    assert result.total_optimizations == 0


async def test_health_strategies_fallback():
    """Strategy loading failure returns empty list (no crash)."""
    with (
        patch("app.tools._shared._routing", _mock_routing(provider_name="test")),
        patch("app.tools.health.async_session_factory") as mock_factory,
        patch("app.tools.health.StrategyLoader") as mock_sl,
    ):
        mock_sl.side_effect = Exception("filesystem error")

        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tools.health.OptimizationService") as mock_opt_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={"total": 0, "items": []})
            mock_svc.get_recent_error_counts = AsyncMock(return_value={"last_hour": 0, "last_24h": 0})
            mock_opt_svc_cls.return_value = mock_svc

            result = await synthesis_health()

    assert result.available_strategies == []
    assert result.status == "healthy"  # provider present = healthy
