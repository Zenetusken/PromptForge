"""Tests for feedback CRUD and aggregation."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.feedback_service import (
    upsert_feedback,
    get_feedback_for_optimization,
    get_feedback_aggregate,
    get_user_feedback_history,
)


def _mock_feedback(rating=1, overrides=None, opt_id="opt-1", user_id="user-1"):
    fb = MagicMock()
    fb.id = "fb-1"
    fb.optimization_id = opt_id
    fb.user_id = user_id
    fb.rating = rating
    fb.dimension_overrides = json.dumps(overrides) if overrides else None
    fb.corrected_issues = None
    fb.comment = None
    fb.created_at = MagicMock(isoformat=MagicMock(return_value="2026-03-13T00:00:00"))
    return fb


class TestUpsertFeedback:
    @pytest.mark.asyncio
    async def test_creates_new_feedback(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        result = await upsert_feedback(
            optimization_id="opt-1",
            user_id="user-1",
            rating=1,
            dimension_overrides=None,
            corrected_issues=None,
            comment=None,
            db=db,
        )
        assert result["created"] is True
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_feedback(self):
        db = AsyncMock()
        existing = _mock_feedback()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute.return_value = result_mock

        result = await upsert_feedback(
            optimization_id="opt-1",
            user_id="user-1",
            rating=-1,
            dimension_overrides=None,
            corrected_issues=None,
            comment="updated",
            db=db,
        )
        assert result["created"] is False
        assert existing.rating == -1


class TestGetAggregate:
    @pytest.mark.asyncio
    async def test_empty_aggregate(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        db.execute.return_value = result_mock

        agg = await get_feedback_aggregate("opt-1", db)
        assert agg["total_ratings"] == 0
