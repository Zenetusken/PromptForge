"""Tests for synthesis_history MCP tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp_server import synthesis_history
from app.schemas.mcp_models import HistoryOutput

pytestmark = pytest.mark.asyncio


def _make_opt(opt_id="opt1", task_type="coding", strategy="auto", overall_score=7.5,
              status="completed", raw_prompt="a" * 250, optimized_prompt="b" * 250):
    """Create a mock Optimization object."""
    opt = MagicMock()
    opt.id = opt_id
    opt.task_type = task_type
    opt.strategy_used = strategy
    opt.overall_score = overall_score
    opt.status = status
    opt.raw_prompt = raw_prompt
    opt.optimized_prompt = optimized_prompt
    opt.intent_label = "test label"
    opt.domain = "backend"
    opt.created_at = MagicMock()
    opt.created_at.isoformat.return_value = "2026-01-01T00:00:00"
    return opt


async def test_history_returns_paginated():
    """synthesis_history returns paginated HistoryOutput."""
    with patch("app.tools.history.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tools.history.OptimizationService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={
                "total": 25,
                "items": [_make_opt("opt1"), _make_opt("opt2")],
            })
            mock_svc_cls.return_value = mock_svc

            # Mock feedback query — no feedback
            fb_result = MagicMock()
            fb_result.all.return_value = []
            mock_db.execute = AsyncMock(return_value=fb_result)

            result = await synthesis_history(limit=2, offset=0)

    assert isinstance(result, HistoryOutput)
    assert result.total == 25
    assert result.count == 2
    assert result.has_more is True
    assert len(result.items) == 2
    assert result.items[0].id == "opt1"
    # Prompts are truncated to 200 chars
    assert len(result.items[0].raw_prompt_preview) == 200


async def test_history_empty():
    """Empty history returns zero items."""
    with patch("app.tools.history.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tools.history.OptimizationService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={
                "total": 0,
                "items": [],
            })
            mock_svc_cls.return_value = mock_svc

            result = await synthesis_history()

    assert result.total == 0
    assert result.count == 0
    assert result.has_more is False
    assert result.items == []


async def test_history_clamps_limit():
    """Limit is clamped to [1, 50]."""
    with patch("app.tools.history.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tools.history.OptimizationService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={
                "total": 0,
                "items": [],
            })
            mock_svc_cls.return_value = mock_svc

            # Limit 999 should be clamped to 50
            await synthesis_history(limit=999)
            call_kwargs = mock_svc.list_optimizations.call_args[1]
            assert call_kwargs["limit"] == 50


async def test_history_invalid_sort_column_falls_back():
    """Invalid sort_by falls back to 'created_at'."""
    with patch("app.tools.history.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tools.history.OptimizationService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={
                "total": 0,
                "items": [],
            })
            mock_svc_cls.return_value = mock_svc

            await synthesis_history(sort_by="sql_injection; DROP TABLE")
            call_kwargs = mock_svc.list_optimizations.call_args[1]
            assert call_kwargs["sort_by"] == "created_at"


async def test_history_with_feedback_rating():
    """Feedback ratings are included in history items."""
    with patch("app.tools.history.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tools.history.OptimizationService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_optimizations = AsyncMock(return_value={
                "total": 1,
                "items": [_make_opt("opt1")],
            })
            mock_svc_cls.return_value = mock_svc

            # Mock feedback query — has feedback
            fb_result = MagicMock()
            fb_result.all.return_value = [("opt1", "thumbs_up")]
            mock_db.execute = AsyncMock(return_value=fb_result)

            result = await synthesis_history()

    assert result.items[0].feedback_rating == "thumbs_up"
