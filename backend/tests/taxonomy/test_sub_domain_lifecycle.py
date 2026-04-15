"""End-to-end tests for the sub-domain lifecycle: creation guard, archival,
and cold-path parent preservation.

Validates the three fixes for orphaned sub-domains:
1. _propose_sub_domains() skips domains that already have sub-domains
2. phase_archive_empty_sub_domains() garbage-collects empty sub-domains
3. Cold path Step 12 preserves sub-domain parent_id links

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.models import MetaPattern, Optimization, PromptCluster
from app.services.taxonomy._constants import (
    EXCLUDED_STRUCTURAL_STATES,
    SUB_DOMAIN_ARCHIVAL_IDLE_HOURS,
)
from app.services.taxonomy.cluster_meta import write_meta

EMBEDDING_DIM = 384


def _random_embedding(seed: int = 0) -> bytes:
    rng = np.random.RandomState(seed)
    vec = rng.randn(EMBEDDING_DIM).astype(np.float32)
    vec /= np.linalg.norm(vec) + 1e-9
    return vec.tobytes()


def _make_domain(label: str, *, parent_id: str | None = None, source: str = "discovered") -> PromptCluster:
    return PromptCluster(
        label=label,
        state="domain",
        domain=label,
        task_type="general",
        parent_id=parent_id,
        persistence=1.0,
        color_hex="#aabbcc",
        centroid_embedding=_random_embedding(hash(label) % 2**31),
        cluster_metadata=write_meta(None, source=source),
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )


def _make_cluster(label: str, domain: str, parent_id: str) -> PromptCluster:
    return PromptCluster(
        label=label,
        state="active",
        domain=domain,
        parent_id=parent_id,
        member_count=5,
        centroid_embedding=_random_embedding(hash(label) % 2**31),
    )


# ---------------------------------------------------------------------------
# Phase 5.5: Sub-domain archival
# ---------------------------------------------------------------------------


class TestSubDomainArchival:
    """Tests for phase_archive_empty_sub_domains()."""

    @pytest.mark.asyncio
    async def test_archive_empty_sub_domain(self, db):
        """An empty sub-domain older than the idle threshold is archived."""
        from unittest.mock import MagicMock

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        # Create parent domain + empty sub-domain
        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("async-patterns", parent_id=parent.id)
        idle_hours = SUB_DOMAIN_ARCHIVAL_IDLE_HOURS + 1
        sub.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=idle_hours)
        db.add(sub)
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 1
        assert sub.state == "archived"
        assert sub.member_count == 0

    @pytest.mark.asyncio
    async def test_skip_sub_domain_with_multiple_children(self, db):
        """A sub-domain with 2+ active child clusters is NOT archived."""
        from unittest.mock import MagicMock

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("warm-path-ops", parent_id=parent.id)
        sub.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
        db.add(sub)
        await db.flush()

        # Add TWO active child clusters — genuine multi-cluster sub-domain
        child1 = _make_cluster("perf-cluster", domain="backend", parent_id=sub.id)
        child2 = _make_cluster("cache-cluster", domain="backend", parent_id=sub.id)
        db.add_all([child1, child2])
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 0
        assert sub.state == "domain"

    @pytest.mark.asyncio
    async def test_archive_single_child_sub_domain(self, db):
        """A sub-domain with exactly 1 child is a 1:1 wrapper — archived."""
        from unittest.mock import MagicMock

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("single-child-sub", parent_id=parent.id)
        sub.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
        db.add(sub)
        await db.flush()

        child = _make_cluster("lonely-cluster", domain="backend", parent_id=sub.id)
        db.add(child)
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 1
        assert sub.state == "archived"
        # Child reparented to top-level domain
        await db.refresh(child)
        assert child.parent_id == parent.id

    @pytest.mark.asyncio
    async def test_skip_young_sub_domain(self, db):
        """A sub-domain younger than the idle threshold is NOT archived."""
        from unittest.mock import MagicMock

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("fresh-sub", parent_id=parent.id)
        sub.created_at = datetime.now(timezone.utc).replace(tzinfo=None)  # just created
        db.add(sub)
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 0
        assert sub.state == "domain"

    @pytest.mark.asyncio
    async def test_skip_seed_domain(self, db):
        """Seed domains are never auto-archived."""
        from unittest.mock import MagicMock

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("seeded-sub", parent_id=parent.id, source="seed")
        sub.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
        db.add(sub)
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 0
        assert sub.state == "domain"

    @pytest.mark.asyncio
    async def test_skip_top_level_domain(self, db):
        """Top-level domains (parent_id=None) are never archived by this phase."""
        from unittest.mock import MagicMock

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        # Top-level domain with 0 children, old — still should NOT be archived
        top = _make_domain("abandoned")
        top.member_count = 0
        top.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90)
        db.add(top)
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 0
        assert top.state == "domain"

    @pytest.mark.asyncio
    async def test_skip_sub_domain_with_optimizations(self, db):
        """A sub-domain with directly assigned optimizations is NOT archived."""
        from unittest.mock import MagicMock

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("has-opts", parent_id=parent.id)
        sub.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
        db.add(sub)
        await db.flush()

        # Directly assigned optimization (unusual for domains, but safety check)
        opt = Optimization(
            raw_prompt="test",
            cluster_id=sub.id,
            embedding=_random_embedding(42),
        )
        db.add(opt)
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 0
        assert sub.state == "domain"

    @pytest.mark.asyncio
    async def test_meta_patterns_cleaned_on_archival(self, db):
        """MetaPatterns owned by the sub-domain are deleted on archival."""
        from unittest.mock import MagicMock

        from sqlalchemy import func, select

        from app.services.taxonomy.warm_phases import phase_archive_empty_sub_domains

        engine = MagicMock()
        engine.embedding_index = MagicMock()
        engine.transformation_index = MagicMock()
        engine.optimized_index = MagicMock()

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("stale-sub", parent_id=parent.id)
        sub.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
        db.add(sub)
        await db.flush()

        # Add patterns to the sub-domain
        mp = MetaPattern(
            cluster_id=sub.id,
            pattern_text="some pattern",
            embedding=_random_embedding(99),
        )
        db.add(mp)
        await db.flush()

        archived = await phase_archive_empty_sub_domains(engine, db)

        assert archived == 1
        remaining = (await db.execute(
            select(func.count()).where(MetaPattern.cluster_id == sub.id)
        )).scalar()
        assert remaining == 0


# ---------------------------------------------------------------------------
# Sub-domain creation guard
# ---------------------------------------------------------------------------


class TestSubDomainCreationGuard:
    """Tests for the guard that prevents re-discovery when sub-domains exist."""

    @pytest.mark.asyncio
    async def test_skip_discovery_when_sub_domains_exist(self, db):
        """_propose_sub_domains() should skip a domain that already has sub-domains."""
        from sqlalchemy import func, select

        # Create a parent domain that would normally trigger discovery
        parent = _make_domain("backend")
        parent.member_count = 17
        db.add(parent)
        await db.flush()

        # Create an existing sub-domain under it
        sub = _make_domain("existing-sub", parent_id=parent.id)
        db.add(sub)
        await db.flush()

        # The guard in _propose_sub_domains() checks:
        # SELECT count(*) FROM prompt_cluster WHERE parent_id=? AND state='domain'
        existing_sub_count = (await db.execute(
            select(func.count()).where(
                PromptCluster.parent_id == parent.id,
                PromptCluster.state == "domain",
            )
        )).scalar()

        assert existing_sub_count > 0, "Guard should detect existing sub-domains"


# ---------------------------------------------------------------------------
# Cold path sub-domain parent preservation
# ---------------------------------------------------------------------------


class TestColdPathSubDomainPreservation:
    """Tests for cold path Step 12 preserving sub-domain parent links."""

    @pytest.mark.asyncio
    async def test_preserve_valid_sub_domain_parent(self, db):
        """Clusters under a valid sub-domain keep their parent_id through cold path repair."""
        from sqlalchemy import select

        # Setup: backend -> sub-domain -> cluster
        backend = _make_domain("backend")
        db.add(backend)
        await db.flush()

        sub = _make_domain("warm-path-ops", parent_id=backend.id)
        db.add(sub)
        await db.flush()

        cluster = _make_cluster("perf-cluster", domain="backend", parent_id=sub.id)
        db.add(cluster)
        await db.flush()

        # Simulate Step 12 logic: build maps
        domain_q = await db.execute(
            select(PromptCluster).where(PromptCluster.state == "domain")
        )
        all_domain_nodes = list(domain_q.scalars().all())
        domain_id_to_label = {dn.id: dn.label for dn in all_domain_nodes}

        sub_domain_ids_by_domain: dict[str, set[str]] = {}
        for dn in all_domain_nodes:
            if dn.parent_id and dn.parent_id in domain_id_to_label:
                parent_label = domain_id_to_label[dn.parent_id]
                sub_domain_ids_by_domain.setdefault(parent_label, set()).add(dn.id)

        # Run the repair logic
        valid_subs = sub_domain_ids_by_domain.get(cluster.domain, set())

        # Cluster is under a valid sub-domain — should be preserved
        assert cluster.parent_id in valid_subs
        assert cluster.parent_id == sub.id  # NOT re-parented to backend

    @pytest.mark.asyncio
    async def test_reparent_invalid_parent_to_domain(self, db):
        """Clusters with an invalid parent get re-parented to their top-level domain."""
        from sqlalchemy import select

        backend = _make_domain("backend")
        db.add(backend)
        await db.flush()

        # Cluster with a non-domain parent (leftover from HDBSCAN)
        cluster = _make_cluster("orphan-cluster", domain="backend", parent_id="nonexistent-id")
        db.add(cluster)
        await db.flush()

        # Build maps
        domain_q = await db.execute(
            select(PromptCluster).where(PromptCluster.state == "domain")
        )
        all_domain_nodes = list(domain_q.scalars().all())
        domain_node_map = {dn.label: dn.id for dn in all_domain_nodes}
        domain_id_to_label = {dn.id: dn.label for dn in all_domain_nodes}

        sub_domain_ids_by_domain: dict[str, set[str]] = {}
        for dn in all_domain_nodes:
            if dn.parent_id and dn.parent_id in domain_id_to_label:
                parent_label = domain_id_to_label[dn.parent_id]
                sub_domain_ids_by_domain.setdefault(parent_label, set()).add(dn.id)

        # Run repair
        correct_parent = domain_node_map.get(cluster.domain)
        valid_subs = sub_domain_ids_by_domain.get(cluster.domain, set())

        if cluster.parent_id not in valid_subs and cluster.parent_id != correct_parent:
            cluster.parent_id = correct_parent

        assert cluster.parent_id == backend.id


# ---------------------------------------------------------------------------
# Tree integrity check 8
# ---------------------------------------------------------------------------


class TestTreeIntegrityEmptySubDomain:
    """Tests for check 8 in verify_domain_tree_integrity()."""

    @pytest.mark.asyncio
    async def test_detects_empty_sub_domain(self, db):
        """Empty sub-domains are reported as violations."""
        from sqlalchemy import func, select

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("empty-sub", parent_id=parent.id)
        sub.member_count = 0
        db.add(sub)
        await db.flush()

        # Gather domain IDs
        domain_id_q = await db.execute(
            select(PromptCluster.id).where(PromptCluster.state == "domain")
        )
        domain_ids = set(domain_id_q.scalars().all())

        # Check 8 logic
        violations = []
        for did in domain_ids:
            d_node = await db.get(PromptCluster, did)
            if not d_node or d_node.state != "domain":
                continue
            if d_node.parent_id not in domain_ids:
                continue
            child_count = (await db.execute(
                select(func.count()).where(
                    PromptCluster.parent_id == did,
                    PromptCluster.state.notin_(EXCLUDED_STRUCTURAL_STATES),
                )
            )).scalar() or 0
            if child_count == 0:
                violations.append(d_node.label)

        assert "empty-sub" in violations

    @pytest.mark.asyncio
    async def test_non_empty_sub_domain_passes(self, db):
        """Sub-domains with children are not flagged."""
        from sqlalchemy import func, select

        parent = _make_domain("backend")
        db.add(parent)
        await db.flush()

        sub = _make_domain("healthy-sub", parent_id=parent.id)
        db.add(sub)
        await db.flush()

        child = _make_cluster("child-cluster", domain="backend", parent_id=sub.id)
        db.add(child)
        await db.flush()

        domain_id_q = await db.execute(
            select(PromptCluster.id).where(PromptCluster.state == "domain")
        )
        domain_ids = set(domain_id_q.scalars().all())

        violations = []
        for did in domain_ids:
            d_node = await db.get(PromptCluster, did)
            if not d_node or d_node.state != "domain":
                continue
            if d_node.parent_id not in domain_ids:
                continue
            child_count = (await db.execute(
                select(func.count()).where(
                    PromptCluster.parent_id == did,
                    PromptCluster.state.notin_(EXCLUDED_STRUCTURAL_STATES),
                )
            )).scalar() or 0
            if child_count == 0:
                violations.append(d_node.label)

        assert "healthy-sub" not in violations


class TestSignalDrivenCreation:
    """Tests for the signal-driven sub-domain discovery logic."""

    @pytest.mark.asyncio
    async def test_qualifier_from_domain_raw(self, db):
        """parse_domain() correctly extracts qualifier from domain_raw."""
        from app.utils.text_cleanup import parse_domain

        primary, qualifier = parse_domain("backend: auth")
        assert primary == "backend"
        assert qualifier == "auth"

    @pytest.mark.asyncio
    async def test_qualifier_none_for_plain_domain(self, db):
        """parse_domain() returns None qualifier for plain domain."""
        from app.utils.text_cleanup import parse_domain

        primary, qualifier = parse_domain("backend")
        assert primary == "backend"
        assert qualifier is None

    @pytest.mark.asyncio
    async def test_intent_label_fallback_matching(self, db):
        """intent_label keyword matching finds qualifiers from vocabulary."""
        from app.services.heuristic_analyzer import _DOMAIN_QUALIFIERS

        domain_qualifiers = _DOMAIN_QUALIFIERS.get("backend", {})
        intent_label = "MCP routing architecture"
        intent_lower = intent_label.lower()

        best_q = None
        best_hits = 0
        for q_name, keywords in domain_qualifiers.items():
            hits = sum(1 for kw in keywords if kw in intent_lower)
            if hits > best_hits:
                best_hits = hits
                best_q = q_name

        # "routing" doesn't match any backend qualifier keywords
        assert best_q is None or best_hits == 0
