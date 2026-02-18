"""MCP (Model Context Protocol) server for PromptForge.

Exposes prompt optimization capabilities as MCP tools that can be used
by Claude and other MCP-compatible clients.

Tools:
  - promptforge_optimize: Run the full optimization pipeline on a prompt
  - promptforge_get: Retrieve an optimization by ID
  - promptforge_list: List optimizations with filtering, sorting, pagination
  - promptforge_get_by_project: Get all optimizations for a project
  - promptforge_search: Full-text search across prompts
  - promptforge_tag: Add/remove tags, set project on an optimization
  - promptforge_stats: Get usage statistics
  - promptforge_delete: Delete an optimization record
"""

import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from app.constants import LEGACY_STRATEGY_ALIASES, OptimizationStatus, Strategy
from app.converters import (
    optimization_to_dict,
    optimization_to_summary,
    update_optimization_status,
    with_display_scores,
)
from app.database import async_session_factory, init_db
from app.repositories.project import (
    ProjectRepository,
    ensure_project_by_name,
    ensure_prompt_in_project,
)
from app.repositories.optimization import (
    _UNSET,
    ListFilters,
    OptimizationRepository,
    Pagination,
)
from app.services.pipeline import run_pipeline
from app.utils.scores import score_to_display

# Score keys that need 0.0-1.0 → 1-10 conversion in stats responses
_STATS_SCORE_KEYS = (
    "average_overall_score",
    "average_clarity_score",
    "average_specificity_score",
    "average_structure_score",
    "average_faithfulness_score",
)

# --- Helpers ---

@asynccontextmanager
async def _repo_session():
    """Provide an OptimizationRepository bound to a fresh async session."""
    async with async_session_factory() as session:
        yield OptimizationRepository(session), session


