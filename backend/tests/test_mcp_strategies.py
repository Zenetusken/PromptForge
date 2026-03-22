"""Tests for synthesis_strategies MCP tool."""

from unittest.mock import patch

import pytest

from app.mcp_server import synthesis_strategies
from app.schemas.mcp_models import StrategiesOutput

pytestmark = pytest.mark.asyncio


async def test_strategies_returns_list():
    """synthesis_strategies returns a StrategiesOutput with strategy metadata."""
    with patch("app.tools.strategies.StrategyLoader") as mock_sl:
        mock_sl.return_value.list_with_metadata.return_value = [
            {"name": "auto", "tagline": "Automatic selection", "description": "Let the system choose."},
            {"name": "chain-of-thought", "tagline": "Step by step", "description": "Break down reasoning."},
            {"name": "few-shot", "tagline": "Learn by example", "description": "Provide examples."},
        ]

        result = await synthesis_strategies()

    assert isinstance(result, StrategiesOutput)
    assert len(result.strategies) == 3
    assert result.strategies[0].name == "auto"
    assert result.strategies[0].tagline == "Automatic selection"
    assert result.strategies[1].name == "chain-of-thought"
    assert result.strategies[2].name == "few-shot"


async def test_strategies_empty():
    """Returns empty list when no strategy files exist."""
    with patch("app.tools.strategies.StrategyLoader") as mock_sl:
        mock_sl.return_value.list_with_metadata.return_value = []

        result = await synthesis_strategies()

    assert isinstance(result, StrategiesOutput)
    assert result.strategies == []


async def test_strategies_missing_metadata_fields():
    """Missing tagline/description default to empty string."""
    with patch("app.tools.strategies.StrategyLoader") as mock_sl:
        mock_sl.return_value.list_with_metadata.return_value = [
            {"name": "auto"},  # no tagline or description
        ]

        result = await synthesis_strategies()

    assert len(result.strategies) == 1
    assert result.strategies[0].name == "auto"
    assert result.strategies[0].tagline == ""
    assert result.strategies[0].description == ""
