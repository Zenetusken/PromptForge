"""Tests for MetaPattern.global_source_count field."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MetaPattern, PromptCluster


@pytest.mark.asyncio
async def test_meta_pattern_has_global_source_count_field(db: AsyncSession):
    """MetaPattern should have a global_source_count integer field defaulting to 0."""
    cluster = PromptCluster(
        label="test-cluster",
        state="active",
        domain="general",
    )
    db.add(cluster)
    await db.flush()

    mp = MetaPattern(
        cluster_id=cluster.id,
        pattern_text="Use chain-of-thought reasoning",
        source_count=5,
    )
    db.add(mp)
    await db.flush()

    result = await db.execute(select(MetaPattern).where(MetaPattern.id == mp.id))
    loaded = result.scalar_one()
    assert loaded.global_source_count == 0  # default
    assert isinstance(loaded.global_source_count, int)


@pytest.mark.asyncio
async def test_global_source_count_can_be_set(db: AsyncSession):
    """global_source_count should be writable."""
    cluster = PromptCluster(label="test", state="active", domain="general")
    db.add(cluster)
    await db.flush()

    mp = MetaPattern(
        cluster_id=cluster.id,
        pattern_text="Test pattern",
        source_count=1,
        global_source_count=7,
    )
    db.add(mp)
    await db.flush()

    loaded = (await db.execute(select(MetaPattern).where(MetaPattern.id == mp.id))).scalar_one()
    assert loaded.global_source_count == 7
