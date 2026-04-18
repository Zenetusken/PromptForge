"""Schema-level tests for PromptTemplate and PromptCluster.template_count."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import PromptCluster, PromptTemplate


@pytest.mark.asyncio
async def test_prompt_template_columns_present(db_session):
    row = PromptTemplate(
        id=uuid.uuid4().hex,
        source_cluster_id=None,
        source_optimization_id=None,
        project_id=None,
        label="test",
        prompt="echo this",
        strategy="auto",
        score=7.5,
        pattern_ids=[],
        domain_label="general",
    )
    db_session.add(row)
    await db_session.flush()

    result = await db_session.execute(select(PromptTemplate).where(PromptTemplate.id == row.id))
    fetched = result.scalar_one()
    assert fetched.usage_count == 0
    assert fetched.retired_at is None
    assert fetched.promoted_at is not None
    assert isinstance(fetched.promoted_at, datetime)


@pytest.mark.asyncio
async def test_prompt_cluster_has_template_count_default_zero(db_session):
    cluster = PromptCluster(id="c1", label="x", state="active")
    db_session.add(cluster)
    await db_session.flush()
    assert cluster.template_count == 0
