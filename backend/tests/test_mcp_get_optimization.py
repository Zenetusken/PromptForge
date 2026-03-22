"""Tests for synthesis_get_optimization MCP tool."""

import uuid

from unittest.mock import AsyncMock, patch

import pytest

from app.mcp_server import synthesis_get_optimization
from app.models import Optimization
from app.schemas.mcp_models import OptimizationDetailOutput

pytestmark = pytest.mark.asyncio


async def test_get_optimization_by_id(db_session):
    """Retrieve optimization by primary ID."""
    opt_id = str(uuid.uuid4())
    opt = Optimization(
        id=opt_id,
        raw_prompt="Original prompt text for retrieval test.",
        optimized_prompt="Optimized prompt text for retrieval test.",
        task_type="coding",
        strategy_used="chain-of-thought",
        changes_summary="Restructured for clarity",
        score_clarity=8.0,
        score_specificity=7.5,
        score_structure=9.0,
        score_faithfulness=8.0,
        score_conciseness=7.0,
        overall_score=7.9,
        status="completed",
        scoring_mode="independent",
        trace_id=str(uuid.uuid4()),
    )
    db_session.add(opt)
    await db_session.commit()

    with patch("app.tools.get_optimization.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await synthesis_get_optimization(optimization_id=opt_id)

    assert isinstance(result, OptimizationDetailOutput)
    assert result.id == opt_id
    assert result.raw_prompt == "Original prompt text for retrieval test."
    assert result.optimized_prompt == "Optimized prompt text for retrieval test."
    assert result.task_type == "coding"
    assert result.strategy_used == "chain-of-thought"
    assert result.scores is not None
    assert result.scores["clarity"] == 8.0
    assert result.overall_score == 7.9
    assert result.has_feedback is False
    assert result.refinement_versions == 0


async def test_get_optimization_by_trace_id(db_session):
    """Falls back to trace_id lookup when ID doesn't match."""
    trace_id = str(uuid.uuid4())
    opt = Optimization(
        id=str(uuid.uuid4()),
        raw_prompt="Trace lookup test prompt with enough chars.",
        optimized_prompt="Trace lookup optimized result.",
        task_type="writing",
        strategy_used="auto",
        status="completed",
        trace_id=trace_id,
    )
    db_session.add(opt)
    await db_session.commit()

    with patch("app.tools.get_optimization.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await synthesis_get_optimization(optimization_id=trace_id)

    assert isinstance(result, OptimizationDetailOutput)
    assert result.task_type == "writing"


async def test_get_optimization_not_found(db_session):
    """Raises ValueError when optimization doesn't exist."""
    with patch("app.tools.get_optimization.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="Optimization not found"):
            await synthesis_get_optimization(optimization_id="nonexistent-id")