# --- Lifespan ---

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize database on startup."""
    await init_db()
    yield {}


# --- FastMCP Server ---

mcp = FastMCP(
    name="PromptForge",
    instructions=(
        "PromptForge is an AI-powered prompt optimization engine. "
        "Use these tools to optimize prompts, manage optimization history, "
        "and retrieve usage statistics."
    ),
    lifespan=lifespan,
)


# --- Tool 1: promptforge_optimize ---

@mcp.tool(
    name="promptforge_optimize",
    description=(
        "Optimize a raw prompt using the PromptForge 4-stage pipeline "
        "(Analyze → Strategy → Optimize → Validate). Returns the optimized prompt, "
        "scores, changes made, and full analysis. Saves result to database."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
    ),
)
async def promptforge_optimize(
    prompt: str,
    project: str | None = None,
    tags: list[str] | None = None,
    title: str | None = None,
    strategy: str | None = None,
    secondary_frameworks: list[str] | None = None,
    prompt_id: str | None = None,
) -> dict[str, object]:
    """Run the full optimization pipeline on a prompt.

    Args:
        prompt: The raw prompt text to optimize.
        project: Optional project name to associate with the optimization.
        tags: Optional list of tags.
        title: Optional title for the optimization.
        strategy: Optional strategy override (e.g. 'chain-of-thought'). Skips auto-selection.
        secondary_frameworks: Optional secondary frameworks (max 2) to combine with strategy.
        prompt_id: Optional originating prompt ID from a project.
    """
    if not prompt or not prompt.strip():
        return {"error": "Prompt must not be empty or whitespace-only"}
    if len(prompt) > 100_000:
        return {"error": "Prompt must be 100,000 characters or fewer"}
    if tags:
        tags = [t[:50] for t in tags]
    valid = {s.value for s in Strategy}
    if strategy is not None:
        # Accept legacy aliases
        strategy = LEGACY_STRATEGY_ALIASES.get(strategy, strategy)
        if strategy not in valid:
            return {"error": f"Unknown strategy {strategy!r}. Valid: {', '.join(sorted(valid))}"}
    if secondary_frameworks:
        if len(secondary_frameworks) > 2:
            return {"error": "At most 2 secondary frameworks allowed"}
        resolved = []
        for fw in secondary_frameworks:
            mapped = LEGACY_STRATEGY_ALIASES.get(fw, fw)
            if mapped not in valid:
                return {"error": f"Unknown secondary framework {fw!r}. Valid: {', '.join(sorted(valid))}"}
            resolved.append(mapped)
        secondary_frameworks = resolved

    start_time = time.time()
    optimization_id = str(uuid.uuid4())

    # Create initial DB record and auto-create Project if needed
    resolved_project_id: str | None = None
    async with _repo_session() as (repo, session):
        # Validate prompt_id FK before creating record
        if prompt_id:
            proj_repo = ProjectRepository(session)
            existing_prompt = await proj_repo.get_prompt_by_id(prompt_id)
            if not existing_prompt:
                return {"error": f"prompt_id does not reference a valid prompt: {prompt_id}"}
            resolved_project_id = existing_prompt.project_id

        opt_record = await repo.create(
            id=optimization_id,
            raw_prompt=prompt,
            status=OptimizationStatus.RUNNING,
            project=project,
            tags=json.dumps(tags) if tags else None,
            title=title,
            prompt_id=prompt_id,
        )
        if project:
            pid = await ensure_project_by_name(session, project)
            if not resolved_project_id:
                resolved_project_id = pid
            # Auto-create prompt if no explicit prompt_id
            if not prompt_id and pid:
                auto_prompt_id = await ensure_prompt_in_project(session, pid, prompt)
                if auto_prompt_id:
                    opt_record.prompt_id = auto_prompt_id
        await session.commit()

    # Run pipeline
    try:
        result = await run_pipeline(
            prompt,
            strategy_override=strategy,
            secondary_frameworks_override=secondary_frameworks,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        await update_optimization_status(
            optimization_id,
            result_data=asdict(result),
            start_time=start_time,
            model_fallback=result.model_used,
        )

        result_dict = with_display_scores(asdict(result))
        result_dict["id"] = optimization_id
        result_dict["duration_ms"] = elapsed_ms
        result_dict["status"] = OptimizationStatus.COMPLETED
        if resolved_project_id:
            result_dict["project_id"] = resolved_project_id
        return result_dict
    except Exception as e:
        await update_optimization_status(optimization_id, error=str(e))
        return {"error": str(e), "id": optimization_id, "status": OptimizationStatus.ERROR}


# --- Tool 2: promptforge_get ---

@mcp.tool(
    name="promptforge_get",
    description=(
        "Retrieve a specific optimization record by its UUID. "
        "Returns the complete record with all fields including prompts, "
        "scores, analysis data, and metadata."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def promptforge_get(optimization_id: str) -> dict[str, object]:
    """Get a single optimization by ID.

    Args:
        optimization_id: The UUID of the optimization to retrieve.
    """
    async with _repo_session() as (repo, _session):
        opt = await repo.get_by_id(optimization_id)

        if not opt:
            return {"error": f"Optimization not found: {optimization_id}"}

        return with_display_scores(optimization_to_dict(opt))


# --- Tool 3: promptforge_list ---

@mcp.tool(
    name="promptforge_list",
    description=(
        "List optimization records with filtering, sorting, and pagination. "
        "Supports filtering by project name, project_id, task_type, min_score, "
        "and search text. Returns paginated results with offset-based pagination."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def promptforge_list(
    project: str | None = None,
    project_id: str | None = None,
    task_type: str | None = None,
    min_score: float | None = None,
    search: str | None = None,
    include_archived: bool = True,
    limit: int = 20,
    offset: int = 0,
    sort: str = "created_at",
    order: str = "desc",
) -> dict[str, object]:
    """List optimizations with optional filters.

    Args:
        project: Filter by project name.
        project_id: Filter by project UUID (matches via FK chain and legacy name fallback).
        task_type: Filter by task type (e.g., 'coding', 'creative').
        min_score: Filter to only include items with overall_score >= this value (1-10 scale).
        search: Full-text search across prompt text.
        include_archived: Include items from archived projects (default True).
        limit: Maximum number of items to return (default 20).
        offset: Number of items to skip for pagination (default 0).
        sort: Field to sort by ('created_at', 'overall_score', 'task_type'). Default 'created_at'.
        order: Sort order ('asc' or 'desc'). Default 'desc'.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    async with _repo_session() as (repo, _session):
        filters = ListFilters(
            project=project,
            project_id=project_id,
            task_type=task_type,
            min_score=min_score,
            search=search,
            completed_only=True,
            include_archived=include_archived,
        )
        pagination = Pagination(sort=sort, order=order, offset=offset, limit=limit)

        items, total = await repo.list(filters=filters, pagination=pagination)

        summaries = [optimization_to_summary(opt) for opt in items]
        count = len(summaries)
        has_more = (offset + count) < total
        next_offset = offset + count if has_more else None

        return {
            "items": summaries,
            "total": total,
            "count": count,
            "offset": offset,
            "has_more": has_more,
            "next_offset": next_offset,
        }


# --- Tool 4: promptforge_get_by_project ---

