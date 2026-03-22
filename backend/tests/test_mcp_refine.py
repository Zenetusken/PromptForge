"""Tests for synthesis_refine MCP tool."""

import uuid

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp_server import synthesis_refine
from app.schemas.mcp_models import RefineOutput
from app.services.routing import RoutingDecision

pytestmark = pytest.mark.asyncio


def _mock_routing(tier="internal", provider=None, provider_name=None):
    """Create a mock RoutingManager."""
    decision = RoutingDecision(
        tier=tier,
        provider=provider,
        provider_name=provider_name or (provider.name if provider else None),
        reason=f"test → {tier}",
    )
    rm = MagicMock()
    rm.resolve.return_value = decision
    return rm


async def test_refine_rejects_passthrough():
    """Refinement requires a provider — passthrough tier is rejected."""
    with (
        patch("app.tools._shared._routing", _mock_routing("passthrough")),
        patch("app.tools.refine.PreferencesService") as mock_prefs_cls,
    ):
        mock_prefs = MagicMock()
        mock_prefs.load.return_value = {}
        mock_prefs_cls.return_value = mock_prefs

        with pytest.raises(ValueError, match="requires a local LLM provider"):
            await synthesis_refine(
                optimization_id="opt-123",
                refinement_request="Add more examples",
            )


async def test_refine_optimization_not_found():
    """Raises ValueError when optimization doesn't exist."""
    mock_provider = AsyncMock()
    mock_provider.name = "test_provider"

    with (
        patch("app.tools._shared._routing", _mock_routing(
            "internal", provider=mock_provider, provider_name="test_provider",
        )),
        patch("app.tools.refine.PreferencesService") as mock_prefs_cls,
        patch("app.tools.refine.async_session_factory") as mock_factory,
    ):
        mock_prefs = MagicMock()
        mock_prefs.load.return_value = {}
        mock_prefs_cls.return_value = mock_prefs

        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock empty query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Optimization not found"):
            await synthesis_refine(
                optimization_id="nonexistent-opt",
                refinement_request="Improve structure",
            )


async def test_refine_no_optimized_prompt():
    """Raises ValueError when optimization has no optimized prompt."""
    mock_provider = AsyncMock()
    mock_provider.name = "test_provider"

    mock_opt = MagicMock()
    mock_opt.id = "opt-123"
    mock_opt.optimized_prompt = ""  # empty = no prompt to refine
    mock_opt.status = "pending"

    with (
        patch("app.tools._shared._routing", _mock_routing(
            "internal", provider=mock_provider, provider_name="test_provider",
        )),
        patch("app.tools.refine.PreferencesService") as mock_prefs_cls,
        patch("app.tools.refine.async_session_factory") as mock_factory,
    ):
        mock_prefs = MagicMock()
        mock_prefs.load.return_value = {}
        mock_prefs_cls.return_value = mock_prefs

        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_opt
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="has no optimized prompt"):
            await synthesis_refine(
                optimization_id="opt-123",
                refinement_request="Add error handling",
            )
