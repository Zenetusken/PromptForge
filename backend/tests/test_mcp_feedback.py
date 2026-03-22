"""Tests for synthesis_feedback MCP tool."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.mcp_server import synthesis_feedback
from app.models import Optimization
from app.schemas.mcp_models import FeedbackOutput

pytestmark = pytest.mark.asyncio


async def test_feedback_thumbs_up(db_session):
    """Valid thumbs_up feedback returns FeedbackOutput."""
    opt_id = str(uuid.uuid4())
    opt = Optimization(
        id=opt_id,
        raw_prompt="Test prompt for feedback.",
        optimized_prompt="Optimized test prompt.",
        task_type="coding",
        strategy_used="auto",
        status="completed",
    )
    db_session.add(opt)
    await db_session.commit()

    with (
        patch("app.tools.feedback.async_session_factory") as mock_factory,
        patch("app.tools.feedback.notify_event_bus", new_callable=AsyncMock) as mock_notify,
    ):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await synthesis_feedback(
            optimization_id=opt_id,
            rating="thumbs_up",
            comment="Great optimization!",
        )

    assert isinstance(result, FeedbackOutput)
    assert result.feedback_id
    assert result.optimization_id == opt_id
    assert result.rating == "thumbs_up"
    assert result.strategy_affinity_updated is True

    # Verify event bus was notified
    mock_notify.assert_called_once()
    call_args = mock_notify.call_args
    assert call_args[0][0] == "feedback_submitted"
    assert call_args[0][1]["optimization_id"] == opt_id
    assert call_args[0][1]["rating"] == "thumbs_up"


async def test_feedback_thumbs_down(db_session):
    """Valid thumbs_down feedback returns FeedbackOutput."""
    opt_id = str(uuid.uuid4())
    opt = Optimization(
        id=opt_id,
        raw_prompt="Test prompt for negative feedback.",
        optimized_prompt="Optimized negative test.",
        task_type="writing",
        strategy_used="chain-of-thought",
        status="completed",
    )
    db_session.add(opt)
    await db_session.commit()

    with (
        patch("app.tools.feedback.async_session_factory") as mock_factory,
        patch("app.tools.feedback.notify_event_bus", new_callable=AsyncMock),
    ):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await synthesis_feedback(
            optimization_id=opt_id,
            rating="thumbs_down",
        )

    assert result.rating == "thumbs_down"
    assert result.strategy_affinity_updated is True


async def test_feedback_invalid_optimization_id(db_session):
    """Raises ValueError for nonexistent optimization."""
    with (
        patch("app.tools.feedback.async_session_factory") as mock_factory,
        patch("app.tools.feedback.notify_event_bus", new_callable=AsyncMock),
    ):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ValueError):
            await synthesis_feedback(
                optimization_id="nonexistent-optimization-id",
                rating="thumbs_up",
            )
