"""Tests for FeedbackService — TDD: tests written before implementation."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Feedback, Optimization
from app.services.adaptation_tracker import AdaptationTracker
from app.services.feedback_service import FeedbackService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def opt_id(db_session: AsyncSession) -> str:
    """Insert a sample Optimization and return its id."""
    opt = Optimization(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        raw_prompt="Sample prompt for feedback tests",
        task_type="generation",
        strategy_used="chain-of-thought",
        status="completed",
    )
    db_session.add(opt)
    await db_session.commit()
    await db_session.refresh(opt)
    return opt.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_create_feedback(db_session: AsyncSession, opt_id: str) -> None:
    """create_feedback returns a persisted Feedback with correct fields."""
    svc = FeedbackService(db_session)

    fb = await svc.create_feedback(opt_id, "thumbs_up", comment="Great result!")

    assert fb is not None
    assert isinstance(fb, Feedback)
    assert fb.optimization_id == opt_id
    assert fb.rating == "thumbs_up"
    assert fb.comment == "Great result!"
    assert fb.id is not None
    assert fb.created_at is not None


async def test_create_feedback_invalid_optimization(db_session: AsyncSession) -> None:
    """create_feedback raises ValueError("not found") when optimization does not exist."""
    svc = FeedbackService(db_session)

    with pytest.raises(ValueError, match="not found"):
        await svc.create_feedback("nonexistent-opt-id", "thumbs_up")


async def test_create_feedback_invalid_rating(db_session: AsyncSession, opt_id: str) -> None:
    """create_feedback raises ValueError("Invalid rating") for an unrecognised rating."""
    svc = FeedbackService(db_session)

    with pytest.raises(ValueError, match="Invalid rating"):
        await svc.create_feedback(opt_id, "neutral")


async def test_get_feedback_for_optimization(db_session: AsyncSession, opt_id: str) -> None:
    """get_for_optimization returns the list of Feedback rows ordered newest-first."""
    svc = FeedbackService(db_session)

    await svc.create_feedback(opt_id, "thumbs_up")
    await svc.create_feedback(opt_id, "thumbs_down", comment="Could be better")

    results = await svc.get_for_optimization(opt_id)

    assert isinstance(results, list)
    assert len(results) == 2
    # Most recent first
    assert results[0].created_at >= results[1].created_at


async def test_get_aggregation(db_session: AsyncSession, opt_id: str) -> None:
    """get_aggregation returns correct total, thumbs_up, and thumbs_down counts."""
    svc = FeedbackService(db_session)

    await svc.create_feedback(opt_id, "thumbs_up")
    await svc.create_feedback(opt_id, "thumbs_up")
    await svc.create_feedback(opt_id, "thumbs_down")

    agg = await svc.get_aggregation(opt_id)

    assert agg["total"] == 3
    assert agg["thumbs_up"] == 2
    assert agg["thumbs_down"] == 1


async def test_feedback_triggers_degenerate_check(
    db_session: AsyncSession, opt_id: str,
) -> None:
    """create_feedback calls check_degenerate after updating affinity.

    After enough one-sided feedback, the degenerate check should detect
    the pattern (logged as warning, non-fatal).
    """
    svc = FeedbackService(db_session)

    # Submit 11 thumbs_up — enough to trigger degenerate detection
    for _ in range(11):
        await svc.create_feedback(opt_id, "thumbs_up")

    # Verify the tracker sees the degenerate pattern
    tracker = AdaptationTracker(db_session)
    is_degenerate = await tracker.check_degenerate("generation", "chain-of-thought")
    assert is_degenerate is True


async def test_degenerate_skips_affinity_update(
    db_session: AsyncSession, opt_id: str,
) -> None:
    """Once feedback is degenerate, further feedback does NOT update affinity.

    The counter should freeze at the degenerate state — no more signal value.
    """
    svc = FeedbackService(db_session)
    tracker = AdaptationTracker(db_session)

    # Submit 11 thumbs_up to reach degenerate state
    for _ in range(11):
        await svc.create_feedback(opt_id, "thumbs_up")

    # Record the affinity state after reaching degenerate
    affinities_before = await tracker.get_affinities("generation")
    count_before = affinities_before["chain-of-thought"]["thumbs_up"]

    # Submit 3 more — these should be skipped (degenerate)
    for _ in range(3):
        await svc.create_feedback(opt_id, "thumbs_up")

    affinities_after = await tracker.get_affinities("generation")
    count_after = affinities_after["chain-of-thought"]["thumbs_up"]

    # Counts should NOT have increased
    assert count_after == count_before
