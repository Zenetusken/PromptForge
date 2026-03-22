"""Handler for synthesis_save_result MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging
import uuid

from mcp.server.fastmcp import Context
from sqlalchemy import select

from app.config import PROMPTS_DIR, settings
from app.database import async_session_factory
from app.models import Optimization
from app.schemas.mcp_models import SaveResultOutput
from app.schemas.pipeline_contracts import DimensionScores
from app.services.event_notification import notify_event_bus
from app.services.heuristic_scorer import HeuristicScorer
from app.services.preferences import PreferencesService
from app.services.score_blender import blend_scores
from app.services.strategy_loader import StrategyLoader
from app.tools._shared import DATA_DIR

logger = logging.getLogger(__name__)


async def handle_save_result(
    trace_id: str,
    optimized_prompt: str,
    changes_summary: str | None,
    task_type: str | None,
    strategy_used: str | None,
    scores: dict | None,
    model: str | None,
    codebase_context: str | None,
    ctx: Context | None,
) -> SaveResultOutput:
    """Persist an optimization result from an external LLM."""
    logger.info("synthesis_save_result called: trace_id=%s model=%s", trace_id, model)

    # Normalize strategy_used — external LLMs often return verbose rationales
    if strategy_used:
        strategy_loader = StrategyLoader(PROMPTS_DIR / "strategies")
        known = strategy_loader.list_strategies()
        if strategy_used not in known:
            normalized = "auto"
            lower = strategy_used.lower()
            for name in known:
                if name != "auto" and name in lower:
                    normalized = name
                    break
            logger.info(
                "Strategy normalized: '%s' → '%s'",
                strategy_used[:80], normalized,
            )
            strategy_used = normalized

    # Check scoring preference
    prefs = PreferencesService(DATA_DIR)
    scoring_enabled = prefs.get("pipeline.enable_scoring")
    if scoring_enabled is None:
        scoring_enabled = True

    # Determine scoring mode and compute final scores
    clean_scores: dict[str, float] = {}
    heuristic_flags: list[str] = []
    scoring_mode = "skipped" if not scoring_enabled else "heuristic"

    if scores and scoring_enabled:
        scoring_mode = "hybrid_passthrough"
        for k, v in scores.items():
            try:
                clean_scores[k] = float(v)
            except (ValueError, TypeError):
                clean_scores[k] = 5.0

    # Persist — look up pending optimization created by prepare, or create new
    async with async_session_factory() as db:
        result = await db.execute(
            select(Optimization).where(Optimization.trace_id == trace_id)
        )
        opt = result.scalar_one_or_none()

        # Determine strategy compliance
        strategy_compliance = "unknown"
        if opt and opt.strategy_used and strategy_used:
            if opt.strategy_used == strategy_used:
                strategy_compliance = "matched"
            else:
                strategy_compliance = "partial"
                logger.info(
                    "Strategy mismatch: requested=%s, used=%s",
                    opt.strategy_used,
                    strategy_used,
                )
        elif strategy_used:
            strategy_compliance = "matched"

        # Compute scores
        heuristic_scores: dict[str, float] = {}
        final_scores: dict[str, float] = {}
        overall: float | None = None
        original_scores: dict[str, float] | None = None
        deltas: dict[str, float] | None = None

        if scoring_enabled:
            heuristic_scores = HeuristicScorer.score_prompt(
                optimized_prompt,
                original=opt.raw_prompt if opt and opt.raw_prompt else None,
            )

            if clean_scores:
                try:
                    corrected = HeuristicScorer.apply_bias_correction(clean_scores)
                    ide_scores_corrected = DimensionScores(
                        clarity=corrected.get("clarity", 5.0),
                        specificity=corrected.get("specificity", 5.0),
                        structure=corrected.get("structure", 5.0),
                        faithfulness=corrected.get("faithfulness", 5.0),
                        conciseness=corrected.get("conciseness", 5.0),
                    )

                    historical_stats: dict | None = None
                    try:
                        from app.services.optimization_service import OptimizationService
                        opt_svc = OptimizationService(db)
                        historical_stats = await opt_svc.get_score_distribution(
                            exclude_scoring_modes=["heuristic"],
                        )
                    except Exception as exc:
                        logger.debug("Could not fetch score distribution: %s", exc)

                    blended = blend_scores(
                        ide_scores_corrected, heuristic_scores, historical_stats,
                    )
                    blended_dims = blended.to_dimension_scores()
                    final_scores = {
                        "clarity": blended_dims.clarity,
                        "specificity": blended_dims.specificity,
                        "structure": blended_dims.structure,
                        "faithfulness": blended_dims.faithfulness,
                        "conciseness": blended_dims.conciseness,
                    }

                    heuristic_flags = blended.divergence_flags or []
                    scoring_mode = "hybrid_passthrough"

                except Exception as exc:
                    logger.warning("Hybrid blending failed, falling back to heuristic: %s", exc)
                    final_scores = heuristic_scores
                    scoring_mode = "heuristic"
            else:
                final_scores = heuristic_scores
                scoring_mode = "heuristic"

            overall = round(
                sum(final_scores.values()) / max(len(final_scores), 1), 2,
            )

            if opt and opt.raw_prompt:
                original_heur = HeuristicScorer.score_prompt(opt.raw_prompt)
                original_scores = original_heur
                deltas = {
                    dim: round(final_scores[dim] - original_scores[dim], 2)
                    for dim in final_scores
                    if dim in original_scores
                }

        # Truncate codebase context if provided
        context_snapshot = None
        if codebase_context:
            context_snapshot = codebase_context[: settings.MAX_CODEBASE_CONTEXT_CHARS]

        if opt:
            opt.optimized_prompt = optimized_prompt
            opt.task_type = task_type or opt.task_type or "general"
            opt.strategy_used = strategy_used or opt.strategy_used or "auto"
            opt.changes_summary = changes_summary or ""
            opt.score_clarity = final_scores.get("clarity")
            opt.score_specificity = final_scores.get("specificity")
            opt.score_structure = final_scores.get("structure")
            opt.score_faithfulness = final_scores.get("faithfulness")
            opt.score_conciseness = final_scores.get("conciseness")
            opt.overall_score = overall
            opt.original_scores = original_scores
            opt.score_deltas = deltas
            opt.model_used = model or "external"
            opt.scoring_mode = scoring_mode
            opt.status = "completed"
            if context_snapshot:
                opt.codebase_context_snapshot = context_snapshot
            opt_id = opt.id
        else:
            opt_id = str(uuid.uuid4())
            opt = Optimization(
                id=opt_id,
                raw_prompt="",
                optimized_prompt=optimized_prompt,
                task_type=task_type or "general",
                strategy_used=strategy_used or "auto",
                changes_summary=changes_summary or "",
                score_clarity=final_scores.get("clarity"),
                score_specificity=final_scores.get("specificity"),
                score_structure=final_scores.get("structure"),
                score_faithfulness=final_scores.get("faithfulness"),
                score_conciseness=final_scores.get("conciseness"),
                overall_score=overall,
                provider="mcp_passthrough",
                model_used=model or "external",
                scoring_mode=scoring_mode,
                status="completed",
                trace_id=trace_id,
                codebase_context_snapshot=context_snapshot,
            )
            db.add(opt)

        await db.commit()

        await notify_event_bus("optimization_created", {
            "id": opt_id,
            "trace_id": trace_id,
            "task_type": opt.task_type,
            "strategy_used": opt.strategy_used,
            "overall_score": overall,
            "provider": opt.provider,
            "status": "completed",
        })

    logger.info(
        "synthesis_save_result completed: optimization_id=%s strategy_compliance=%s flags=%d",
        opt_id, strategy_compliance, len(heuristic_flags),
    )

    return SaveResultOutput(
        optimization_id=opt_id,
        scoring_mode=scoring_mode,
        scores={k: round(v, 2) for k, v in final_scores.items()} if final_scores else {},
        original_scores=original_scores,
        score_deltas=deltas,
        overall_score=overall,
        strategy_compliance=strategy_compliance,
        heuristic_flags=heuristic_flags,
    )
