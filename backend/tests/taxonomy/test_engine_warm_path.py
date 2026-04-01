"""Tests for TaxonomyEngine warm path — periodic re-clustering with lifecycle."""


import numpy as np
import pytest

from app.models import Optimization, PromptCluster
from app.services.taxonomy.engine import TaxonomyEngine
from tests.taxonomy.conftest import EMBEDDING_DIM, make_cluster_distribution


@pytest.mark.asyncio
async def test_warm_path_creates_snapshot(db, mock_embedding, mock_provider):
    """Warm path should always create a snapshot."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    result = await engine.run_warm_path(db)
    assert result is not None
    assert result.snapshot_id is not None


@pytest.mark.asyncio
async def test_warm_path_lock_deduplication(db, mock_embedding, mock_provider):
    """Concurrent warm-path invocations should be deduplicated."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)

    # Acquire lock to simulate running warm path
    async with engine._warm_path_lock:
        assert engine._warm_path_lock.locked()
        # Second invocation should skip
        result = await engine.run_warm_path(db)
        assert result is None  # skipped due to lock


@pytest.mark.asyncio
async def test_warm_path_q_system_non_regressive(db, mock_embedding, mock_provider):
    """Q_system should not decrease across warm-path cycles (within epsilon)."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)

    # Create some families and nodes to give the warm path something to work with
    rng = np.random.RandomState(42)
    for text in ["REST API", "SQL queries", "React components"]:
        cluster = make_cluster_distribution(text, 5, spread=0.05, rng=rng)
        for i, emb in enumerate(cluster):
            f = PromptCluster(
                label=f"{text}-{i}",
                domain="general",
                centroid_embedding=emb.astype(np.float32).tobytes(),
            )
            db.add(f)
    await db.commit()

    # Run multiple warm paths
    q_values = []
    for _ in range(3):
        result = await engine.run_warm_path(db)
        if result and result.q_system is not None:
            q_values.append(result.q_system)

    # Q_system should be non-decreasing (within epsilon tolerance).
    # Exception: Q=0.0 is valid when the active set is too small
    # (< 3 nodes with separation data), so skip that comparison.
    for i in range(1, len(q_values)):
        if q_values[i] == 0.0 or q_values[i - 1] == 0.0:
            continue  # Q=0 means insufficient data, not regression
        assert q_values[i] >= q_values[i - 1] - 0.02  # epsilon tolerance


@pytest.mark.asyncio
async def test_warm_path_returns_operation_counts(db, mock_embedding, mock_provider):
    """WarmPathResult should report operations_attempted and operations_accepted."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    result = await engine.run_warm_path(db)
    assert result is not None
    assert result.operations_attempted >= 0
    assert result.operations_accepted >= 0
    assert result.operations_accepted <= result.operations_attempted


@pytest.mark.asyncio
async def test_warm_path_deadlock_breaker_field(db, mock_embedding, mock_provider):
    """WarmPathResult should include deadlock_breaker_used field."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    result = await engine.run_warm_path(db)
    assert result is not None
    assert isinstance(result.deadlock_breaker_used, bool)


@pytest.mark.asyncio
async def test_warm_path_lock_released_after_completion(db, mock_embedding, mock_provider):
    """Warm path should release lock after completing."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    await engine.run_warm_path(db)
    # Lock should be released after completion
    assert not engine._warm_path_lock.locked()


