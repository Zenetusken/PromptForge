"""Tests for ADR-005 Phase 2A project creation."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LinkedRepo, PromptCluster


@pytest.mark.asyncio
async def test_linked_repo_has_project_node_id(db_session: AsyncSession):
    """LinkedRepo model has project_node_id column."""
    assert hasattr(LinkedRepo, "project_node_id")


@pytest.mark.asyncio
async def test_cross_project_threshold_boost_constant():
    """CROSS_PROJECT_THRESHOLD_BOOST constant exists."""
    from app.services.taxonomy._constants import CROSS_PROJECT_THRESHOLD_BOOST
    assert CROSS_PROJECT_THRESHOLD_BOOST == 0.15
