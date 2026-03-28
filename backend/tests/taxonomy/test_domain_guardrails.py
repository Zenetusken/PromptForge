"""Tests for domain stability guardrails in lifecycle operations."""

from __future__ import annotations

import numpy as np
import pytest

from app.models import PromptCluster
from app.services.taxonomy.lifecycle import (
    GuardrailViolationError,
    _assert_domain_guardrails,
)


def _make_domain_node(label: str = "backend") -> PromptCluster:
    return PromptCluster(label=label, state="domain", domain=label, persistence=1.0)


def _make_cluster(label: str = "test") -> PromptCluster:
    return PromptCluster(label=label, state="active", domain="backend")


def test_retire_domain_raises():
    with pytest.raises(GuardrailViolationError, match="retire"):
        _assert_domain_guardrails("retire", _make_domain_node())


def test_merge_domain_raises():
    with pytest.raises(GuardrailViolationError, match="merge"):
        _assert_domain_guardrails("merge", _make_domain_node())


def test_color_assign_domain_raises():
    with pytest.raises(GuardrailViolationError, match="color_assign"):
        _assert_domain_guardrails("color_assign", _make_domain_node())


def test_non_domain_cluster_passes():
    for op in ("retire", "merge", "color_assign", "split", "emerge"):
        _assert_domain_guardrails(op, _make_cluster())


def test_unknown_operation_on_domain_passes():
    # Operations not in the violations map should pass through
    _assert_domain_guardrails("split", _make_domain_node())
    _assert_domain_guardrails("emerge", _make_domain_node())


@pytest.mark.asyncio
async def test_split_children_inherit_parent_domain(db):
    """When splitting, children inherit domain from parent."""
    from app.services.taxonomy.lifecycle import attempt_split

    parent = PromptCluster(
        label="api-patterns", state="active", domain="backend",
        centroid_embedding=np.zeros(384, dtype=np.float32).tobytes(),
        member_count=10,
    )
    db.add(parent)
    await db.flush()

    # Create child cluster material
    child_ids_1 = []
    child_embeddings_1 = []
    child_ids_2 = []
    child_embeddings_2 = []
    for i in range(6):
        emb = np.random.randn(384).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        c = PromptCluster(
            label=f"child-{i}", state="active", domain="backend",
            parent_id=parent.id,
            centroid_embedding=emb.tobytes(),
        )
        db.add(c)
        await db.flush()
        if i < 3:
            child_ids_1.append(c.id)
            child_embeddings_1.append(emb)
        else:
            child_ids_2.append(c.id)
            child_embeddings_2.append(emb)

    sub_clusters = [
        (child_ids_1, child_embeddings_1),
        (child_ids_2, child_embeddings_2),
    ]

    children = await attempt_split(
        db, parent, sub_clusters, warm_path_age=1, provider=None, model="test",
    )
    assert len(children) == 2
    for child in children:
        assert child.state == "candidate"
        assert child.domain == "backend"  # Inherited from parent


@pytest.mark.asyncio
async def test_split_domain_node_children_inherit_label(db):
    """When splitting a domain node, children inherit its label as domain."""
    from app.services.taxonomy.lifecycle import attempt_split

    parent = PromptCluster(
        label="backend", state="domain", domain="backend",
        centroid_embedding=np.zeros(384, dtype=np.float32).tobytes(),
        member_count=10, persistence=1.0,
    )
    db.add(parent)
    await db.flush()

    child_ids = []
    child_embeddings = []
    for i in range(6):
        emb = np.random.randn(384).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        c = PromptCluster(
            label=f"child-{i}", state="active", domain="backend",
            parent_id=parent.id,
            centroid_embedding=emb.tobytes(),
        )
        db.add(c)
        await db.flush()
        child_ids.append(c.id)
        child_embeddings.append(emb)

    sub_clusters = [
        (child_ids[:3], child_embeddings[:3]),
        (child_ids[3:], child_embeddings[3:]),
    ]

    children = await attempt_split(
        db, parent, sub_clusters, warm_path_age=1, provider=None, model="test",
    )
    for child in children:
        assert child.state == "candidate"   # Never "domain"
        assert child.domain == "backend"    # Inherited from parent label


@pytest.mark.asyncio
async def test_emerge_node_inherits_majority_domain(db):
    """Emerged node should inherit domain from the majority of member clusters."""
    from app.services.taxonomy.lifecycle import attempt_emerge

    # Create 4 backend + 2 frontend member clusters
    member_ids = []
    embeddings = []
    for i in range(4):
        emb = np.random.randn(384).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        c = PromptCluster(
            label=f"backend-cluster-{i}", state="active", domain="backend",
            centroid_embedding=emb.tobytes(),
        )
        db.add(c)
        await db.flush()
        member_ids.append(c.id)
        embeddings.append(emb)
    for i in range(2):
        emb = np.random.randn(384).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        c = PromptCluster(
            label=f"frontend-cluster-{i}", state="active", domain="frontend",
            centroid_embedding=emb.tobytes(),
        )
        db.add(c)
        await db.flush()
        member_ids.append(c.id)
        embeddings.append(emb)

    node = await attempt_emerge(
        db, member_ids, embeddings, warm_path_age=1, provider=None, model="test",
    )
    assert node is not None
    assert node.state == "candidate"
    assert node.domain == "backend"  # Majority domain wins
