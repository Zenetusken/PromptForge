"""Tests for explicit input validation on sort/order parameters.

IV-sort  — sort column whitelist (history router, optimization_service)
IV-order — order direction validation
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.optimization_service import VALID_SORT_COLUMNS, list_optimizations

# ---------------------------------------------------------------------------
# IV-sort-1: optimization_service rejects unknown sort columns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_optimization_service_rejects_invalid_sort():
    """list_optimizations must raise ValueError for unknown sort columns."""
    mock_session = AsyncMock()
    with pytest.raises(ValueError, match="Invalid sort column"):
        await list_optimizations(mock_session, sort="DROP TABLE")


def test_valid_sort_columns_whitelist_is_nonempty():
    """VALID_SORT_COLUMNS must contain the expected core columns."""
    assert "created_at" in VALID_SORT_COLUMNS
    assert "overall_score" in VALID_SORT_COLUMNS
    assert "updated_at" in VALID_SORT_COLUMNS


# ---------------------------------------------------------------------------
# IV-order-1: optimization_service rejects invalid order direction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_optimization_service_rejects_invalid_order():
    """list_optimizations must raise ValueError for invalid order values."""
    mock_session = AsyncMock()
    with pytest.raises(ValueError, match="Invalid order"):
        await list_optimizations(mock_session, order="sideways")


@pytest.mark.asyncio
async def test_optimization_service_rejects_empty_order():
    """list_optimizations must reject empty string order."""
    mock_session = AsyncMock()
    with pytest.raises(ValueError, match="Invalid order"):
        await list_optimizations(mock_session, order="")


@pytest.mark.asyncio
async def test_optimization_service_rejects_uppercase_order():
    """list_optimizations must reject case-variant order values (strict match)."""
    mock_session = AsyncMock()
    with pytest.raises(ValueError, match="Invalid order"):
        await list_optimizations(mock_session, order="ASC")
