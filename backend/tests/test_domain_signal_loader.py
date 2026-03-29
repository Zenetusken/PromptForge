"""Tests for DomainSignalLoader — dynamic heuristic keyword signals."""

from __future__ import annotations

import re

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, PromptCluster
from app.services.domain_signal_loader import DomainSignalLoader


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    await engine.dispose()


async def _seed_domain(db: AsyncSession, label: str, keywords: list) -> None:
    db.add(PromptCluster(
        label=label, state="domain", domain=label, persistence=1.0,
        cluster_metadata={"source": "seed", "signal_keywords": keywords},
    ))
    await db.commit()


@pytest.mark.asyncio
async def test_load_signals_from_domain_metadata(db):
    await _seed_domain(db, "backend", [["api", 0.8], ["endpoint", 0.9]])
    loader = DomainSignalLoader()
    await loader.load(db)
    assert "backend" in loader.signals
    assert ("api", 0.8) in loader.signals["backend"]


@pytest.mark.asyncio
async def test_classify_returns_matching_domain(db):
    await _seed_domain(db, "backend", [["api", 0.8], ["endpoint", 0.9]])
    await _seed_domain(db, "frontend", [["react", 1.0], ["component", 0.8]])
    loader = DomainSignalLoader()
    await loader.load(db)
    scored = {"backend": 2.5, "frontend": 0.3}
    assert loader.classify(scored) == "backend"


@pytest.mark.asyncio
async def test_classify_returns_general_when_no_scores(db):
    loader = DomainSignalLoader()
    await loader.load(db)
    assert loader.classify({}) == "general"


@pytest.mark.asyncio
async def test_classify_returns_general_when_below_threshold(db):
    await _seed_domain(db, "backend", [["api", 0.8]])
    loader = DomainSignalLoader()
    await loader.load(db)
    scored = {"backend": 0.5}  # Below 1.0 threshold
    assert loader.classify(scored) == "general"


@pytest.mark.asyncio
async def test_classify_cross_cutting_domain(db):
    await _seed_domain(db, "backend", [["api", 0.8]])
    await _seed_domain(db, "security", [["auth", 0.7], ["jwt", 0.9]])
    loader = DomainSignalLoader()
    await loader.load(db)
    scored = {"backend": 2.0, "security": 1.5}
    result = loader.classify(scored)
    assert result == "backend: security"


@pytest.mark.asyncio
async def test_score_words(db):
    await _seed_domain(db, "backend", [["api", 0.8], ["endpoint", 0.9]])
    loader = DomainSignalLoader()
    await loader.load(db)
    words = {"api", "endpoint", "the", "a"}
    scored = loader.score(words)
    assert scored["backend"] == pytest.approx(1.7)


@pytest.mark.asyncio
async def test_empty_signals_classify_general(db):
    """No domain nodes → classifier returns 'general' for everything."""
    loader = DomainSignalLoader()
    await loader.load(db)
    assert loader.classify({"backend": 5.0}) == "general"


@pytest.mark.asyncio
async def test_patterns_precompiled(db):
    await _seed_domain(db, "backend", [["api", 0.8]])
    loader = DomainSignalLoader()
    await loader.load(db)
    assert "api" in loader.patterns
    assert isinstance(loader.patterns["api"], re.Pattern)


@pytest.mark.asyncio
async def test_domain_without_keywords_skipped(db):
    """Domain node with no signal_keywords is ignored."""
    db.add(PromptCluster(
        label="empty", state="domain", domain="empty", persistence=1.0,
        cluster_metadata={"source": "seed"},  # No signal_keywords key
    ))
    await db.commit()
    loader = DomainSignalLoader()
    await loader.load(db)
    assert "empty" not in loader.signals
