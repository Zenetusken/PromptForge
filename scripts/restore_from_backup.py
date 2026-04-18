"""Restore optimizations from a pre-taxonomy backup DB into the current schema.

Zero-LLM restore. Reuses the backup's raw prompts, optimized prompts, scores,
strategies, and analysis metadata verbatim. Rebuilds only the deterministic
fields the current schema requires (4 embeddings, task_type/domain/intent
via heuristic analyzer, taxonomy cluster assignment via cosine similarity).

Safe by construction:
  - Idempotent via raw-prompt hash dedupe (re-running skips already-restored rows)
  - Dry-run mode prints what would happen without writing
  - Refuses to run while services are up unless --force is passed

Usage:
    source backend/.venv/bin/activate
    ./init.sh stop
    python scripts/restore_from_backup.py --dry-run
    python scripts/restore_from_backup.py
    ./init.sh start

Copyright 2026 Project Synthesis contributors.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.models import Optimization, OptimizationPattern  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402
from app.services.heuristic_analyzer import HeuristicAnalyzer  # noqa: E402
from app.services.taxonomy.engine import TaxonomyEngine  # noqa: E402
from app.services.taxonomy.family_ops import assign_cluster  # noqa: E402
from app.services.taxonomy.embedding_index import EmbeddingIndex  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("restore")


DEFAULT_BACKUP = REPO_ROOT / "data" / "synthesis.db.pre-knowledge-graph"
DEFAULT_TARGET = REPO_ROOT / "data" / "synthesis.db"
PID_DIR = REPO_ROOT / "data" / "pids"


@dataclass
class BackupRow:
    id: str
    created_at: str
    raw_prompt: str
    optimized_prompt: str | None
    task_type: str | None
    strategy_used: str | None
    changes_summary: str | None
    score_clarity: float | None
    score_specificity: float | None
    score_structure: float | None
    score_faithfulness: float | None
    score_conciseness: float | None
    overall_score: float | None
    provider: str | None
    model_used: str | None
    scoring_mode: str | None
    duration_ms: int | None
    status: str
    trace_id: str | None
    tokens_total: int | None
    tokens_by_phase: Any
    context_sources: Any
    original_scores: Any
    score_deltas: Any
    intent_label: str | None
    domain: str | None


def _services_running() -> list[str]:
    """Return list of running service pid files."""
    running: list[str] = []
    if not PID_DIR.is_dir():
        return running
    for pid_file in PID_DIR.glob("*.pid"):
        try:
            pid = int(pid_file.read_text().strip())
            (Path("/proc") / str(pid)).stat()
            running.append(pid_file.stem)
        except (OSError, ValueError):
            continue
    return running


def load_backup_rows(backup_path: Path) -> list[BackupRow]:
    """Load completed + analyzed rows from the backup DB."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT id, created_at, raw_prompt, optimized_prompt, task_type,
               strategy_used, changes_summary,
               score_clarity, score_specificity, score_structure,
               score_faithfulness, score_conciseness, overall_score,
               provider, model_used, scoring_mode, duration_ms,
               status, trace_id, tokens_total, tokens_by_phase,
               context_sources, original_scores, score_deltas,
               intent_label, domain
        FROM optimizations
        WHERE status IN ('completed', 'analyzed')
          AND raw_prompt IS NOT NULL
          AND raw_prompt != ''
        ORDER BY created_at ASC
        """
    )
    rows = [BackupRow(**dict(r)) for r in cur.fetchall()]
    conn.close()
    return rows


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


async def existing_hashes(db: AsyncSession) -> set[str]:
    """SHA-16 of all raw_prompts currently in the target DB — idempotency guard."""
    result = await db.execute(select(Optimization.raw_prompt))
    return {prompt_hash(rp) for rp in result.scalars().all()}


def parse_created_at(raw: str) -> Any:
    """Parse backup's TEXT timestamp to a naive UTC datetime."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


