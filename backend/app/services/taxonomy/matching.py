"""Prompt matching and domain mapping — search/retrieval operations for the
taxonomy engine.

Extracted from engine.py (Task 2.3) to keep engine.py focused on
orchestration (hot/warm/cold paths + read API).

All functions accept explicit dependencies rather than referencing
engine state.  The TaxonomyEngine delegates to these functions from
``match_prompt()`` and ``map_domain()``.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MetaPattern,
    PromptCluster,
)
from app.services.embedding_service import EmbeddingService
from app.services.taxonomy.family_ops import (
    PATTERN_MERGE_THRESHOLD,
    build_breadcrumb,
    compute_pattern_centroid,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — cosine similarity thresholds
# ---------------------------------------------------------------------------

DOMAIN_ALIGNMENT_FLOOR = 0.35

# Pattern matching thresholds — calibrated for raw (non-fused) embeddings.
# Raw prompt-to-centroid cosine similarity is ~0.15-0.20 lower than fused,
# because centroids are averaged cluster embeddings (blurred by member diversity).
# Fusion was removed from match_prompt() for cross-process consistency
# (MCP and backend produce identical results with raw embeddings).
FAMILY_MATCH_THRESHOLD = 0.55
CLUSTER_MATCH_THRESHOLD = 0.45
CANDIDATE_THRESHOLD = 0.65

# ---------------------------------------------------------------------------
# Embedding cache — avoids re-embedding identical prompts during rapid typing
# ---------------------------------------------------------------------------

_EMBEDDING_CACHE: dict[str, tuple[np.ndarray, float]] = {}
_EMBEDDING_CACHE_MAX = 50
_EMBEDDING_CACHE_TTL = 300  # seconds


def _cache_key(text: str) -> str:
    return hashlib.md5(text[:500].encode()).hexdigest()


def _get_cached_embedding(text: str) -> np.ndarray | None:
    key = _cache_key(text)
    entry = _EMBEDDING_CACHE.get(key)
    if entry is None:
        return None
    emb, ts = entry
    if time.monotonic() - ts > _EMBEDDING_CACHE_TTL:
        del _EMBEDDING_CACHE[key]
        return None
    return emb


def _put_cached_embedding(text: str, emb: np.ndarray) -> None:
    if len(_EMBEDDING_CACHE) >= _EMBEDDING_CACHE_MAX:
        oldest_key = min(_EMBEDDING_CACHE, key=lambda k: _EMBEDDING_CACHE[k][1])
        del _EMBEDDING_CACHE[oldest_key]
    _EMBEDDING_CACHE[_cache_key(text)] = (emb, time.monotonic())


# ---------------------------------------------------------------------------
# Public data-transfer objects
# ---------------------------------------------------------------------------


@dataclass
class TaxonomyMapping:
    """Result of map_domain — may be fully unmapped (cluster_id is None)."""

    cluster_id: str | None
    taxonomy_label: str | None
    taxonomy_breadcrumb: list[str]
    domain_raw: str


@dataclass
class PatternMatch:
    """Result of a pattern similarity search against the knowledge graph."""

    cluster: PromptCluster | None
    meta_patterns: list[MetaPattern]
    similarity: float
    match_level: str  # "family" | "cluster" | "none"
    taxonomy_breadcrumb: list[str] | None = None
    cross_cluster_patterns: list[MetaPattern] = field(default_factory=list)


# ---------------------------------------------------------------------------
# match_prompt — hierarchical pattern matching (Spec Section 7.2, 7.4, 7.7, 7.9)
# ---------------------------------------------------------------------------


async def match_prompt(
    prompt_text: str,
    db: AsyncSession,
    embedding_service: EmbeddingService,
) -> PatternMatch | None:
    """Hierarchical pattern matching for on-paste suggestion.

    Reference: Spec Section 7.2, 7.4, 7.7, 7.9

    Cascade search:
    1. Embed prompt
    2. Search leaf families -- if cosine >= family_threshold -> family match
    3. If no leaf match, search parent clusters -- if cosine >= cluster_threshold -> cluster match
    4. No match at any level -> return None

    Cold-start: candidate families use strict 0.80 threshold (Spec 7.4).
    Thresholds adapt per-cluster coherence (Spec 7.9).
    """
    from app.services.taxonomy.quality import suggestion_threshold

    # 1. Embed the prompt text (with LRU cache for rapid typing)
    cached = _get_cached_embedding(prompt_text)
    if cached is not None:
        query_emb = cached
    else:
        query_emb = await embedding_service.aembed_single(prompt_text)
        _put_cached_embedding(prompt_text, query_emb)

    # Use raw embedding for matching — composite fusion depends on process-local
    # engine state (embedding_index, transformation_index) which diverges between
    # the backend and MCP processes. Raw embedding is deterministic: same prompt
    # always produces the same search vector regardless of which process runs it.
    # Fusion is still used by auto_inject_patterns() during optimization, where
    # the caller controls which engine instance is used.
    search_emb = query_emb
    _fusion_used = False

    # Diagnostic tracking — record best scores for no-match logging
    _best_family_score: float = 0.0
    _best_family_threshold: float = 0.0
    _best_cluster_score: float = 0.0
    _best_cluster_threshold: float = 0.0

    # ------------------------------------------------------------------
    # Level 1: Family-level search
    # ------------------------------------------------------------------
    result = await db.execute(
        select(PromptCluster).where(
            PromptCluster.parent_id.isnot(None)
        )
    )
    families = list(result.scalars().all())

    result: PatternMatch | None = None

    if families:
        # Build family centroids and load their parent nodes
        valid_families: list[PromptCluster] = []
        centroids: list[np.ndarray] = []
        node_ids: set[str] = set()

        for f in families:
            try:
                c = np.frombuffer(f.centroid_embedding, dtype=np.float32)
                if c.shape[0] != query_emb.shape[0]:
                    continue
                centroids.append(c)
                valid_families.append(f)
                if f.parent_id:
                    node_ids.add(f.parent_id)
            except (ValueError, TypeError):
                continue

        skipped = len(families) - len(valid_families)
        if skipped > 0:
            logger.warning(
                "match_prompt: skipped %d/%d families (dimension mismatch or corrupt centroid)",
                skipped, len(families),
            )

        # Pre-load all referenced taxonomy nodes
        node_map: dict[str, PromptCluster] = {}
        if node_ids:
            node_result = await db.execute(
                select(PromptCluster).where(PromptCluster.id.in_(list(node_ids)))
            )
            for n in node_result.scalars().all():
                node_map[n.id] = n

        if centroids:
            # Search all family centroids
            matches = EmbeddingService.cosine_search(
                search_emb, centroids, top_k=len(centroids)
            )

            for idx, score in matches:
                family = valid_families[idx]
                node = node_map.get(family.parent_id) if family.parent_id else None

                # Determine threshold based on node state (Spec 7.4)
                if node and node.state == "candidate":
                    threshold = CANDIDATE_THRESHOLD
                elif node:
                    coherence = node.coherence if node.coherence is not None else 0.0
                    threshold = suggestion_threshold(
                        base=FAMILY_MATCH_THRESHOLD, coherence=coherence
                    )
                else:
                    threshold = FAMILY_MATCH_THRESHOLD

                # Track best score for diagnostics
                if score > _best_family_score:
                    _best_family_score = score
                    _best_family_threshold = threshold

                if score >= threshold:
                    # Load meta-patterns for this cluster
                    mp_result = await db.execute(
                        select(MetaPattern).where(
                            MetaPattern.cluster_id == family.id
                        )
                    )
                    meta_patterns = list(mp_result.scalars().all())

                    breadcrumb = await build_breadcrumb(db, node) if node else []

                    result = PatternMatch(
                        cluster=node or family,
                        meta_patterns=meta_patterns,
                        similarity=score,
                        match_level="family",
                        taxonomy_breadcrumb=breadcrumb,
                    )
                    break

    # ------------------------------------------------------------------
    # Level 2: Cluster-level fallback
    # ------------------------------------------------------------------
    if result is None:
        node_result = await db.execute(
            select(PromptCluster).where(
                PromptCluster.state.in_(["active", "candidate"])
            )
        )
        all_nodes = list(node_result.scalars().all())

        if all_nodes:
            valid_nodes: list[PromptCluster] = []
            node_centroids: list[np.ndarray] = []

            for n in all_nodes:
                try:
                    c = np.frombuffer(n.centroid_embedding, dtype=np.float32)
                    if c.shape[0] != query_emb.shape[0]:
                        continue
                    node_centroids.append(c)
                    valid_nodes.append(n)
                except (ValueError, TypeError):
                    continue

            skipped_nodes = len(all_nodes) - len(valid_nodes)
            if skipped_nodes > 0:
                logger.warning(
                    "match_prompt: skipped %d/%d taxonomy nodes (dimension mismatch or corrupt centroid)",
                    skipped_nodes, len(all_nodes),
                )

            if node_centroids:
                matches = EmbeddingService.cosine_search(
                    search_emb, node_centroids, top_k=len(node_centroids)
                )

                for idx, score in matches:
                    node = valid_nodes[idx]
                    coherence = node.coherence if node.coherence is not None else 0.0
                    # Spec 7.4 strict CANDIDATE_THRESHOLD applies only at family
                    # level. Cluster-level uses adaptive threshold for all node
                    # states — the match is more general (parent cluster context).
                    threshold = suggestion_threshold(
                        base=CLUSTER_MATCH_THRESHOLD, coherence=coherence
                    )

                    # Track best score for diagnostics
                    if score > _best_cluster_score:
                        _best_cluster_score = score
                        _best_cluster_threshold = threshold

                    if score >= threshold:
                        # Aggregate meta-patterns from top-3 child families
                        # ranked by cosine similarity to query (Spec 7.7).
                        # Load direct children once (covers both leaf families
                        # and intermediate nodes in the unified PromptCluster model).
                        children_result = await db.execute(
                            select(PromptCluster)
                            .where(PromptCluster.parent_id == node.id)
                        )
                        direct_children = list(children_result.scalars().all())
                        candidate_families = list(direct_children)

                        # Also include grandchildren (families under child nodes)
                        child_node_ids = [cn.id for cn in direct_children]
                        if child_node_ids:
                            grandchildren_result = await db.execute(
                                select(PromptCluster)
                                .where(
                                    PromptCluster.parent_id.in_(child_node_ids)
                                )
                            )
                            candidate_families.extend(
                                grandchildren_result.scalars().all()
                            )

                        # Rank all candidate families by cosine similarity
                        # to the query embedding and take top-3
                        scored_families: list[tuple[PromptCluster, float]] = []
                        for fam in candidate_families:
                            try:
                                fc = np.frombuffer(
                                    fam.centroid_embedding, dtype=np.float32
                                )
                                if fc.shape[0] != search_emb.shape[0]:
                                    continue
                                norm_fc = np.linalg.norm(fc)
                                norm_q = np.linalg.norm(search_emb)
                                if norm_fc > 0 and norm_q > 0:
                                    sim = float(
                                        np.dot(search_emb, fc) / (norm_q * norm_fc)
                                    )
                                    scored_families.append((fam, sim))
                            except (ValueError, TypeError):
                                continue

                        scored_families.sort(key=lambda x: x[1], reverse=True)
                        top_families = [f for f, _ in scored_families[:3]]

                        # Gather meta-patterns from these families
                        cluster_ids = [f.id for f in top_families]
                        if cluster_ids:
                            mp_result = await db.execute(
                                select(MetaPattern).where(
                                    MetaPattern.cluster_id.in_(cluster_ids)
                                )
                            )
                            all_meta_patterns = list(mp_result.scalars().all())
                        else:
                            all_meta_patterns = []

                        # Deduplicate at cosine 0.82
                        deduped = _deduplicate_meta_patterns(all_meta_patterns)

                        breadcrumb = await build_breadcrumb(db, node)

                        result = PatternMatch(
                            cluster=node,
                            meta_patterns=deduped,
                            similarity=score,
                            match_level="cluster",
                            taxonomy_breadcrumb=breadcrumb,
                        )
                        break

    # ------------------------------------------------------------------
    # No match at any level — create a "none" result with diagnostics
    # ------------------------------------------------------------------
    if result is None:
        logger.info(
            "match_prompt: no match found — "
            "best_family=%.3f (threshold=%.3f) best_cluster=%.3f (threshold=%.3f) "
            "fusion=%s prompt_len=%d",
            _best_family_score, _best_family_threshold,
            _best_cluster_score, _best_cluster_threshold,
            "fused" if _fusion_used else "raw",
            len(prompt_text),
        )
        result = PatternMatch(
            cluster=None,
            meta_patterns=[],
            similarity=0.0,
            match_level="none",
        )

    # ------------------------------------------------------------------
    # Cross-cluster patterns: fetch high global_source_count patterns
    # from ANY cluster, ranked by relevance to the prompt.
    # ------------------------------------------------------------------
    cross_cluster: list[MetaPattern] = []
    try:
        import math

        from app.services.pipeline_constants import (
            CROSS_CLUSTER_MAX_PATTERNS,
            CROSS_CLUSTER_MIN_SOURCE_COUNT,
            CROSS_CLUSTER_RELEVANCE_FLOOR,
        )
        from app.services.taxonomy._constants import EXCLUDED_STRUCTURAL_STATES

        cc_q = await db.execute(
            select(MetaPattern, PromptCluster.avg_score)
            .join(PromptCluster, MetaPattern.cluster_id == PromptCluster.id)
            .where(
                MetaPattern.global_source_count >= CROSS_CLUSTER_MIN_SOURCE_COUNT,
                MetaPattern.embedding.isnot(None),
                PromptCluster.state.notin_(EXCLUDED_STRUCTURAL_STATES),
            )
            .order_by(MetaPattern.global_source_count.desc())
            .limit(CROSS_CLUSTER_MAX_PATTERNS * 3)  # fetch extra for filtering
        )

        # Deduplicate against patterns already collected for the matched cluster
        existing_ids: set[str] = set()
        if result and result.meta_patterns:
            existing_ids = {p.id for p in result.meta_patterns}

        # Score and rank by relevance (same formula as pattern_injection.py)
        scored_candidates: list[tuple[MetaPattern, float]] = []
        for cp, cluster_avg_score in cc_q.all():
            if cp.id in existing_ids:
                continue
            try:
                pat_emb = np.frombuffer(cp.embedding, dtype=np.float32)
                sim = float(
                    np.dot(query_emb, pat_emb)
                    / (np.linalg.norm(query_emb) * np.linalg.norm(pat_emb) + 1e-9)
                )
                cluster_score_factor = max(0.1, (cluster_avg_score or 5.0) / 10.0)
                relevance = sim * math.log2(1 + cp.global_source_count) * cluster_score_factor
                if relevance >= CROSS_CLUSTER_RELEVANCE_FLOOR:
                    scored_candidates.append((cp, relevance))
            except (ValueError, TypeError):
                continue

        # Sort by relevance descending, take top-N
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        for cp, _ in scored_candidates[:CROSS_CLUSTER_MAX_PATTERNS]:
            cross_cluster.append(cp)
    except Exception as cc_exc:
        logger.warning("Cross-cluster pattern lookup failed (non-fatal): %s", cc_exc)

    result.cross_cluster_patterns = cross_cluster

    return result


def _deduplicate_meta_patterns(
    patterns: list[MetaPattern],
) -> list[MetaPattern]:
    """Deduplicate meta-patterns by cosine similarity at PATTERN_MERGE_THRESHOLD.

    Keeps the first occurrence (by order) and drops near-duplicates.
    Patterns without embeddings are always kept.
    """
    if len(patterns) <= 1:
        return patterns

    deduped: list[MetaPattern] = []
    deduped_embeddings: list[np.ndarray] = []

    for mp in patterns:
        if not mp.embedding:
            deduped.append(mp)
            continue

        try:
            emb = np.frombuffer(mp.embedding, dtype=np.float32)
        except (ValueError, TypeError):
            deduped.append(mp)
            continue

        # Check against already-kept patterns
        is_duplicate = False
        for kept_emb in deduped_embeddings:
            if emb.shape != kept_emb.shape:
                continue
            norm_a = np.linalg.norm(emb)
            norm_b = np.linalg.norm(kept_emb)
            if norm_a > 0 and norm_b > 0:
                sim = float(np.dot(emb, kept_emb) / (norm_a * norm_b))
                if sim >= PATTERN_MERGE_THRESHOLD:
                    is_duplicate = True
                    break

        if not is_duplicate:
            deduped.append(mp)
            deduped_embeddings.append(emb)

    return deduped


# ---------------------------------------------------------------------------
# map_domain — domain string to nearest active PromptCluster
# ---------------------------------------------------------------------------


async def map_domain(
    domain_raw: str,
    db: AsyncSession,
    embedding_service: EmbeddingService,
    applied_pattern_ids: list[str] | None = None,
) -> TaxonomyMapping:
    """Map a free-text domain string to the nearest active PromptCluster.

    If applied_pattern_ids are provided, compute a pattern centroid and
    blend 70 % analyzer embedding + 30 % pattern centroid (Bayesian prior).

    Args:
        domain_raw: Raw domain string from the analyzer phase.
        db: Async SQLAlchemy session.
        embedding_service: EmbeddingService instance for embedding text.
        applied_pattern_ids: Optional list of MetaPattern IDs applied to
            this optimization — used to inject a pattern-based prior.

    Returns:
        TaxonomyMapping.  cluster_id is None when no active node
        has cosine similarity >= DOMAIN_ALIGNMENT_FLOOR.
    """
    # Embed domain_raw
    query_emb = await embedding_service.aembed_single(domain_raw)

    # Optional 70/30 Bayesian blend with pattern centroid
    if applied_pattern_ids:
        pattern_centroid = await compute_pattern_centroid(
            db, applied_pattern_ids
        )
        if pattern_centroid is not None:
            # 70 % analyzer, 30 % pattern prior
            blended = 0.7 * query_emb + 0.3 * pattern_centroid
            norm = np.linalg.norm(blended)
            if norm > 0:
                query_emb = blended / norm

    # Load active PromptCluster centroids
    result = await db.execute(
        select(PromptCluster).where(PromptCluster.state == "active")
    )
    nodes = result.scalars().all()

    if not nodes:
        return TaxonomyMapping(
            cluster_id=None,
            taxonomy_label=None,
            taxonomy_breadcrumb=[],
            domain_raw=domain_raw,
        )

    # Build centroid list, skip corrupt rows
    valid_nodes: list[PromptCluster] = []
    centroids: list[np.ndarray] = []
    for node in nodes:
        try:
            c = np.frombuffer(node.centroid_embedding, dtype=np.float32)
            if c.shape[0] != query_emb.shape[0]:
                logger.warning(
                    "PromptCluster '%s' centroid dim %d != query dim %d — skipped",
                    node.label,
                    c.shape[0],
                    query_emb.shape[0],
                )
                continue
            centroids.append(c)
            valid_nodes.append(node)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "PromptCluster '%s' has corrupt centroid: %s — skipped",
                node.label,
                exc,
            )

    if not centroids:
        return TaxonomyMapping(
            cluster_id=None,
            taxonomy_label=None,
            taxonomy_breadcrumb=[],
            domain_raw=domain_raw,
        )

    # Nearest centroid search
    matches = EmbeddingService.cosine_search(query_emb, centroids, top_k=1)
    if not matches:
        return TaxonomyMapping(
            cluster_id=None,
            taxonomy_label=None,
            taxonomy_breadcrumb=[],
            domain_raw=domain_raw,
        )

    idx, score = matches[0]
    if score < DOMAIN_ALIGNMENT_FLOOR:
        return TaxonomyMapping(
            cluster_id=None,
            taxonomy_label=None,
            taxonomy_breadcrumb=[],
            domain_raw=domain_raw,
        )

    best_node = valid_nodes[idx]
    breadcrumb = await build_breadcrumb(db, best_node)

    return TaxonomyMapping(
        cluster_id=best_node.id,
        taxonomy_label=best_node.label,
        taxonomy_breadcrumb=breadcrumb,
        domain_raw=domain_raw,
    )
