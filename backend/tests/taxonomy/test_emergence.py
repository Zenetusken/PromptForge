"""Behavioral tests — distinct prompt domains produce distinct clusters.

Reference: Spec Section 9.1, Layer 3.
"""

import numpy as np
import pytest
from sqlalchemy import select

from app.models import Optimization, PatternFamily
from app.services.taxonomy.engine import TaxonomyEngine
from tests.taxonomy.conftest import make_cluster_distribution


@pytest.mark.asyncio
async def test_distinct_domains_produce_distinct_clusters(db, mock_embedding, mock_provider):
    """Three distinct prompt domains should emerge as separate taxonomy nodes.

    This is the core behavioral property of the taxonomy engine.
    """
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    rng = np.random.RandomState(42)

    # Simulate 15 optimizations across 3 distinct domains
    domains = {
        "REST API design": make_cluster_distribution("REST API design", 5, spread=0.03, rng=rng),
        "SQL optimization": make_cluster_distribution("SQL optimization", 5, spread=0.03, rng=rng),
        "React components": make_cluster_distribution("React components", 5, spread=0.03, rng=rng),
    }

    for domain_text, embeddings in domains.items():
        for i, emb in enumerate(embeddings):
            opt = Optimization(
                raw_prompt=f"{domain_text} prompt {i}",
                optimized_prompt=f"optimized {i}",
                status="completed",
                intent_label=domain_text,
                domain_raw=domain_text,
            )
            db.add(opt)
    await db.commit()

    # Process all optimizations
    all_opts = (await db.execute(select(Optimization))).scalars().all()
    for opt in all_opts:
        await engine.process_optimization(opt.id, db)

    # Run warm path to crystallize clusters
    await engine.run_warm_path(db)

    # Check families were created
    families = (await db.execute(select(PatternFamily))).scalars().all()
    assert len(families) >= 3, f"Expected >=3 families, got {len(families)}"


@pytest.mark.asyncio
async def test_identical_prompts_converge(db, mock_embedding, mock_provider):
    """Identical prompts should join the same family, not proliferate."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)

    for i in range(5):
        opt = Optimization(
            raw_prompt="Build a REST API with FastAPI and PostgreSQL",
            optimized_prompt=f"optimized {i}",
            status="completed",
            intent_label="REST API",
            domain_raw="REST API design",
        )
        db.add(opt)
    await db.commit()

    all_opts = (await db.execute(select(Optimization))).scalars().all()
    for opt in all_opts:
        await engine.process_optimization(opt.id, db)

    families = (await db.execute(select(PatternFamily))).scalars().all()
    # All 5 identical prompts should converge into 1 family
    assert len(families) == 1
    assert families[0].member_count == 5