@pytest.mark.asyncio
async def test_warm_path_deadlock_breaker_triggers_at_cycle_5(
    db, mock_embedding, mock_provider
):
    """Deadlock breaker should activate after 5 consecutive rejected cycles.

    We set the counter to 4 and run one cycle where ops are attempted but
    ALL are rejected (ops_accepted == 0), pushing the counter to 5.
    """
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    engine._consecutive_rejected_cycles = 4

    # Create exactly ONE confirmed node with member_count=0 so retire is
    # attempted.  After retire succeeds, Q drops from ~0.7 to 0.0 (no
    # confirmed nodes left), which fails the non-regression check.  The
    # rollback makes ops_accepted=0, pushing the counter from 4 to 5.
    node = PromptCluster(
        label="Idle node",
        centroid_embedding=np.random.randn(EMBEDDING_DIM).astype(np.float32).tobytes(),
        state="active",
        member_count=0,
        coherence=0.9,
        color_hex="#a855f7",
    )
    db.add(node)
    await db.commit()

    result = await engine.run_warm_path(db)
    assert result is not None
    # The counter should have hit 5, triggering the breaker
    assert result.deadlock_breaker_used is True
    # Counter should be reset after breaker triggers
    assert engine._consecutive_rejected_cycles == 0
    # _cold_path_needed flag should be set
    assert engine._cold_path_needed is True


@pytest.mark.asyncio
async def test_warm_path_lock_released_on_error(db, mock_embedding, mock_provider):
    """Warm path should release lock even if an error occurs mid-execution."""
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)

    # Create a node with corrupt centroid to trigger error during Q computation
    node = PromptCluster(
        label="Corrupt",
        centroid_embedding=b"not_valid_floats",
        state="active",
        member_count=5,
        color_hex="#a855f7",
    )
    db.add(node)
    await db.commit()

    # Should not raise, and lock should be released
    await engine.run_warm_path(db)
    assert not engine._warm_path_lock.locked()


# ---------------------------------------------------------------------------
# Stale coherence tests
# ---------------------------------------------------------------------------


def _make_diverse_embeddings(n_topics: int, per_topic: int, rng: np.random.RandomState) -> list[np.ndarray]:
    """Generate embeddings for n_topics distinct clusters.

    Each topic gets a random center with tight samples (spread=0.02).
    Inter-topic similarity is low because random 384-dim vectors are
    nearly orthogonal.
    """
    all_embs: list[np.ndarray] = []
    for _ in range(n_topics):
        center = rng.randn(EMBEDDING_DIM).astype(np.float32)
        center /= np.linalg.norm(center) + 1e-9
        for _ in range(per_topic):
            noise = rng.randn(EMBEDDING_DIM).astype(np.float32) * 0.02
            vec = center + noise
            vec /= np.linalg.norm(vec) + 1e-9
            all_embs.append(vec)
    return all_embs


@pytest.mark.asyncio
async def test_warm_path_recomputes_stale_coherence(db, mock_embedding, mock_provider):
    """Clusters with stale high coherence should be corrected by warm path.

    The hot path never updates coherence, so a cluster that grew from 2 to 10
    members can still show coherence=0.95 when actual pairwise mean is ~0.4.
    The reconciliation phase must always recompute, not just when NULL/0.0.
    """
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    rng = np.random.RandomState(42)

    # Create a cluster with falsely high coherence
    center = rng.randn(EMBEDDING_DIM).astype(np.float32)
    center /= np.linalg.norm(center) + 1e-9

    cluster = PromptCluster(
        label="Stale Coherence Cluster",
        state="active",
        domain="general",
        centroid_embedding=center.tobytes(),
        member_count=10,
        coherence=0.95,  # stale — will not match actual pairwise
        color_hex="#a855f7",
    )
    db.add(cluster)
    await db.flush()

    # Add 10 diverse optimizations (5 topics × 2) — actual coherence will be low
    diverse_embs = _make_diverse_embeddings(5, 2, rng)
    for i, emb in enumerate(diverse_embs):
        opt = Optimization(
            raw_prompt=f"diverse prompt topic {i}",
            cluster_id=cluster.id,
            embedding=emb.astype(np.float32).tobytes(),
        )
        db.add(opt)
    await db.commit()

    await engine.run_warm_path(db)

    # Refresh from DB
    await db.refresh(cluster)
    # Coherence should now reflect actual pairwise similarity, not the stale 0.95
    assert cluster.coherence is not None
    assert cluster.coherence < 0.6, (
        f"Expected coherence to drop from stale 0.95 to actual pairwise (~0.4), "
        f"got {cluster.coherence:.3f}"
    )