@mcp.tool(
    name="promptforge_get_by_project",
    description=(
        "Retrieve all optimizations for a specific project, "
        "sorted by most recent first. Returns full optimization records."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def promptforge_get_by_project(
    project: str,
    include_prompts: bool = True,
    limit: int = 50,
) -> dict[str, object]:
    """Get all optimizations for a project.

    Args:
        project: The project name to filter by.
        include_prompts: Whether to include full prompt text (default True).
        limit: Maximum number of results (default 50).
    """
    async with _repo_session() as (repo, _session):
        filters = ListFilters(project=project, completed_only=True)
        pagination = Pagination(sort="created_at", order="desc", limit=limit)

        items, _ = await repo.list(filters=filters, pagination=pagination)

        if include_prompts:
            converted = [with_display_scores(optimization_to_dict(opt)) for opt in items]
        else:
            converted = [optimization_to_summary(opt) for opt in items]

        return {
            "project": project,
            "items": converted,
            "count": len(converted),
        }


# --- Tool 5: promptforge_search ---

@mcp.tool(
    name="promptforge_search",
    description=(
        "Full-text search across both original and optimized prompt content, "
        "titles, tags, and project names. Returns matching optimization records."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def promptforge_search(
    query: str,
    include_archived: bool = True,
    limit: int = 20,
) -> dict[str, object]:
    """Search for optimizations by text.

    Args:
        query: The search query text (minimum 2 characters).
        include_archived: Include items from archived projects (default True).
        limit: Maximum number of results (default 20).
    """
    if len(query) < 2:
        return {"error": "Search query must be at least 2 characters", "items": [], "total": 0}

    async with _repo_session() as (repo, _session):
        filters = ListFilters(search=query, include_archived=include_archived)
        pagination = Pagination(sort="created_at", order="desc", limit=limit)

        items, total = await repo.list(filters=filters, pagination=pagination)

        return {
            "items": [optimization_to_summary(opt) for opt in items],
            "total": total,
            "query": query,
        }


# --- Tool 6: promptforge_tag ---

@mcp.tool(
    name="promptforge_tag",
    description=(
        "Add or remove tags from an optimization, and/or set its project name. "
        "Can add new tags, remove existing tags, and change the project "
        "association in a single call."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def promptforge_tag(
    optimization_id: str,
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
    project: str | None = None,
    title: str | None = None,
) -> dict[str, object]:
    """Update tags and metadata on an optimization.

    Args:
        optimization_id: The UUID of the optimization to update.
        add_tags: Tags to add to the optimization.
        remove_tags: Tags to remove from the optimization.
        project: Set the project name (use empty string to clear).
        title: Set the title (use empty string to clear).
    """
    if add_tags:
        add_tags = [t[:50] for t in add_tags]
    if remove_tags:
        remove_tags = [t[:50] for t in remove_tags]

    async with _repo_session() as (repo, session):
        # Block tagging to an archived project
        if project:
            proj_repo = ProjectRepository(session)
            existing = await proj_repo.get_by_name(project)
            if existing and existing.status == "archived":
                return {"error": f"Cannot assign to archived project: {project}"}

        result = await repo.update_tags(
            optimization_id,
            add_tags=add_tags,
            remove_tags=remove_tags,
            project=project if project is not None else _UNSET,
            title=title if title is not None else _UNSET,
        )

        if result is None:
            return {"error": f"Optimization not found: {optimization_id}"}

        # Auto-create Project if setting a non-empty project name
        if project:
            await ensure_project_by_name(session, project)

        await session.commit()

        # Re-fetch to resolve project_id via FK chain
        opt = await repo.get_by_id(optimization_id)
        if opt:
            result["project_id"] = getattr(opt, "_resolved_project_id", None)

        return result


# --- Tool 7: promptforge_stats ---

@mcp.tool(
    name="promptforge_stats",
    description=(
        "Get usage statistics for PromptForge, including total optimizations, "
        "average scores, task type breakdown, project counts, and time-based metrics. "
        "Can optionally scope statistics to a specific project."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def promptforge_stats(project: str | None = None) -> dict[str, object]:
    """Get usage statistics.

    Args:
        project: Optional project name to scope statistics to.
    """
    async with _repo_session() as (repo, _session):
        stats = await repo.get_stats(project=project)
        # Convert 0.0-1.0 averages to 1-10 display scale for MCP consistency
        for key in _STATS_SCORE_KEYS:
            if key in stats:
                stats[key] = score_to_display(stats[key])
        # Convert per-strategy score averages too
        if stats.get("score_by_strategy"):
            stats["score_by_strategy"] = {
                name: score_to_display(val)
                for name, val in stats["score_by_strategy"].items()
            }
        return stats


# --- Tool 8: promptforge_delete ---

@mcp.tool(
    name="promptforge_delete",
    description=(
        "Permanently delete an optimization record from the database. "
        "This action cannot be undone."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
    ),
)
async def promptforge_delete(optimization_id: str) -> dict[str, object]:
    """Delete an optimization by ID.

    Args:
        optimization_id: The UUID of the optimization to delete.
    """
    async with _repo_session() as (repo, session):
        deleted = await repo.delete_by_id(optimization_id)

        if not deleted:
            return {"error": f"Optimization not found: {optimization_id}"}

        await session.commit()
        return {"deleted": True, "id": optimization_id}


# --- Main entry point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
