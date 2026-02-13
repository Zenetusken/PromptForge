"""Tests for history endpoints."""

import pytest


@pytest.mark.asyncio
async def test_empty_history_list(client):
    response = await client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_empty_stats(client):
    response = await client.get("/api/history/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_optimizations"] == 0
    assert data["average_overall_score"] is None
    assert data["improvement_rate"] is None
