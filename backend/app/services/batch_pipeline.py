"""In-memory batch optimization pipeline.

Runs N prompts through analyze → optimize → score → embed in parallel
with zero DB writes. Results accumulate as PendingOptimization objects.
Bulk persist writes everything in a single transaction.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.config import settings
from app.providers.base import LLMProvider
from app.services.embedding_service import EmbeddingService
from app.services.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


@dataclass
class PendingOptimization:
    """In-memory optimization result awaiting bulk persist."""

    id: str
    trace_id: str
    raw_prompt: str
    batch_id: str = ""  # Lineage: which batch produced this row
    optimized_prompt: str | None = None
    task_type: str | None = None
    strategy_used: str | None = None
    changes_summary: str | None = None
    score_clarity: float | None = None
    score_specificity: float | None = None
    score_structure: float | None = None
    score_faithfulness: float | None = None
    score_conciseness: float | None = None
    overall_score: float | None = None
    improvement_score: float | None = None
    scoring_mode: str | None = None
    intent_label: str | None = None
    domain: str | None = None
    domain_raw: str | None = None
    embedding: bytes | None = None
    optimized_embedding: bytes | None = None
    transformation_embedding: bytes | None = None
    models_by_phase: dict | None = None
    original_scores: dict | None = None
    score_deltas: dict | None = None
    duration_ms: int | None = None
    status: str = "completed"
    provider: str | None = None
    model_used: str | None = None
    routing_tier: str | None = None
    heuristic_flags: list | None = None
    suggestions: list | None = None
    context_sources: dict | None = None
    error: str | None = None  # Non-None if this prompt failed


async def run_single_prompt(
    raw_prompt: str,
    provider: LLMProvider,
    prompt_loader: PromptLoader,
    embedding_service: EmbeddingService,
    *,
    codebase_context: str | None = None,
    workspace_guidance: str | None = None,
    batch_id: str = "",
    agent_name: str = "",
    prompt_index: int = 0,
    total_prompts: int = 1,
) -> PendingOptimization:
    """Run one prompt through analyze → optimize → score → embed in memory.

    IMPORTANT: This function does NOT use PipelineOrchestrator. It makes
    direct provider calls following the same phase logic but without DB
    dependencies.

    Returns a PendingOptimization with all fields populated.
    On any phase failure, returns a PendingOptimization with error set
    and status="failed". Never raises — errors are captured in the result.
    """
    opt_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    t0 = time.monotonic()

    try:
        from app.config import DATA_DIR
        from app.providers.base import call_provider_with_retry
        from app.schemas.pipeline_contracts import (
            AnalysisResult,
            DimensionScores,
            OptimizationResult,
            ScoreResult,
        )
        from app.services.heuristic_scorer import HeuristicScorer
        from app.services.pipeline_constants import (
            ANALYZE_MAX_TOKENS,
            SCORE_MAX_TOKENS,
            VALID_TASK_TYPES,
            compute_optimize_max_tokens,
            resolve_effective_strategy,
            semantic_upgrade_general,
        )
        from app.services.preferences import PreferencesService
        from app.services.score_blender import blend_scores
        from app.services.strategy_loader import StrategyLoader
        from app.utils.text_cleanup import sanitize_optimization_result, title_case_label

        prefs = PreferencesService(DATA_DIR)
        prefs_snapshot = prefs.load()
        analyzer_model = prefs.resolve_model("analyzer", prefs_snapshot)
        optimizer_model = prefs.resolve_model("optimizer", prefs_snapshot)
        scorer_model = prefs.resolve_model("scorer", prefs_snapshot)

        system_prompt = prompt_loader.load("agent-guidance.md")
        strategy_loader = StrategyLoader(prompt_loader._prompts_dir / "strategies")
        available_strategies = strategy_loader.format_available()

        # --- Phase 1: Analyze ---
        analyze_msg = prompt_loader.render("analyze.md", {
            "raw_prompt": raw_prompt,
            "available_strategies": available_strategies,
            "known_domains": "backend, frontend, database, data, devops, security, fullstack, general",
        })
        analysis: AnalysisResult = await call_provider_with_retry(
            provider,
            model=analyzer_model,
            system_prompt=system_prompt,
            user_message=analyze_msg,
            output_format=AnalysisResult,
            max_tokens=ANALYZE_MAX_TOKENS,
            effort=prefs.get("pipeline.analyzer_effort", prefs_snapshot) or "low",
        )

        # Semantic upgrade gate (matches pipeline.py)
        effective_task_type = semantic_upgrade_general(analysis.task_type, raw_prompt)
        if effective_task_type != analysis.task_type:
            analysis.task_type = effective_task_type

        effective_strategy = resolve_effective_strategy(
            selected_strategy=analysis.selected_strategy,
            available=strategy_loader.list_strategies(),
            blocked_strategies=set(),
            confidence=analysis.confidence,
            strategy_override=None,
            trace_id=trace_id,
            data_recommendation=None,
        )
        strategy_instructions = strategy_loader.load(effective_strategy)
        analysis_summary = (
            f"Task type: {analysis.task_type}\n"
            f"Weaknesses: {', '.join(analysis.weaknesses)}\n"
            f"Strengths: {', '.join(analysis.strengths)}\n"
            f"Strategy: {effective_strategy}\n"
            f"Rationale: {analysis.strategy_rationale}"
        )

        # --- Phase 2: Optimize ---
        optimize_msg = prompt_loader.render("optimize.md", {
            "raw_prompt": raw_prompt,
            "analysis_summary": analysis_summary,
            "strategy_instructions": strategy_instructions,
            "codebase_guidance": workspace_guidance,
            "codebase_context": codebase_context,
            "adaptation_state": None,
            "applied_patterns": None,
            "few_shot_examples": None,
        })
        dynamic_max_tokens = compute_optimize_max_tokens(len(raw_prompt))
        optimization: OptimizationResult = await call_provider_with_retry(
            provider,
            model=optimizer_model,
            system_prompt=system_prompt,
            user_message=optimize_msg,
            output_format=OptimizationResult,
            max_tokens=dynamic_max_tokens,
            effort=prefs.get("pipeline.optimizer_effort", prefs_snapshot) or "high",
            streaming=True,
        )
        _clean_prompt, _clean_changes = sanitize_optimization_result(
            optimization.optimized_prompt, optimization.changes_summary,
        )
        optimization = OptimizationResult(
            optimized_prompt=_clean_prompt,
            changes_summary=_clean_changes,
            strategy_used=optimization.strategy_used,
        )

        # --- Phase 3: Score ---
        original_scores = None
        optimized_scores = None
        deltas = None
        scoring_mode = "skipped"
        if prefs.get("pipeline.enable_scoring", prefs_snapshot):
            import random
            original_first = random.choice([True, False])
            prompt_a = raw_prompt if original_first else optimization.optimized_prompt
            prompt_b = optimization.optimized_prompt if original_first else raw_prompt

            scoring_system = prompt_loader.load("scoring.md")
            scorer_msg = (
                f"<prompt-a>\n{prompt_a}\n</prompt-a>\n\n"
                f"<prompt-b>\n{prompt_b}\n</prompt-b>"
            )
            scores: ScoreResult = await call_provider_with_retry(
                provider,
                model=scorer_model,
                system_prompt=scoring_system,
                user_message=scorer_msg,
                output_format=ScoreResult,
                max_tokens=SCORE_MAX_TOKENS,
                effort=prefs.get("pipeline.scorer_effort", prefs_snapshot) or "low",
            )
            llm_original = scores.prompt_a_scores if original_first else scores.prompt_b_scores
            llm_optimized = scores.prompt_b_scores if original_first else scores.prompt_a_scores

            heur_original = HeuristicScorer.score_prompt(raw_prompt)
            heur_optimized = HeuristicScorer.score_prompt(
                optimization.optimized_prompt, original=raw_prompt,
            )
            blended_original = blend_scores(llm_original, heur_original, None)
            blended_optimized = blend_scores(llm_optimized, heur_optimized, None)

            original_scores = blended_original.to_dimension_scores()
            optimized_scores = blended_optimized.to_dimension_scores()
            deltas = DimensionScores.compute_deltas(original_scores, optimized_scores)
            scoring_mode = "hybrid"

        # Improvement score (matches pipeline.py weights)
        improvement_score: float | None = None
        if deltas:
            _imp = (
                deltas.get("clarity", 0) * 0.25
                + deltas.get("specificity", 0) * 0.25
                + deltas.get("structure", 0) * 0.20
                + deltas.get("faithfulness", 0) * 0.20
                + deltas.get("conciseness", 0) * 0.10
            )
            improvement_score = round(max(0.0, min(10.0, _imp)), 2)

        # --- Phase 4: Embed ---
        raw_embedding: bytes | None = None
        opt_embedding: bytes | None = None
        xfm_embedding: bytes | None = None
        try:
            raw_vec = await embedding_service.aembed_single(raw_prompt)
            raw_embedding = raw_vec.astype("float32").tobytes()
        except Exception as exc:
            logger.warning("Raw embedding failed for prompt %d: %s", prompt_index, exc)
        try:
            opt_vec = await embedding_service.aembed_single(optimization.optimized_prompt)
            opt_embedding = opt_vec.astype("float32").tobytes()
        except Exception:
            pass
        try:
            diff_text = f"{raw_prompt} → {optimization.optimized_prompt}"
            xfm_vec = await embedding_service.aembed_single(diff_text)
            xfm_embedding = xfm_vec.astype("float32").tobytes()
        except Exception:
            pass

        duration_ms = int((time.monotonic() - t0) * 1000)
        task_type = (
            analysis.task_type if analysis.task_type in VALID_TASK_TYPES else "general"
        )

        return PendingOptimization(
            id=opt_id,
            trace_id=trace_id,
            batch_id=batch_id,
            raw_prompt=raw_prompt,
            optimized_prompt=optimization.optimized_prompt,
            task_type=task_type,
            strategy_used=effective_strategy,
            changes_summary=optimization.changes_summary,
            score_clarity=optimized_scores.clarity if optimized_scores else None,
            score_specificity=optimized_scores.specificity if optimized_scores else None,
            score_structure=optimized_scores.structure if optimized_scores else None,
            score_faithfulness=optimized_scores.faithfulness if optimized_scores else None,
            score_conciseness=optimized_scores.conciseness if optimized_scores else None,
            overall_score=optimized_scores.overall if optimized_scores else None,
            improvement_score=improvement_score,
            scoring_mode=scoring_mode,
            intent_label=title_case_label(analysis.intent_label or "general"),
            domain=analysis.domain or "general",
            domain_raw=(analysis.domain or "general"),
            embedding=raw_embedding,
            optimized_embedding=opt_embedding,
            transformation_embedding=xfm_embedding,
            models_by_phase={"analyze": analyzer_model, "optimize": optimizer_model, "score": scorer_model},
            original_scores=original_scores.model_dump() if original_scores else None,
            score_deltas=deltas,
            duration_ms=duration_ms,
            status="completed",
            provider=provider.name,
            model_used=optimizer_model,
            routing_tier="internal",
            context_sources={
                "source": "batch_seed",
                "batch_id": batch_id,
                "agent": agent_name,
            },
        )

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "Batch prompt %d/%d failed: %s", prompt_index + 1, total_prompts, exc
        )
        return PendingOptimization(
            id=opt_id,
            trace_id=trace_id,
            batch_id=batch_id,
            raw_prompt=raw_prompt,
            status="failed",
            error=str(exc)[:500],
            duration_ms=duration_ms,
        )
