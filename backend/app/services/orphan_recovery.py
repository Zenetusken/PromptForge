"""OrphanRecoveryService — detect and recover taxonomy orphan optimizations.

Orphan optimizations are rows where ``process_optimization()`` failed
mid-transaction, leaving ``embedding IS NULL`` while ``overall_score IS NOT NULL``.
This service scans for stale orphans, recomputes their embeddings, assigns
clusters, and creates the missing ``OptimizationPattern`` join record.

Copyright 2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Optimization, OptimizationPattern, PromptCluster
from app.services.taxonomy._constants import _utcnow
from app.services.taxonomy.event_logger import get_event_logger
from app.services.taxonomy.family_ops import assign_cluster
from app.utils.text_cleanup import parse_domain

if TYPE_CHECKING:
    from app.services.taxonomy.engine import TaxonomyEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STALENESS_MINUTES = 5
_MAX_ORPHANS_PER_SCAN = 20
_MAX_RETRY_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class OrphanRecoveryService:
    """Scans for and recovers orphan optimizations missing embeddings."""

    def __init__(self) -> None:
        self._orphan_count: int = 0
        self._recovered_total: int = 0
        self._failed_total: int = 0
        self._last_scan_at: datetime | None = None
        self._last_recovery_at: datetime | None = None
        self._in_progress: set[str] = set()

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    async def _scan_orphans(self, db: AsyncSession) -> list[Optimization]:
        """Find orphan optimizations older than the staleness threshold.

        Orphans have ``embedding IS NULL``, ``overall_score IS NOT NULL``,
        ``raw_prompt IS NOT NULL``, and ``created_at`` older than
        ``_STALENESS_MINUTES``.  Post-filters out rows with
        ``heuristic_flags.recovery_exhausted == True``.
        """
        cutoff = _utcnow() - __import__("datetime").timedelta(minutes=_STALENESS_MINUTES)

        stmt = (
            select(Optimization)
            .where(
                Optimization.embedding.is_(None),
                Optimization.overall_score.isnot(None),
                Optimization.raw_prompt.isnot(None),
                Optimization.created_at < cutoff,
            )
            .limit(_MAX_ORPHANS_PER_SCAN)
        )
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())

        # Post-filter: skip rows flagged as recovery_exhausted
        orphans: list[Optimization] = []
        for opt in candidates:
            flags = opt.heuristic_flags
            if isinstance(flags, dict) and flags.get("recovery_exhausted"):
                continue
            orphans.append(opt)

        return orphans

    # ------------------------------------------------------------------
    # Recover one
    # ------------------------------------------------------------------

    async def _recover_one(
        self,
        optimization_id: str,
        db: AsyncSession,
        engine: TaxonomyEngine,
    ) -> bool:
        """Attempt to recover a single orphan optimization.

        Returns True on success, False if skipped or budget exhausted.
        Raises on unexpected errors (caller handles retry accounting).
        """
        # Concurrency guard
        if optimization_id in self._in_progress:
            logger.debug("Skipping %s — already in progress", optimization_id)
            return False
        self._in_progress.add(optimization_id)
        try:
            return await self._do_recover(optimization_id, db, engine)
        finally:
            self._in_progress.discard(optimization_id)

    async def _do_recover(
        self,
        optimization_id: str,
        db: AsyncSession,
        engine: TaxonomyEngine,
    ) -> bool:
        """Inner recovery logic (runs inside concurrency guard)."""
        result = await db.execute(
            select(Optimization).where(Optimization.id == optimization_id)
        )
        opt = result.scalar_one_or_none()
        if opt is None:
            return False

        # Idempotent: skip if embedding already set
        if opt.embedding is not None:
            return False

        # Check retry budget
        flags = opt.heuristic_flags if isinstance(opt.heuristic_flags, dict) else {}
        attempts = flags.get("recovery_attempts", 0)
        if attempts >= _MAX_RETRY_ATTEMPTS:
            flags["recovery_exhausted"] = True
            opt.heuristic_flags = {**flags}
            return False

        # Compute embeddings OUTSIDE write transaction
        embedding_svc = engine._embedding
        raw_emb = await embedding_svc.aembed_single(opt.raw_prompt)
        opt.embedding = raw_emb.astype(np.float32).tobytes()

        if opt.optimized_prompt:
            optimized_emb = await embedding_svc.aembed_single(opt.optimized_prompt)
            opt.optimized_embedding = optimized_emb.astype(np.float32).tobytes()

            # Transformation vector: direction of improvement
            transform = optimized_emb - raw_emb
            t_norm = np.linalg.norm(transform)
            if t_norm > 1e-9:
                transform = transform / t_norm
            opt.transformation_embedding = transform.astype(np.float32).tobytes()

        # If cluster_id points to an archived cluster, clear it
        if opt.cluster_id:
            cluster_q = await db.execute(
                select(PromptCluster).where(PromptCluster.id == opt.cluster_id)
            )
            existing_cluster = cluster_q.scalar_one_or_none()
            if existing_cluster and existing_cluster.state == "archived":
                opt.cluster_id = None

        # Assign cluster if needed
        if not opt.cluster_id:
            domain_primary, _ = parse_domain(opt.domain or "general")
            cluster = await assign_cluster(
                db=db,
                embedding=raw_emb,
                label=opt.intent_label or "general",
                domain=domain_primary,
                task_type=opt.task_type or "general",
                overall_score=opt.overall_score,
                embedding_index=engine._embedding_index,
                project_id=opt.project_id,
            )
            opt.cluster_id = cluster.id
            engine.mark_dirty(cluster.id, project_id=opt.project_id)

        # Create OptimizationPattern (source) if not exists
        existing_pattern = await db.execute(
            select(OptimizationPattern).where(
                OptimizationPattern.optimization_id == optimization_id,
                OptimizationPattern.relationship == "source",
            )
        )
        if not existing_pattern.scalars().first():
            db.add(OptimizationPattern(
                optimization_id=optimization_id,
                cluster_id=opt.cluster_id,
                relationship="source",
            ))

        await db.flush()
        return True

    # ------------------------------------------------------------------
    # Retry accounting
    # ------------------------------------------------------------------

    async def _increment_retry(
        self,
        optimization_id: str,
        db: AsyncSession,
        error: Exception,
    ) -> None:
        """Increment retry counter and record last error in heuristic_flags."""
        result = await db.execute(
            select(Optimization).where(Optimization.id == optimization_id)
        )
        opt = result.scalar_one_or_none()
        if opt is None:
            return

        flags = opt.heuristic_flags if isinstance(opt.heuristic_flags, dict) else {}
        attempts = flags.get("recovery_attempts", 0) + 1
        flags["recovery_attempts"] = attempts
        flags["recovery_last_error"] = str(error)[:500]
        if attempts >= _MAX_RETRY_ATTEMPTS:
            flags["recovery_exhausted"] = True
        opt.heuristic_flags = {**flags}

        await db.commit()

    # ------------------------------------------------------------------
    # Full scan-and-recover cycle
    # ------------------------------------------------------------------

    async def scan_and_recover(
        self,
        session_factory: Callable[..., Any],
        engine: TaxonomyEngine,
    ) -> dict[str, Any]:
        """Run a full orphan scan and recovery cycle.

        Args:
            session_factory: Callable that returns an async context manager
                yielding an ``AsyncSession``.
            engine: The ``TaxonomyEngine`` instance for embeddings and
                cluster assignment.

        Returns:
            Dict with scan/recovery statistics.
        """
        self._last_scan_at = _utcnow()

        # Phase 1: scan in one session
        async with session_factory() as scan_db:
            orphans = await self._scan_orphans(scan_db)
            orphan_ids = [o.id for o in orphans]

        self._orphan_count = len(orphan_ids)

        try:
            get_event_logger().log_decision(
                path="warm",
                op="recovery",
                decision="scan",
                context={"orphan_count": len(orphan_ids)},
            )
        except (RuntimeError, Exception):
            pass

        recovered = 0
        failed = 0

        # Phase 2: per-orphan recovery in fresh sessions
        for oid in orphan_ids:
            try:
                async with session_factory() as db:
                    success = await self._recover_one(oid, db, engine)
                    if success:
                        await db.commit()
                        recovered += 1
                        self._last_recovery_at = _utcnow()

                        try:
                            get_event_logger().log_decision(
                                path="warm",
                                op="recovery",
                                decision="success",
                                context={"optimization_id": oid},
                            )
                        except (RuntimeError, Exception):
                            pass
                    else:
                        # Skipped (idempotent or exhausted) — still commit flags
                        await db.commit()
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Orphan recovery failed for %s: %s", oid, exc,
                )
                try:
                    async with session_factory() as retry_db:
                        await self._increment_retry(oid, retry_db, exc)
                except Exception:
                    logger.exception("Failed to increment retry for %s", oid)

                try:
                    get_event_logger().log_decision(
                        path="warm",
                        op="recovery",
                        decision="failed",
                        context={
                            "optimization_id": oid,
                            "error": str(exc)[:200],
                        },
                    )
                except (RuntimeError, Exception):
                    pass

        self._recovered_total += recovered
        self._failed_total += failed

        return {
            "scanned": len(orphan_ids),
            "recovered": recovered,
            "failed": failed,
            "recovered_total": self._recovered_total,
            "failed_total": self._failed_total,
        }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Return current recovery counters for the health endpoint."""
        return {
            "orphan_count": self._orphan_count,
            "recovered_total": self._recovered_total,
            "failed_total": self._failed_total,
            "last_scan_at": self._last_scan_at.isoformat() if self._last_scan_at else None,
            "last_recovery_at": self._last_recovery_at.isoformat() if self._last_recovery_at else None,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

recovery_service = OrphanRecoveryService()