async def restore_one(
    row: BackupRow,
    db: AsyncSession,
    embedding_svc: EmbeddingService,
    analyzer: HeuristicAnalyzer,
    engine: TaxonomyEngine,
    embedding_index: EmbeddingIndex,
    *,
    dry_run: bool,
) -> tuple[str, str]:
    """Insert one row + assign cluster. Returns (action, detail)."""
    raw_emb = await embedding_svc.aembed_single(row.raw_prompt)
    opt_emb = None
    xfm_emb = None
    if row.optimized_prompt:
        opt_emb = await embedding_svc.aembed_single(row.optimized_prompt)
        transform = opt_emb - raw_emb
        t_norm = float(np.linalg.norm(transform))
        if t_norm > 1e-9:
            xfm_emb = (transform / t_norm).astype(np.float32)

    analysis = await analyzer.analyze(row.raw_prompt, db, enable_llm_fallback=False)
    task_type = row.task_type or analysis.task_type
    domain_raw = row.domain or analysis.domain or "general"
    domain_primary = domain_raw.split(":", 1)[0].strip() or "general"
    intent_label = row.intent_label or analysis.intent_label or "general"

    if dry_run:
        return (
            "would-insert",
            f"task={task_type} domain={domain_primary} intent={intent_label!r} "
            f"score={row.overall_score}",
        )

    new_id = str(uuid.uuid4())
    opt = Optimization(
        id=new_id,
        created_at=parse_created_at(row.created_at),
        raw_prompt=row.raw_prompt,
        optimized_prompt=row.optimized_prompt,
        task_type=task_type,
        strategy_used=row.strategy_used,
        changes_summary=row.changes_summary,
        score_clarity=row.score_clarity,
        score_specificity=row.score_specificity,
        score_structure=row.score_structure,
        score_faithfulness=row.score_faithfulness,
        score_conciseness=row.score_conciseness,
        overall_score=row.overall_score,
        provider=row.provider,
        model_used=row.model_used,
        scoring_mode=row.scoring_mode,
        duration_ms=row.duration_ms,
        status=row.status,
        trace_id=row.trace_id,
        tokens_total=row.tokens_total,
        tokens_by_phase=row.tokens_by_phase,
        context_sources=row.context_sources,
        original_scores=row.original_scores,
        score_deltas=row.score_deltas,
        intent_label=intent_label,
        domain=domain_primary,
        domain_raw=domain_raw,
        embedding=raw_emb.astype(np.float32).tobytes(),
        optimized_embedding=(
            opt_emb.astype(np.float32).tobytes() if opt_emb is not None else None
        ),
        transformation_embedding=(
            xfm_emb.tobytes() if xfm_emb is not None else None
        ),
    )
    db.add(opt)
    await db.flush()

    cluster = await assign_cluster(
        db=db,
        embedding=raw_emb,
        label=intent_label,
        domain=domain_primary,
        task_type=task_type,
        overall_score=row.overall_score,
        embedding_index=embedding_index,
        project_id=None,
    )
    opt.cluster_id = cluster.id

    db.add(OptimizationPattern(
        optimization_id=new_id,
        cluster_id=cluster.id,
        relationship="source",
    ))

    return ("inserted", f"cluster={cluster.label or cluster.id[:8]} → {domain_primary}")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true",
                    help="Bypass running-service check")
    args = ap.parse_args()

    if not args.force:
        running = _services_running()
        if running:
            logger.error(
                "Services appear to be running: %s. Stop them (./init.sh stop) "
                "or pass --force.", ", ".join(running),
            )
            return 2

    if not args.target.exists():
        logger.error("Target DB not found: %s", args.target)
        return 2

    rows = load_backup_rows(args.backup)
    logger.info("Backup: %d usable rows (completed + analyzed)", len(rows))
    if args.limit:
        rows = rows[: args.limit]
        logger.info("Limit applied: %d rows", len(rows))

    engine = create_async_engine(f"sqlite+aiosqlite:///{args.target}", echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    embedding_svc = EmbeddingService()
    analyzer = HeuristicAnalyzer()
    taxonomy_engine = TaxonomyEngine(embedding_service=embedding_svc)
    embedding_index = EmbeddingIndex()

    inserted = 0
    skipped = 0
    errors = 0
    t0 = time.monotonic()

    async with Session() as db:
        seen = await existing_hashes(db)
        logger.info("Target DB: %d existing prompts (dedupe set)", len(seen))

        for i, row in enumerate(rows, 1):
            h = prompt_hash(row.raw_prompt)
            if h in seen:
                skipped += 1
                logger.info("[%3d/%d] skip (duplicate): %s",
                            i, len(rows), row.raw_prompt[:60])
                continue
            try:
                action, detail = await restore_one(
                    row, db, embedding_svc, analyzer,
                    taxonomy_engine, embedding_index, dry_run=args.dry_run,
                )
                logger.info("[%3d/%d] %s: %s — %s",
                            i, len(rows), action, row.raw_prompt[:50], detail)
                seen.add(h)
                if action == "inserted":
                    inserted += 1
            except Exception as exc:
                errors += 1
                logger.exception("[%3d/%d] ERROR on %s: %s",
                                 i, len(rows), row.id, exc)

        if args.dry_run:
            await db.rollback()
            logger.info("Dry run — rolled back.")
        else:
            await db.commit()
            logger.info("Committed.")

    await engine.dispose()
    elapsed = time.monotonic() - t0
    logger.info(
        "Done in %.1fs — inserted=%d skipped=%d errors=%d",
        elapsed, inserted, skipped, errors,
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
