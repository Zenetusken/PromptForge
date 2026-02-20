"""MCP (Model Context Protocol) server for PromptForge.

Exposes prompt optimization capabilities as MCP tools that can be used
by Claude and other MCP-compatible clients.

Tools:
  - promptforge_optimize: Run the full optimization pipeline on a prompt
  - promptforge_retry: Re-run an existing optimization (with optional strategy override)
  - promptforge_get: Retrieve an optimization by ID
  - promptforge_list: List optimizations with filtering, sorting, pagination
  - promptforge_get_by_project: Get all optimizations for a project
  - promptforge_search: Full-text search across prompts
  - promptforge_tag: Add/remove tags, set project on an optimization
  - promptforge_stats: Get usage statistics
  - promptforge_delete: Delete an optimization record
  - promptforge_list_projects: List projects with filtering and pagination
  - promptforge_get_project: Retrieve a project by ID with its prompts
  - promptforge_strategies: List all available optimization strategies
  - promptforge_create_project: Create a new project
  - promptforge_add_prompt: Add a prompt to a project
  - promptforge_update_prompt: Update prompt content (auto-versions)
"""

import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from app.constants import LEGACY_STRATEGY_ALIASES, OptimizationStatus, ProjectStatus, Strategy
from app.converters import (
    deserialize_json_field,
    optimization_to_dict,
    optimization_to_summary,
    update_optimization_status,
    with_display_scores,
)
from app.database import async_session_factory, engine, init_db
from app.models.project import Project, Prompt
from app.providers.errors import ProviderError
from app.repositories.project import (
    ProjectFilters,
    ProjectPagination,
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
from app.services.strategy_selector import _STRATEGY_DESCRIPTIONS, _STRATEGY_REASON_MAP
from app.utils.scores import score_to_display

logger = logging.getLogger(__name__)

# Score keys that need 0.0-1.0 → 1-10 conversion in stats responses
_STATS_SCORE_KEYS = (
    "average_overall_score",
    "average_clarity_score",
    "average_specificity_score",
    "average_structure_score",
    "average_faithfulness_score",
)

# UUID v4 format regex (case-insensitive)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Version label format regex: v<number> (case-insensitive)
_VERSION_RE = re.compile(r"^v\d+$", re.IGNORECASE)


# --- Helpers ---

def _validate_uuid(value: str, field_name: str = "ID") -> None:
    """Validate that a string is a properly formatted UUID.

    Raises ToolError if the format is invalid.
    """
    if not _UUID_RE.match(value):
        raise ToolError(f"Invalid {field_name} format: expected UUID (e.g. '550e8400-e29b-41d4-a716-446655440000')")


def _validate_tags(tags: list[str]) -> None:
    """Validate that all tags are 50 characters or fewer.

    Raises ToolError if any tag exceeds the limit.
    """
    for tag in tags:
        if len(tag) > 50:
            raise ToolError(f"Tag must be 50 characters or fewer, got {len(tag)}")


@asynccontextmanager
async def _repo_session():
    """Provide an OptimizationRepository bound to a fresh async session."""
    async with async_session_factory() as session:
        yield OptimizationRepository(session), session


def _project_to_dict(project: Project) -> dict[str, object]:
    """Serialize a Project ORM object to a dict for MCP responses."""
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


def _prompt_to_dict(prompt: Prompt) -> dict[str, object]:
    """Serialize a Prompt ORM object to a dict for MCP responses."""
    return {
        "id": prompt.id,
        "content": prompt.content,
        "version": prompt.version,
        "order_index": prompt.order_index,
        "project_id": prompt.project_id,
        "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
        "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
    }


# --- Lifespan ---

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize database on startup, dispose engine on shutdown."""
    await init_db()
    try:
        yield {}
    finally:
        await engine.dispose()


# --- FastMCP Server ---

mcp = FastMCP(
    name="promptforge_mcp",
    instructions=(
        "PromptForge optimizes prompts via a 4-stage AI pipeline "
        "(Analyze → Strategy → Optimize → Validate). "
        "Scores are 1-10 integers; strategy_confidence is 0.0-1.0 probability.\n\n"
        "Common workflows:\n"
        "- Quick: promptforge_optimize(prompt='...')\n"
        "- Project-based: promptforge_create_project → promptforge_add_prompt → "
        "promptforge_optimize with prompt_id\n"
        "- Iterate: promptforge_retry with strategy override, or optimize again "
        "with different strategy\n"
        "- Browse: promptforge_list/promptforge_search, then promptforge_get for full details\n"
        "- Discover strategies: promptforge_strategies lists all 10 valid strategy names"
    ),
    lifespan=lifespan,
)


# --- Tool 1: promptforge_optimize ---

@mcp.tool(
    name="promptforge_optimize",
    description=(
        "Optimize a raw prompt using the PromptForge 4-stage pipeline "
        "(Analyze → Strategy → Optimize → Validate). Returns the optimized prompt, "
        "scores (1-10 scale), changes made, and full analysis. Saves result to database. "
        "Note: strategy_confidence is a 0.0-1.0 probability, not a 1-10 score."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def promptforge_optimize(
    prompt: Annotated[str, Field(description="The raw prompt text to optimize (1-100,000 chars)")],
    ctx: Context,
    project: Annotated[str | None, Field(description="Project name to associate (max 100 chars). Auto-creates if new.")] = None,
    tags: Annotated[list[str] | None, Field(description="Tags to attach (each max 50 chars)")] = None,
    title: Annotated[str | None, Field(description="Title for the optimization (max 200 chars)")] = None,
    strategy: Annotated[str | None, Field(description="Strategy override — skips auto-selection. Use promptforge_strategies to see valid values.")] = None,
    secondary_frameworks: Annotated[list[str] | None, Field(description="Secondary frameworks (max 2) to combine with strategy. Use promptforge_strategies for valid values.")] = None,
    prompt_id: Annotated[str | None, Field(description="UUID of an existing project prompt to link this optimization to")] = None,
    version: Annotated[str | None, Field(description="Version label in 'v<number>' format (e.g. 'v1', 'v2')")] = None,
) -> dict[str, object]:
    """Run the full optimization pipeline on a prompt.

    Returns a dict with: id, status, optimized_prompt, scores (1-10),
    strategy_confidence (0.0-1.0), and more.
    """
    if not prompt or not prompt.strip():
        raise ToolError("Prompt must not be empty or whitespace-only")
    if len(prompt) > 100_000:
        raise ToolError("Prompt must be 100,000 characters or fewer")
    if tags:
        _validate_tags(tags)
    if project is not None and len(project) > 100:
        raise ToolError("Project name must be 100 characters or fewer")
    if title is not None and len(title) > 200:
        raise ToolError("Title must be 200 characters or fewer")
    if version is not None and version.strip():
        if not _VERSION_RE.match(version.strip()):
            raise ToolError("Version must be in 'v<number>' format (e.g. 'v1', 'v2')")
    if prompt_id:
        _validate_uuid(prompt_id, "prompt_id")
    valid = {s.value for s in Strategy}
    if strategy is not None:
        # Accept legacy aliases
        strategy = LEGACY_STRATEGY_ALIASES.get(strategy, strategy)
        if strategy not in valid:
            raise ToolError(f"Unknown strategy {strategy!r}. Valid: {', '.join(sorted(valid))}")
    if secondary_frameworks:
        if len(secondary_frameworks) > 2:
            raise ToolError("At most 2 secondary frameworks allowed")
        resolved = []
        for fw in secondary_frameworks:
            mapped = LEGACY_STRATEGY_ALIASES.get(fw, fw)
            if mapped not in valid:
                raise ToolError(f"Unknown secondary framework {fw!r}. Valid: {', '.join(sorted(valid))}")
            resolved.append(mapped)
        secondary_frameworks = resolved

    start_time = time.time()
    optimization_id = str(uuid.uuid4())

    await ctx.report_progress(0.0, 1.0, "Creating optimization record")

    # Create initial DB record and auto-create Project if needed
    resolved_project_id: str | None = None
    async with _repo_session() as (repo, session):
        # Validate prompt_id FK before creating record
        if prompt_id:
            proj_repo = ProjectRepository(session)
            existing_prompt = await proj_repo.get_prompt_by_id(prompt_id)
            if not existing_prompt:
                raise ToolError(f"prompt_id does not reference a valid prompt: {prompt_id}")
            resolved_project_id = existing_prompt.project_id

        opt_record = await repo.create(
            id=optimization_id,
            raw_prompt=prompt,
            status=OptimizationStatus.RUNNING,
            project=project,
            tags=json.dumps(tags) if tags else None,
            title=title,
            prompt_id=prompt_id,
            version=version,
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

    await ctx.report_progress(0.1, 1.0, "Running optimization pipeline")

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

        await ctx.report_progress(1.0, 1.0, "Optimization complete")

        result_dict = with_display_scores(asdict(result))
        result_dict["id"] = optimization_id
        result_dict["duration_ms"] = elapsed_ms
        result_dict["status"] = OptimizationStatus.COMPLETED
        if resolved_project_id:
            result_dict["project_id"] = resolved_project_id
        return result_dict
    except ProviderError as e:
        await update_optimization_status(optimization_id, error=str(e))
        raise ToolError(str(e))
    except Exception as e:
        logger.exception("Pipeline error for optimization %s", optimization_id)
        await update_optimization_status(optimization_id, error=str(e))
        raise ToolError("Optimization pipeline failed. Check server logs for details.")


# --- Tool 2: promptforge_retry ---

@mcp.tool(
    name="promptforge_retry",
    description=(
        "Re-run an existing optimization with its original parameters. "
        "Optionally override the strategy or secondary_frameworks to try "
        "a different approach (e.g. 'retry with chain-of-thought'). "
        "Returns a new optimization record."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def promptforge_retry(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to retry")],
    ctx: Context,
    strategy: Annotated[str | None, Field(description="Override strategy for the retry. Use promptforge_strategies for valid values.")] = None,
    secondary_frameworks: Annotated[list[str] | None, Field(description="Override secondary frameworks (max 2). Use promptforge_strategies for valid values.")] = None,
) -> dict[str, object]:
    """Re-run an optimization, optionally with a different strategy.

    Returns the same shape as promptforge_optimize output.
    """
    _validate_uuid(optimization_id, "optimization_id")

    async with _repo_session() as (repo, _session):
        opt = await repo.get_by_id(optimization_id)
        if not opt:
            raise ToolError(f"Optimization not found: {optimization_id}")

        raw_prompt = opt.raw_prompt
        orig_project = opt.project
        orig_title = opt.title
        orig_strategy = opt.strategy
        orig_prompt_id = opt.prompt_id
        orig_version = opt.version
        orig_tags = deserialize_json_field(opt.tags)
        orig_secondary = deserialize_json_field(opt.secondary_frameworks)

    return await promptforge_optimize(
        prompt=raw_prompt,
        ctx=ctx,
        project=orig_project,
        tags=orig_tags,
        title=orig_title,
        strategy=strategy if strategy is not None else orig_strategy,
        secondary_frameworks=secondary_frameworks if secondary_frameworks is not None else orig_secondary,
        prompt_id=orig_prompt_id,
        version=orig_version,
    )


# --- Tool 3: promptforge_get ---

@mcp.tool(
    name="promptforge_get",
    description=(
        "Retrieve a specific optimization record by its UUID. "
        "Returns the complete record with all fields including prompts, "
        "scores (1-10 scale), analysis data, and metadata. "
        "Note: strategy_confidence is a 0.0-1.0 probability, not a 1-10 score."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_get(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to retrieve")],
) -> dict[str, object]:
    """Get a single optimization by ID.

    Returns the complete record with all fields including prompts,
    scores (1-10), analysis data, and metadata.
    """
    _validate_uuid(optimization_id, "optimization_id")

    async with _repo_session() as (repo, _session):
        opt = await repo.get_by_id(optimization_id)

        if not opt:
            raise ToolError(f"Optimization not found: {optimization_id}")

        return with_display_scores(optimization_to_dict(opt))


# --- Tool 4: promptforge_list ---

@mcp.tool(
    name="promptforge_list",
    description=(
        "List optimization records with filtering, sorting, and pagination. "
        "Supports filtering by project name, project_id, task_type, min_score (1-10), "
        "and search text. Returns paginated summaries with offset-based pagination."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_list(
    project: Annotated[str | None, Field(description="Filter by project name")] = None,
    project_id: Annotated[str | None, Field(description="Filter by project UUID")] = None,
    task_type: Annotated[str | None, Field(description="Filter by task type (e.g. 'coding', 'creative', 'reasoning')")] = None,
    min_score: Annotated[float | None, Field(description="Minimum overall score filter (1-10 scale)")] = None,
    search: Annotated[str | None, Field(description="Full-text search across prompt text")] = None,
    include_archived: Annotated[bool, Field(description="Include items from archived projects")] = True,
    limit: Annotated[int, Field(description="Max items to return (1-100)")] = 20,
    offset: Annotated[int, Field(description="Items to skip for pagination")] = 0,
    sort: Annotated[str, Field(description="Sort field: 'created_at', 'overall_score', 'task_type'")] = "created_at",
    order: Annotated[str, Field(description="Sort order: 'asc' or 'desc'")] = "desc",
) -> dict[str, object]:
    """List optimizations with optional filters, sorting, and pagination.

    Returns paginated summaries with total count and has_more flag.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    if min_score is not None:
        min_score = max(1.0, min(10.0, min_score))

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


# --- Tool 5: promptforge_get_by_project ---

@mcp.tool(
    name="promptforge_get_by_project",
    description=(
        "Retrieve optimizations for a specific project by name, "
        "sorted by most recent first. Supports pagination."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_get_by_project(
    project: Annotated[str, Field(description="Project name to retrieve optimizations for")],
    include_prompts: Annotated[bool, Field(description="Include full prompt text in results")] = True,
    limit: Annotated[int, Field(description="Max items to return (1-100)")] = 50,
    offset: Annotated[int, Field(description="Items to skip for pagination")] = 0,
) -> dict[str, object]:
    """Get optimizations for a project, sorted by most recent first.

    Returns full dicts when include_prompts=True, summaries otherwise.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    async with _repo_session() as (repo, _session):
        filters = ListFilters(project=project, completed_only=True)
        pagination = Pagination(sort="created_at", order="desc", limit=limit, offset=offset)

        items, total = await repo.list(filters=filters, pagination=pagination)

        if include_prompts:
            converted = [with_display_scores(optimization_to_dict(opt)) for opt in items]
        else:
            converted = [optimization_to_summary(opt) for opt in items]

        count = len(converted)
        has_more = (offset + count) < total
        next_offset = offset + count if has_more else None

        return {
            "project": project,
            "items": converted,
            "count": count,
            "total": total,
            "has_more": has_more,
            "next_offset": next_offset,
            "offset": offset,
        }


# --- Tool 6: promptforge_search ---

@mcp.tool(
    name="promptforge_search",
    description=(
        "Full-text search across both original and optimized prompt content, "
        "titles, tags, and project names. Returns matching optimization summaries "
        "with pagination support."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_search(
    query: Annotated[str, Field(description="Search text (min 2 chars). Matches prompts, titles, tags, projects.")],
    include_archived: Annotated[bool, Field(description="Include items from archived projects")] = True,
    limit: Annotated[int, Field(description="Max items to return (1-100)")] = 20,
    offset: Annotated[int, Field(description="Items to skip for pagination")] = 0,
) -> dict[str, object]:
    """Full-text search across original and optimized prompt content.

    Returns matching optimization summaries with pagination.
    """
    if len(query) < 2:
        raise ToolError("Search query must be at least 2 characters")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    async with _repo_session() as (repo, _session):
        filters = ListFilters(search=query, include_archived=include_archived)
        pagination = Pagination(sort="created_at", order="desc", limit=limit, offset=offset)

        items, total = await repo.list(filters=filters, pagination=pagination)

        summaries = [optimization_to_summary(opt) for opt in items]
        count = len(summaries)
        has_more = (offset + count) < total
        next_offset = offset + count if has_more else None

        return {
            "items": summaries,
            "total": total,
            "query": query,
            "count": count,
            "offset": offset,
            "has_more": has_more,
            "next_offset": next_offset,
        }


# --- Tool 7: promptforge_tag ---

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
        openWorldHint=False,
    ),
)
async def promptforge_tag(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to update")],
    add_tags: Annotated[list[str] | None, Field(description="Tags to add (each max 50 chars)")] = None,
    remove_tags: Annotated[list[str] | None, Field(description="Tags to remove")] = None,
    project: Annotated[str | None, Field(description="Set project name (max 100 chars; empty string to clear)")] = None,
    title: Annotated[str | None, Field(description="Set title (max 200 chars; empty string to clear)")] = None,
) -> dict[str, object]:
    """Add/remove tags, and/or set project and title on an optimization.

    Returns updated tags, project, title, and project_id.
    """
    _validate_uuid(optimization_id, "optimization_id")

    if add_tags:
        _validate_tags(add_tags)
    if remove_tags:
        _validate_tags(remove_tags)
    if project is not None and len(project) > 100:
        raise ToolError("Project name must be 100 characters or fewer")
    if title is not None and len(title) > 200:
        raise ToolError("Title must be 200 characters or fewer")

    async with _repo_session() as (repo, session):
        # Block tagging to an archived project
        if project:
            proj_repo = ProjectRepository(session)
            existing = await proj_repo.get_by_name(project)
            if existing and existing.status == ProjectStatus.ARCHIVED:
                raise ToolError(f"Cannot assign to archived project: {project}")

        result = await repo.update_tags(
            optimization_id,
            add_tags=add_tags,
            remove_tags=remove_tags,
            project=project if project is not None else _UNSET,
            title=title if title is not None else _UNSET,
        )

        if result is None:
            raise ToolError(f"Optimization not found: {optimization_id}")

        # Auto-create Project and resolve project_id directly
        if project:
            project_id = await ensure_project_by_name(session, project)
            result["project_id"] = project_id

        await session.commit()
        return result


# --- Tool 8: promptforge_stats ---

@mcp.tool(
    name="promptforge_stats",
    description=(
        "Get usage statistics for PromptForge, including total optimizations, "
        "average scores (1-10 scale), task type breakdown, project counts, "
        "and time-based metrics. Can optionally scope statistics to a specific project."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_stats(
    project: Annotated[str | None, Field(description="Scope statistics to a specific project name")] = None,
) -> dict[str, object]:
    """Get usage statistics including totals, averages, and distributions.

    Returns scores on 1-10 scale, improvement rate, strategy distribution, etc.
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


# --- Tool 9: promptforge_delete ---

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
        openWorldHint=False,
    ),
)
async def promptforge_delete(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to permanently delete")],
) -> dict[str, object]:
    """Permanently delete an optimization record. Cannot be undone."""
    _validate_uuid(optimization_id, "optimization_id")

    async with _repo_session() as (repo, session):
        deleted = await repo.delete_by_id(optimization_id)

        if not deleted:
            raise ToolError(f"Optimization not found: {optimization_id}")

        await session.commit()
        return {"deleted": True, "id": optimization_id}


# --- Tool 10: promptforge_list_projects ---

@mcp.tool(
    name="promptforge_list_projects",
    description=(
        "List projects with optional filtering and pagination. "
        "Returns project records with prompt counts. "
        "By default excludes deleted projects."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_list_projects(
    status: Annotated[str | None, Field(description="Filter by status: 'active' or 'archived'. Omit for all non-deleted.")] = None,
    search: Annotated[str | None, Field(description="Search by project name or description")] = None,
    limit: Annotated[int, Field(description="Max items to return (1-100)")] = 20,
    offset: Annotated[int, Field(description="Items to skip for pagination")] = 0,
    sort: Annotated[str, Field(description="Sort field: 'created_at', 'updated_at', 'name'")] = "created_at",
    order: Annotated[str, Field(description="Sort order: 'asc' or 'desc'")] = "desc",
) -> dict[str, object]:
    """List projects with filtering and pagination. Excludes deleted by default.

    Returns project records with prompt_count.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        filters = ProjectFilters(status=status, search=search)
        pagination = ProjectPagination(
            sort=sort, order=order, offset=offset, limit=limit,
        )

        projects, total = await proj_repo.list(filters=filters, pagination=pagination)

        # Batch-fetch prompt counts
        project_ids = [p.id for p in projects]
        prompt_counts = await proj_repo.get_prompt_counts(project_ids) if project_ids else {}

        items = []
        for p in projects:
            d = _project_to_dict(p)
            d["prompt_count"] = prompt_counts.get(p.id, 0)
            items.append(d)

        count = len(items)
        has_more = (offset + count) < total
        next_offset = offset + count if has_more else None

        return {
            "items": items,
            "total": total,
            "count": count,
            "offset": offset,
            "has_more": has_more,
            "next_offset": next_offset,
        }


# --- Tool 11: promptforge_get_project ---

@mcp.tool(
    name="promptforge_get_project",
    description=(
        "Retrieve a single project by its UUID, including its prompts. "
        "Returns the project record with all associated prompt entries."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_get_project(
    project_id: Annotated[str, Field(description="UUID of the project to retrieve")],
) -> dict[str, object]:
    """Get a project by ID, including all its prompts.

    Returns the project record with prompts list (id, content, version, order_index).
    """
    _validate_uuid(project_id, "project_id")

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        project = await proj_repo.get_by_id(project_id, load_prompts=True)

        if not project:
            raise ToolError(f"Project not found: {project_id}")

        result = _project_to_dict(project)
        result["prompts"] = [_prompt_to_dict(p) for p in (project.prompts or [])]
        return result


# --- Tool 12: promptforge_strategies ---

@mcp.tool(
    name="promptforge_strategies",
    description=(
        "List all available optimization strategies with descriptions. "
        "Use this to discover valid strategy names before calling "
        "promptforge_optimize or promptforge_retry with a strategy override."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def promptforge_strategies() -> dict[str, object]:
    """List all 10 optimization strategies with descriptions and reasoning.

    Returns strategies list, count, and legacy alias mappings.
    """
    strategies = []
    for s in Strategy:
        strategies.append({
            "name": s.value,
            "description": _STRATEGY_DESCRIPTIONS.get(s, ""),
            "reasoning": _STRATEGY_REASON_MAP.get(s, ""),
        })

    return {
        "strategies": strategies,
        "count": len(strategies),
        "legacy_aliases": LEGACY_STRATEGY_ALIASES,
    }


# --- Tool 13: promptforge_create_project ---

@mcp.tool(
    name="promptforge_create_project",
    description=(
        "Create a new project. Projects group related prompts and optimizations. "
        "If a soft-deleted project with the same name exists, it is reactivated."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def promptforge_create_project(
    name: Annotated[str, Field(description="Unique project name (1-100 chars)")],
    description: Annotated[str | None, Field(description="Project description (max 2000 chars)")] = None,
) -> dict[str, object]:
    """Create a new project or reactivate a soft-deleted one with the same name.

    Returns the project record with id, name, description, status, timestamps.
    """
    if not name or not name.strip():
        raise ToolError("Project name must not be empty")
    name = name.strip()
    if len(name) > 100:
        raise ToolError("Project name must be 100 characters or fewer")
    if description is not None and len(description) > 2000:
        raise ToolError("Description must be 2000 characters or fewer")

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        existing = await proj_repo.get_by_name(name)

        if existing:
            if existing.status == ProjectStatus.DELETED:
                # Reactivate soft-deleted project
                existing.status = ProjectStatus.ACTIVE
                if description is not None:
                    existing.description = description
                existing.updated_at = datetime.now(timezone.utc)
                await session.flush()
                await session.commit()
                return _project_to_dict(existing)
            raise ToolError(f"Project already exists: {name!r}")

        project = await proj_repo.create(name=name, description=description)
        await session.commit()
        return _project_to_dict(project)


# --- Tool 14: promptforge_add_prompt ---

@mcp.tool(
    name="promptforge_add_prompt",
    description=(
        "Add a prompt to an existing project. The prompt is appended "
        "at the next available order index."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def promptforge_add_prompt(
    project_id: Annotated[str, Field(description="UUID of the project to add the prompt to")],
    content: Annotated[str, Field(description="Prompt content (1-100,000 chars)")],
) -> dict[str, object]:
    """Add a new prompt to a project.

    Returns the prompt record with id, content, version, order_index, timestamps.
    """
    _validate_uuid(project_id, "project_id")
    if not content or not content.strip():
        raise ToolError("Prompt content must not be empty")
    if len(content) > 100_000:
        raise ToolError("Prompt content must be 100,000 characters or fewer")

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        project = await proj_repo.get_by_id(project_id, load_prompts=False)

        if not project or project.status == ProjectStatus.DELETED:
            raise ToolError(f"Project not found: {project_id}")
        if project.status == ProjectStatus.ARCHIVED:
            raise ToolError(f"Cannot add prompts to archived project: {project.name}")

        prompt = await proj_repo.add_prompt(project, content)
        await session.commit()
        return _prompt_to_dict(prompt)


# --- Tool 15: promptforge_update_prompt ---

@mcp.tool(
    name="promptforge_update_prompt",
    description=(
        "Update the content of an existing prompt. Automatically creates "
        "a version snapshot of the previous content before overwriting."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def promptforge_update_prompt(
    prompt_id: Annotated[str, Field(description="UUID of the prompt to update")],
    content: Annotated[str, Field(description="New prompt content (1-100,000 chars)")],
    optimization_id: Annotated[str | None, Field(description="UUID of the optimization that inspired this update (for version tracking)")] = None,
) -> dict[str, object]:
    """Update prompt content with automatic versioning.

    The previous content is snapshotted before overwriting.
    Returns the updated prompt record.
    """
    _validate_uuid(prompt_id, "prompt_id")
    if not content or not content.strip():
        raise ToolError("Prompt content must not be empty")
    if len(content) > 100_000:
        raise ToolError("Prompt content must be 100,000 characters or fewer")
    if optimization_id is not None:
        _validate_uuid(optimization_id, "optimization_id")

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        prompt = await proj_repo.get_prompt_by_id(prompt_id)

        if not prompt:
            raise ToolError(f"Prompt not found: {prompt_id}")

        # Check parent project status
        project = await proj_repo.get_by_id(prompt.project_id, load_prompts=False)
        if project and project.status == ProjectStatus.DELETED:
            raise ToolError(f"Prompt not found: {prompt_id}")
        if project and project.status == ProjectStatus.ARCHIVED:
            raise ToolError(f"Cannot update prompts in archived project: {project.name}")

        prompt = await proj_repo.update_prompt(
            prompt, content=content, optimization_id=optimization_id,
        )
        await session.commit()
        return _prompt_to_dict(prompt)


# --- Main entry point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
