"""Shared cluster split logic — member-level HDBSCAN + k-means fallback.

Extracted from warm_phases.py to be reusable by both warm-path leaf splits
and cold-path mega-cluster splits. The function receives pre-fetched
Optimization embedding rows and handles:
  1. Blended embedding construction
  2. HDBSCAN clustering (min_cluster_size=3)
  3. K-means bisection fallback when HDBSCAN finds < 2 clusters
  4. Child node creation with Haiku labeling
  5. Optimization reassignment to children
  6. Noise point reassignment to nearest child
  7. Parent node archival

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Optimization, PromptCluster
from app.services.taxonomy._constants import SPLIT_MIN_MEMBERS, _utcnow
from app.services.taxonomy.cluster_meta import write_meta
from app.services.taxonomy.clustering import (
    batch_cluster,
    blend_embeddings,
    compute_pairwise_coherence,
    cosine_similarity,
    l2_normalize_1d,
)
from app.services.taxonomy.event_logger import get_event_logger
from app.services.taxonomy.family_ops import merge_score_into_cluster
from app.services.taxonomy.projection import interpolate_position

if TYPE_CHECKING:
    from app.services.taxonomy.engine import TaxonomyEngine

logger = logging.getLogger(__name__)


@dataclass
class SplitResult:
    """Outcome of a split_cluster() attempt."""

    success: bool
    children_created: int
    noise_reassigned: int
    children: list[PromptCluster] = field(default_factory=list)


async def split_cluster(
    node: PromptCluster,
    engine: TaxonomyEngine,
    db: AsyncSession,
    opt_rows: list[tuple[str, bytes, bytes | None, bytes | None]],
    log_path: str = "warm",
) -> SplitResult:
    """Split a cluster into sub-clusters using member-level HDBSCAN.

    Args:
        node: The PromptCluster to split.
        engine: TaxonomyEngine instance (for provider, indices).
        db: Active async session (caller manages commit/rollback).
        opt_rows: Pre-fetched (opt_id, embedding_bytes, optimized_bytes,
                  transformation_bytes) tuples for this cluster's members.

    Returns:
        SplitResult indicating success and what was created.
    """
    # Build blended + raw embeddings
    child_embs: list[np.ndarray] = []       # raw (for centroid storage)
    child_blended: list[np.ndarray] = []    # blended (for HDBSCAN)
    child_opt_ids: list[str] = []
    for opt_id, emb_bytes, opt_bytes, trans_bytes in opt_rows:
        try:
            raw = np.frombuffer(emb_bytes, dtype=np.float32).copy()
            opt_emb = (
                np.frombuffer(opt_bytes, dtype=np.float32).copy()
                if opt_bytes else None
            )
            trans_emb = (
                np.frombuffer(trans_bytes, dtype=np.float32).copy()
                if trans_bytes else None
            )
            child_embs.append(raw)
            child_blended.append(blend_embeddings(
                raw=raw, optimized=opt_emb, transformation=trans_emb,
            ))
            child_opt_ids.append(opt_id)
        except (ValueError, TypeError):
            continue

    if len(child_blended) < SPLIT_MIN_MEMBERS:
        return SplitResult(success=False, children_created=0, noise_reassigned=0)

    # HDBSCAN
    split_result = batch_cluster(child_blended, min_cluster_size=3)
    used_kmeans_fallback = False

    # K-means bisection fallback
    if (
        split_result.n_clusters < 2
        and len(child_blended) >= 2 * SPLIT_MIN_MEMBERS
    ):
        try:
            from sklearn.cluster import KMeans

            emb_stack = np.stack(child_blended, axis=0)
            km = KMeans(n_clusters=2, n_init=10, random_state=42)
            km_labels = km.fit_predict(emb_stack)
            sizes = [int((km_labels == c).sum()) for c in range(2)]
            if all(s >= 3 for s in sizes):
                centroids = [
                    l2_normalize_1d(km.cluster_centers_[c].astype(np.float32))
                    for c in range(2)
                ]
                split_result = type(split_result)(
                    labels=km_labels,
                    centroids=centroids,
                    n_clusters=2,
                    persistences=[0.5, 0.5],
                    noise_count=0,
                )
                used_kmeans_fallback = True
                logger.info(
                    "HDBSCAN failed, k-means bisection succeeded: %s members",
                    sizes,
                )
        except Exception as km_exc:
            logger.debug("k-means fallback failed: %s", km_exc)

    if split_result.n_clusters < 2:
        try:
            get_event_logger().log_decision(
                path=log_path, op="error", decision="split_failed",
                cluster_id=node.id,
                context={
                    "source": "split_cluster",
                    "error_type": "insufficient_clusters",
                    "error_message": f"HDBSCAN produced {split_result.n_clusters} clusters from {len(child_blended)} members",
                    "recovery": "skipped",
                    "stack_trace": "",
                },
            )
        except RuntimeError:
            pass
        return SplitResult(success=False, children_created=0, noise_reassigned=0)

    # Log algorithm result before child creation
    try:
        get_event_logger().log_decision(
            path=log_path, op="split", decision="algorithm_result",
            cluster_id=node.id,
            context={
                "hdbscan_clusters": int(split_result.n_clusters),
                "noise_count": int(split_result.noise_count),
                "fallback": "kmeans" if used_kmeans_fallback else "none",
                "total_members": len(child_blended),
            },
        )
    except RuntimeError:
        pass

    # Create child clusters — 3-phase approach for parallel label generation.
    # Phase 1: Collect per-cluster data (sequential DB queries, fast).
    # Phase 2: Parallel label generation via asyncio.gather (LLM calls, no DB).
    # Phase 3: Create PromptCluster objects with resolved labels (sequential).
    from app.services.taxonomy.coloring import generate_color
    from app.services.taxonomy.labeling import generate_label

    parent_domain = node.domain or "general"
    parent_id_for_children = node.parent_id or node.id
    new_children: list[PromptCluster] = []
    t0_split = time.monotonic()

    # --- Phase 1: Collect per-cluster data (sequential, fast) ---
    cluster_data: list[dict] = []
    for cid in range(split_result.n_clusters):
        mask = split_result.labels == cid
        group_opt_ids = [
            child_opt_ids[i] for i in range(len(child_opt_ids)) if mask[i]
        ]
        group_embs = [
            child_embs[i] for i in range(len(child_embs)) if mask[i]
        ]
        if not group_embs:
            continue

        centroid = l2_normalize_1d(
            np.mean(np.stack(group_embs), axis=0).astype(np.float32)
        )
        child_coherence = compute_pairwise_coherence(group_embs)

        # DB queries for member texts and scores (fast, local)
        opt_labels_q = await db.execute(
            select(Optimization.intent_label)
            .where(Optimization.id.in_(group_opt_ids))
            .limit(10)
        )
        member_texts = [r[0] for r in opt_labels_q.all() if r[0]]

        score_q = await db.execute(
            select(
                func.avg(Optimization.overall_score),
                func.count(Optimization.overall_score),
            ).where(
                Optimization.id.in_(group_opt_ids),
                Optimization.overall_score.isnot(None),
            )
        )
        score_row = score_q.one()

        cluster_data.append({
            "group_opt_ids": group_opt_ids,
            "centroid": centroid,
            "coherence": child_coherence,
            "member_texts": member_texts,
            "avg_score": round(score_row[0], 2) if score_row[0] is not None else None,
            "scored_count": score_row[1] or 0,
        })

    if len(cluster_data) < 2:
        return SplitResult(success=False, children_created=0, noise_reassigned=0)

    # --- Phase 2: Parallel label generation (LLM calls, no DB session) ---
    t0_labels = time.monotonic()
    label_tasks = [
        generate_label(
            provider=engine._provider,
            member_texts=cd["member_texts"],
            model=settings.MODEL_HAIKU,
        )
        for cd in cluster_data
    ]
    labels = await asyncio.gather(*label_tasks, return_exceptions=True)
    for i, lbl in enumerate(labels):
        if isinstance(lbl, BaseException):
            labels[i] = "Unnamed Cluster"
    label_duration_ms = int((time.monotonic() - t0_labels) * 1000)

    # --- Phase 3: Create PromptCluster objects with resolved labels ---
    from datetime import datetime, timedelta, timezone

    for i, cd in enumerate(cluster_data):
        label = labels[i]
        centroid = cd["centroid"]

        child_node = PromptCluster(
            label=label,
            centroid_embedding=centroid.astype(np.float32).tobytes(),
            member_count=len(cd["group_opt_ids"]),
            scored_count=cd["scored_count"],
            avg_score=cd["avg_score"],
            coherence=cd["coherence"],
            state="active",
            domain=parent_domain,
            parent_id=parent_id_for_children,
            color_hex=generate_color(0.0, 0.0, 0.0),
        )
        db.add(child_node)
        await db.flush()

        # Interpolate UMAP position from positioned siblings or parent
        siblings = []
        for existing in new_children:
            if existing.umap_x is not None and existing.centroid_embedding:
                sib_emb = np.frombuffer(
                    existing.centroid_embedding, dtype=np.float32
                )
                siblings.append(
                    (sib_emb, existing.umap_x, existing.umap_y, existing.umap_z)
                )
        if siblings:
            pos = interpolate_position(centroid, siblings)
            if pos:
                child_node.umap_x, child_node.umap_y, child_node.umap_z = pos
        elif node.umap_x is not None:
            child_node.umap_x = node.umap_x + random.uniform(-0.5, 0.5)
            child_node.umap_y = node.umap_y + random.uniform(-0.5, 0.5)
            child_node.umap_z = node.umap_z + random.uniform(-0.5, 0.5)
        # Protect from merge for 30 minutes.
        # INVARIANT: merge_protected_until is stored as naive UTC (no tzinfo).
        # All comparisons use _utcnow() which is also naive UTC.
        # Do NOT compare with timezone-aware datetimes.
        merge_until = (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(tzinfo=None)
        child_node.cluster_metadata = write_meta(
            child_node.cluster_metadata,
            position_source="interpolated",
            merge_protected_until=merge_until.isoformat(),
        )

        # Reassign optimizations
        await db.execute(
            sa_update(Optimization)
            .where(Optimization.id.in_(cd["group_opt_ids"]))
            .values(cluster_id=child_node.id)
        )
        new_children.append(child_node)
        logger.info(
            "  Split child '%s' (%d members, coherence=%.3f)",
            label, len(cd["group_opt_ids"]), cd["coherence"],
        )
        try:
            get_event_logger().log_decision(
                path=log_path, op="split", decision="child_created",
                cluster_id=child_node.id,
                context={
                    "parent_id": node.id,
                    "parent_label": node.label,
                    "child_label": label,
                    "members": len(cd["group_opt_ids"]),
                    "coherence": round(cd["coherence"], 4),
                },
            )
        except RuntimeError:
            pass

    if len(new_children) < 2:
        return SplitResult(success=False, children_created=0, noise_reassigned=0)

    # Archive parent
    node.state = "archived"
    node.archived_at = _utcnow()
    node.member_count = 0
    node.scored_count = 0
    node.usage_count = 0
    node.avg_score = None
    await engine._embedding_index.remove(node.id)
    await engine._transformation_index.remove(node.id)
    await engine._optimized_index.remove(node.id)

    # Upsert children into embedding index
    for child in new_children:
        c_emb = np.frombuffer(child.centroid_embedding, dtype=np.float32)
        await engine._embedding_index.upsert(child.id, c_emb)

    # Reassign noise to nearest child
    noise_reassigned = 0
    noise_ids = [
        child_opt_ids[i]
        for i in range(len(child_opt_ids))
        if split_result.labels[i] == -1
    ]
    if noise_ids:
        noise_emb_lookup: dict[str, bytes] = {}
        for opt_id, emb_bytes, *_ in opt_rows:
            if opt_id in set(noise_ids):
                noise_emb_lookup[opt_id] = emb_bytes

        noise_score_q = await db.execute(
            select(Optimization.id, Optimization.overall_score)
            .where(Optimization.id.in_(noise_ids))
        )
        noise_score_lookup = {r[0]: r[1] for r in noise_score_q.all()}

        for nid in noise_ids:
            n_bytes = noise_emb_lookup.get(nid)
            if not n_bytes:
                continue
            n_emb = np.frombuffer(n_bytes, dtype=np.float32)
            best_c, best_s = None, -1.0
            for ch in new_children:
                c_emb = np.frombuffer(ch.centroid_embedding, dtype=np.float32)
                s = cosine_similarity(n_emb, c_emb)
                if s > best_s:
                    best_s, best_c = s, ch
            if best_c:
                await db.execute(
                    sa_update(Optimization)
                    .where(Optimization.id == nid)
                    .values(cluster_id=best_c.id)
                )
                best_c.member_count = (best_c.member_count or 0) + 1
                merge_score_into_cluster(best_c, noise_score_lookup.get(nid))
                noise_reassigned += 1

    if noise_reassigned > 0:
        try:
            get_event_logger().log_decision(
                path=log_path, op="split", decision="noise_reassigned",
                cluster_id=node.id,
                context={"noise_reassigned": noise_reassigned, "total_noise": len(noise_ids)},
            )
        except RuntimeError:
            pass

    # Compute per-child separation (min cosine distance to any sibling)
    if len(new_children) >= 2:
        child_centroids = []
        for ch in new_children:
            try:
                child_centroids.append(
                    np.frombuffer(ch.centroid_embedding, dtype=np.float32)
                )
            except (ValueError, TypeError):
                child_centroids.append(np.zeros(384, dtype=np.float32))
        for i, ch in enumerate(new_children):
            min_dist = 1.0
            for j, other_c in enumerate(child_centroids):
                if i == j:
                    continue
                sim = float(np.dot(
                    child_centroids[i] / max(np.linalg.norm(child_centroids[i]), 1e-9),
                    other_c / max(np.linalg.norm(other_c), 1e-9),
                ))
                dist = 1.0 - sim
                if dist < min_dist:
                    min_dist = dist
            ch.separation = min_dist

    # Compute output coherence per child from optimized_embeddings
    for ch in new_children:
        try:
            oe_q = await db.execute(
                select(Optimization.optimized_embedding).where(
                    Optimization.cluster_id == ch.id,
                    Optimization.optimized_embedding.isnot(None),
                )
            )
            opt_embs = []
            for (oe_bytes,) in oe_q.all():
                try:
                    oe = np.frombuffer(oe_bytes, dtype=np.float32)
                    if oe.shape[0] == 384:
                        opt_embs.append(oe / max(np.linalg.norm(oe), 1e-9))
                except (ValueError, TypeError):
                    continue
            if len(opt_embs) >= 2:
                out_coh = compute_pairwise_coherence(opt_embs)
                ch.cluster_metadata = write_meta(
                    ch.cluster_metadata, output_coherence=round(out_coh, 4),
                )
        except Exception:
            pass  # Non-fatal

    # Defer meta-pattern extraction to warm-path Phase 4 (Refresh).
    # Mark all children as pattern_stale=True so Phase 4 picks them up.
    # This removes 15+ sequential Haiku LLM calls from the critical split path.
    for ch in new_children:
        ch.cluster_metadata = write_meta(
            ch.cluster_metadata,
            pattern_member_count=ch.member_count,
            pattern_stale=True,
        )

    await db.flush()
    logger.info(
        "Split '%s' -> %d sub-clusters (%d noise reassigned)",
        node.label, len(new_children), noise_reassigned,
    )

    split_duration_ms = int((time.monotonic() - t0_split) * 1000)
    try:
        get_event_logger().log_decision(
            path=log_path, op="split", decision="split_complete",
            cluster_id=node.id,
            duration_ms=split_duration_ms,
            context={
                "parent_label": node.label,
                "hdbscan_clusters": len(new_children),
                "noise_count": noise_reassigned,
                "silhouette": getattr(split_result, 'silhouette', None),
                "label_generation_ms": label_duration_ms,
                "children": [
                    {
                        "id": c.id,
                        "label": c.label,
                        "members": c.member_count or 0,
                        "coherence": round(c.coherence or 0.0, 4),
                    }
                    for c in new_children
                ],
                "fallback": (
                    "kmeans"
                    if split_result.n_clusters >= 2
                    and getattr(split_result, "persistences", None) == [0.5, 0.5]
                    else "none"
                ),
            },
        )
    except RuntimeError:
        pass

    return SplitResult(
        success=True,
        children_created=len(new_children),
        noise_reassigned=noise_reassigned,
        children=new_children,
    )