@pytest.mark.asyncio
async def test_warm_path_recomputes_nonzero_coherence(db, mock_embedding, mock_provider):
    """Reconciliation must recompute coherence even when it's nonzero and non-null.

    Previously, the guard `node.coherence is None or node.coherence == 0.0`
    skipped clusters with any positive coherence value.
    """
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    rng = np.random.RandomState(99)

    # Create a tight 5-member cluster — actual coherence should be high
    tight_embs = make_cluster_distribution("tight cluster test", 5, spread=0.03, rng=rng)

    center = np.mean(tight_embs, axis=0).astype(np.float32)
    center /= np.linalg.norm(center) + 1e-9

    cluster = PromptCluster(
        label="Nonzero Coherence Cluster",
        state="active",
        domain="general",
        centroid_embedding=center.tobytes(),
        member_count=5,
        coherence=0.42,  # intentionally wrong — should be corrected upward
        color_hex="#a855f7",
    )
    db.add(cluster)
    await db.flush()

    for i, emb in enumerate(tight_embs):
        opt = Optimization(
            raw_prompt=f"tight prompt {i}",
            cluster_id=cluster.id,
            embedding=emb.astype(np.float32).tobytes(),
        )
        db.add(opt)
    await db.commit()

    await engine.run_warm_path(db)

    await db.refresh(cluster)
    # Coherence should be recomputed to the tight cluster's actual pairwise value.
    # With spread=0.03 this is ~0.73.  The key assertion: it was recomputed
    # from the stale 0.42 to something significantly higher.
    assert cluster.coherence is not None
    assert cluster.coherence > 0.65, (
        f"Expected tight cluster coherence >0.65, got {cluster.coherence:.3f} "
        f"(old guard would have left it at 0.42)"
    )


@pytest.mark.asyncio
async def test_split_triggers_on_stale_coherence_cluster(db, mock_embedding, mock_provider):
    """A 14-member mega-cluster with stale coherence should be split.

    With actual pairwise coherence well below the dynamic split floor,
    inline recomputation in split detection should trigger the split
    in a single warm cycle — not require two cycles.
    """
    engine = TaxonomyEngine(embedding_service=mock_embedding, provider=mock_provider)
    rng = np.random.RandomState(77)

    # Create a domain node for the cluster to be parented under
    domain_node = PromptCluster(
        label="general",
        state="domain",
        domain="general",
        centroid_embedding=rng.randn(EMBEDDING_DIM).astype(np.float32).tobytes(),
        member_count=14,
        color_hex="#6366f1",
    )
    db.add(domain_node)
    await db.flush()

    # Create a mega-cluster with stale high coherence
    center = rng.randn(EMBEDDING_DIM).astype(np.float32)
    center /= np.linalg.norm(center) + 1e-9

    mega = PromptCluster(
        label="Mega Cluster",
        state="active",
        domain="general",
        parent_id=domain_node.id,
        centroid_embedding=center.tobytes(),
        member_count=14,
        coherence=0.95,  # stale — actual will be ~0.2
        color_hex="#a855f7",
    )
    db.add(mega)
    await db.flush()

    # Add 14 diverse optimizations (7 topics × 2) — low actual coherence
    diverse_embs = _make_diverse_embeddings(7, 2, rng)
    for i, emb in enumerate(diverse_embs):
        opt = Optimization(
            raw_prompt=f"mega topic {i}",
            domain="general",
            cluster_id=mega.id,
            embedding=emb.astype(np.float32).tobytes(),
        )
        db.add(opt)
    await db.commit()

    result = await engine.run_warm_path(db)
    assert result is not None

    # The split should have been attempted
    assert result.operations_attempted >= 1, (
        "Expected at least 1 operation attempted (split), "
        f"got {result.operations_attempted}"
    )
