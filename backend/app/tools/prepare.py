"""Handler for synthesis_prepare_optimization MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging
import uuid

from mcp.server.fastmcp import Context

from app.config import PROMPTS_DIR
from app.database import async_session_factory
from app.models import Optimization
from app.schemas.mcp_models import PrepareOutput
from app.services.passthrough import assemble_passthrough_prompt
from app.services.preferences import PreferencesService
from app.tools._shared import DATA_DIR, resolve_workspace_guidance

logger = logging.getLogger(__name__)


async def handle_prepare(
    prompt: str,
    strategy: str | None,
    max_context_tokens: int,
    workspace_path: str | None,
    repo_full_name: str | None,
    ctx: Context | None,
) -> PrepareOutput:
    """Assemble the full optimization prompt with context for an external LLM."""
    if len(prompt) < 20:
        raise ValueError(
            "Prompt too short (%d chars). Minimum is 20 characters." % len(prompt)
        )
    if max_context_tokens < 1:
        raise ValueError(
            "max_context_tokens must be a positive integer (got %d)" % max_context_tokens
        )

    # Resolve strategy: explicit param → user preference → auto
    prefs = PreferencesService(DATA_DIR)
    effective_strategy = strategy or prefs.get("defaults.strategy") or "auto"

    logger.info(
        "synthesis_prepare_optimization called: prompt_len=%d strategy=%s",
        len(prompt), effective_strategy,
    )

    # Auto-discover workspace roots (zero-config) or fall back to workspace_path
    guidance = await resolve_workspace_guidance(ctx, workspace_path)

    # Resolve adaptation state for passthrough template injection
    adaptation_state: str | None = None
    try:
        from app.services.adaptation_tracker import AdaptationTracker

        async with async_session_factory() as _adapt_db:
            tracker = AdaptationTracker(_adapt_db)
            adaptation_state = await tracker.render_adaptation_state("general")
    except Exception as exc:
        logger.debug("Adaptation state unavailable for MCP prepare: %s", exc)

    assembled, strategy_name = assemble_passthrough_prompt(
        prompts_dir=PROMPTS_DIR,
        raw_prompt=prompt,
        strategy_name=effective_strategy,
        codebase_guidance=guidance,
        adaptation_state=adaptation_state,
    )

    # Enforce max_context_tokens budget
    estimated_tokens = len(assembled) // 4
    if estimated_tokens > max_context_tokens:
        max_chars = max_context_tokens * 4
        assembled = assembled[:max_chars]
        context_size_tokens = max_context_tokens
    else:
        context_size_tokens = estimated_tokens

    trace_id = str(uuid.uuid4())

    # Store pending optimization with raw_prompt for later save_result linkage
    async with async_session_factory() as db:
        pending = Optimization(
            id=str(uuid.uuid4()),
            raw_prompt=prompt,
            status="pending",
            trace_id=trace_id,
            provider="mcp_passthrough",
            strategy_used=strategy_name,
            task_type="general",
        )
        db.add(pending)
        await db.commit()

    logger.info(
        "synthesis_prepare_optimization completed: trace_id=%s strategy=%s tokens=%d",
        trace_id, strategy_name, context_size_tokens,
    )

    return PrepareOutput(
        trace_id=trace_id,
        assembled_prompt=assembled,
        context_size_tokens=context_size_tokens,
        strategy_requested=strategy_name,
    )
