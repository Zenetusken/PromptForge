"""MCP (Model Context Protocol) server for PromptForge.

Exposes prompt optimization capabilities as MCP tools that can be used
by Claude and other MCP-compatible clients.

Tools:
  - optimize: Run the full optimization pipeline on a prompt
  - retry: Re-run an existing optimization (with optional strategy override)
  - get: Retrieve an optimization by ID
  - list: List optimizations with filtering, sorting, pagination
  - get_by_project: Get all optimizations for a project
  - search: Full-text search across prompts
  - tag: Add/remove tags, set project on an optimization
  - stats: Get usage statistics
  - delete: Delete an optimization record
  - bulk_delete: Delete multiple optimization records by ID
  - list_projects: List projects with filtering and pagination
  - get_project: Retrieve a project by ID with its prompts
  - strategies: List all available optimization strategies
  - create_project: Create a new project
  - add_prompt: Add a prompt to a project
  - update_prompt: Update prompt content (auto-versions)
  - set_project_context: Set or clear codebase context profile on a project
  - batch: Optimize multiple prompts in one call
  - cancel: Cancel a running optimization
  - sync_workspace: Sync workspace context from Claude Code or external tools
"""

import contextvars
import functools
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated, Any, Callable

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from apps.promptforge.constants import LEGACY_STRATEGY_ALIASES, OptimizationStatus, ProjectStatus, Strategy
from apps.promptforge.converters import (
    _SCORE_FIELDS,
    compute_score_deltas,
    deserialize_json_field,
    extract_raw_scores,
    optimization_to_dict,
    optimization_to_summary,
    update_optimization_status,
    with_display_and_raw_scores,
)
from app.database import async_session_factory, engine, init_db
from apps.promptforge.models.optimization import Optimization
from apps.promptforge.models.project import Project, Prompt
from app.providers.errors import ProviderError
from apps.promptforge.repositories.optimization import (
    _UNSET,
    ListFilters,
    OptimizationRepository,
    Pagination,
)
from apps.promptforge.repositories.project import (
    ProjectFilters,
    ProjectPagination,
    ProjectRepository,
    ensure_project_by_name,
    ensure_prompt_in_project,
)
from apps.promptforge.schemas.context import (
    codebase_context_from_dict,
    context_to_dict,
    merge_contexts,
)
from apps.promptforge.services.mcp_activity import MCPEventType
from apps.promptforge.services.pipeline import run_pipeline
from apps.promptforge.services.stats_cache import get_stats_cached, invalidate_stats_cache
from apps.promptforge.services.strategy_selector import _STRATEGY_DESCRIPTIONS, _STRATEGY_REASON_MAP
from apps.promptforge.utils.scores import score_to_display

logger = logging.getLogger(__name__)

# --- MCP Activity Tracking ---
# Emits events to the backend's /internal/mcp-event webhook so external tool calls
# appear live in the PromptForge frontend (Network Monitor, Task Manager, notifications).

_webhook_client: httpx.AsyncClient | None = None


def _get_webhook_client() -> httpx.AsyncClient:
    """Lazy-init a shared HTTP client for webhook emission."""
    global _webhook_client
    if _webhook_client is None:
        _webhook_client = httpx.AsyncClient(timeout=2.0)
    return _webhook_client


async def _emit_mcp_event(
    event_type: MCPEventType | str,
    tool_name: str | None = None,
    call_id: str | None = None,
    **kwargs: Any,
) -> None:
    """Fire-and-forget POST to backend webhook. Never raises."""
    try:
        client = _get_webhook_client()
        payload = {
            "event_type": event_type,
            "tool_name": tool_name,
            "call_id": call_id,
            **{k: v for k, v in kwargs.items() if v is not None},
        }
        from app import config as _cfg
        headers = {}
        if _cfg.INTERNAL_WEBHOOK_SECRET:
            headers["X-Webhook-Secret"] = _cfg.INTERNAL_WEBHOOK_SECRET
        await client.post(
            f"http://{_cfg.BACKEND_HOST}:{_cfg.PORT}/api/apps/promptforge/internal/mcp-event",
            json=payload,
            headers=headers,
        )
    except Exception:
        # MCP tools must never fail because the activity feed is down
        pass


_current_call_id: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "_current_call_id", default=None,
)


async def _emit_tool_progress(progress: float, message: str | None = None) -> None:
    """Emit a tool_progress event for the current tracked tool call.

    Only works inside a @_mcp_tracked handler. No-op otherwise.
    """
    ctx = _current_call_id.get()
    if ctx:
        tool_name, call_id = ctx
        await _emit_mcp_event(
            MCPEventType.tool_progress, tool_name, call_id,
            progress=progress, message=message,
        )


def _extract_result_summary(result: Any) -> dict | None:
    """Extract key fields from a tool's return value for the activity feed."""
    if not isinstance(result, dict):
        return None
    summary: dict[str, Any] = {}
    for key in ("id", "status", "overall_score", "total", "completed", "failed"):
        if key in result:
            summary[key] = result[key]
    return summary if summary else None


def _mcp_tracked(tool_name: str) -> Callable:
    """Decorator that wraps MCP tool handlers with activity event emission.

    Sits between @mcp.tool() and the async def handler.
    Emits tool_start before execution, tool_complete/tool_error after.

    When a tracked handler calls another tracked handler (e.g. retry → optimize),
    the inner decorator is skipped so only the outer tool appears in the activity
    feed.  The ContextVar retains the outer call_id, so _emit_tool_progress()
    calls inside the inner handler still attribute to the correct outer tool.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # If already inside a tracked call, skip tracking for this nested call
            if _current_call_id.get() is not None:
                return await func(*args, **kwargs)

            call_id = str(uuid.uuid4())
            token = _current_call_id.set((tool_name, call_id))
            await _emit_mcp_event(MCPEventType.tool_start, tool_name, call_id)
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                await _emit_mcp_event(
                    MCPEventType.tool_complete,
                    tool_name,
                    call_id,
                    duration_ms=duration_ms,
                    result_summary=_extract_result_summary(result),
                )
                return result
            except Exception as exc:
                duration_ms = int((time.time() - start) * 1000)
                await _emit_mcp_event(
                    MCPEventType.tool_error,
                    tool_name,
                    call_id,
                    duration_ms=duration_ms,
                    error=str(exc)[:200],
                )
                raise
            finally:
                _current_call_id.reset(token)
        return wrapper
    return decorator


# Score keys that need 0.0-1.0 → 1-10 conversion in stats responses
_STATS_SCORE_KEYS = (
    "average_overall_score",
    "average_clarity_score",
    "average_specificity_score",
    "average_structure_score",
    "average_faithfulness_score",
    "average_conciseness_score",
    "average_framework_adherence_score",
)

# All dict key names whose float values represent 0.0-1.0 scores
_SCORE_KEY_NAMES = frozenset({
    "avg_score", "min", "max", "avg",
    *_STATS_SCORE_KEYS,
})


def _convert_scores_recursive(obj: object) -> object:
    """Recursively walk a dict/list structure and convert known score fields to 1-10.

    Converts float values in dict entries whose key is in _SCORE_KEY_NAMES.
    Also converts top-level score_by_strategy values (flat str→float dicts).
    """
    if isinstance(obj, dict):
        return {
            k: (
                score_to_display(v) if k in _SCORE_KEY_NAMES and isinstance(v, (int, float))
                else _convert_scores_recursive(v)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_convert_scores_recursive(item) for item in obj]
    return obj

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
        raise ToolError(
            f"Invalid {field_name} format: expected UUID"
            " (e.g. '550e8400-e29b-41d4-a716-446655440000')"
        )


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


def _project_to_dict(project: Project, *, include_context: bool = False) -> dict[str, object]:
    """Serialize a Project ORM object to a dict for MCP responses."""
    d: dict[str, object] = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "parent_id": project.parent_id,
        "depth": project.depth,
        "has_context": bool(project.context_profile),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }
    if include_context and project.context_profile:
        try:
            d["context_profile"] = json.loads(project.context_profile)
        except (json.JSONDecodeError, TypeError):
            d["context_profile"] = None
    return d


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
    """Initialize database on startup, register app MCP tools, dispose engine on shutdown."""
    from kernel.registry.app_registry import get_app_registry

    registry = get_app_registry()
    if not registry.list_all():
        registry.discover()

    await init_db(app_registry=registry)

    # Register MCP tools from installed apps
    app_tools = registry.collect_mcp_tools()
    for tool_fn in app_tools:
        try:
            server.tool()(tool_fn)
        except Exception as exc:
            logger.warning("Failed to register app MCP tool %s: %s", getattr(tool_fn, "__name__", "?"), exc)
    if app_tools:
        logger.info("Registered %d app MCP tool(s)", len(app_tools))

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
        "- Quick: optimize(prompt='...')\n"
        "- Project-based: create_project → add_prompt → "
        "optimize with prompt_id\n"
        "- Iterate: retry with strategy override, or optimize again "
        "with different strategy\n"
        "- Browse: list/search, then get for full details\n"
        "- Discover strategies: strategies lists all 10 valid strategy names\n"
        "- Context-aware: set_project_context → optimize "
        "(auto-resolves context from project)\n"
        "- Filesystem: get_children to browse folders, move to reorganize, "
        "create_project with parent_id for subfolders (max depth 8)"
    ),
    lifespan=lifespan,
)


# --- Tool 1: optimize ---

@mcp.tool(
    name="optimize",
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
@_mcp_tracked("optimize")
async def promptforge_optimize(
    prompt: Annotated[str, Field(description="The raw prompt text to optimize (1-100,000 chars)")],
    ctx: Context,
    project: Annotated[str | None, Field(description="Project name to associate (max 100 chars). Auto-creates if new.")] = None,  # noqa: E501
    tags: Annotated[list[str] | None, Field(description="Tags to attach (each max 50 chars)")] = None,  # noqa: E501
    title: Annotated[str | None, Field(description="Title for the optimization (max 200 chars)")] = None,  # noqa: E501
    strategy: Annotated[str | None, Field(description="Strategy override — skips auto-selection. Use the strategies tool to see valid values.")] = None,  # noqa: E501
    secondary_frameworks: Annotated[list[str] | None, Field(description="Secondary frameworks (max 2) to combine with strategy. Use the strategies tool for valid values.")] = None,  # noqa: E501
    prompt_id: Annotated[str | None, Field(description="UUID of an existing project prompt to link this optimization to")] = None,  # noqa: E501
    version: Annotated[str | None, Field(description="Version label in 'v<number>' format (e.g. 'v1', 'v2')")] = None,  # noqa: E501
    codebase_context: Annotated[dict | None, Field(description="Optional codebase context dict with keys: language, framework, description, conventions, patterns, code_snippets, documentation, test_framework, test_patterns. Grounds the optimization in a real project.")] = None,  # noqa: E501
    max_iterations: Annotated[int | None, Field(description="Max refinement iterations (1-5). Pipeline loops optimize+validate until score_threshold met.")] = None,  # noqa: E501
    score_threshold: Annotated[float | None, Field(description="Target overall score (0.0-1.0). Pipeline iterates until reached.")] = None,  # noqa: E501
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
                raise ToolError(
                    f"Unknown secondary framework {fw!r}."
                    f" Valid: {', '.join(sorted(valid))}"
                )
            resolved.append(mapped)
        secondary_frameworks = resolved
    if max_iterations is not None and not (1 <= max_iterations <= 5):
        raise ToolError("max_iterations must be between 1 and 5")
    if score_threshold is not None and not (0.1 <= score_threshold <= 1.0):
        raise ToolError("score_threshold must be between 0.1 and 1.0")

    start_time = time.time()
    optimization_id = str(uuid.uuid4())

    await ctx.report_progress(0.0, 1.0, "Creating optimization record")
    await _emit_tool_progress(0.0, "Creating optimization record")

    # Create initial DB record, auto-create Project, and resolve context — all in one session
    resolved_project_id: str | None = None
    resolved_context = None
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
            project_info = await ensure_project_by_name(session, project)
            if project_info and not resolved_project_id:
                resolved_project_id = project_info.id
            # Auto-create prompt if no explicit prompt_id
            # Skip linking to archived projects — user intended them to be frozen
            if not prompt_id and project_info and project_info.status != "archived":
                auto_prompt_id = await ensure_prompt_in_project(session, project_info.id, prompt)
                if auto_prompt_id:
                    opt_record.prompt_id = auto_prompt_id

        # Context resolution: workspace auto-context → manual profile → explicit request
        from apps.promptforge.repositories.workspace import WorkspaceRepository
        explicit_context = codebase_context_from_dict(codebase_context)
        workspace_context = None
        project_context = None
        if project:
            ws_repo = WorkspaceRepository(session)
            workspace_context = await ws_repo.get_workspace_context_by_project_name(project)
            project_context = await ProjectRepository(session).get_context_by_name(project)
        base_context = merge_contexts(workspace_context, project_context)  # manual wins
        resolved_context = merge_contexts(base_context, explicit_context)  # per-request wins

        # Snapshot on optimization record
        if resolved_context:
            ctx_dict = context_to_dict(resolved_context)
            if ctx_dict:
                opt_record.codebase_context_snapshot = json.dumps(ctx_dict)

        await session.commit()

    await ctx.report_progress(0.1, 1.0, "Running optimization pipeline")
    await _emit_tool_progress(0.1, "Running optimization pipeline")

    # Run pipeline
    try:
        result = await run_pipeline(
            prompt,
            strategy_override=strategy,
            secondary_frameworks_override=secondary_frameworks,
            codebase_context=resolved_context,
            max_iterations=max_iterations,
            score_threshold=score_threshold,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        await update_optimization_status(
            optimization_id,
            result_data=asdict(result),
            start_time=start_time,
            model_fallback=result.model_used,
        )
        invalidate_stats_cache()

        await ctx.report_progress(1.0, 1.0, "Optimization complete")
        await _emit_tool_progress(1.0, "Optimization complete")

        result_dict = with_display_and_raw_scores(asdict(result))
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


# --- Tool 2: retry ---

@mcp.tool(
    name="retry",
    description=(
        "Re-run an existing optimization with its original parameters. "
        "Optionally override the strategy or secondary_frameworks to try "
        "a different approach (e.g. 'retry with chain-of-thought'). "
        "Context is re-resolved from the project's workspace + manual layers; "
        "pass codebase_context to override with explicit layer-3 context. "
        "Returns a new optimization record."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
@_mcp_tracked("retry")
async def promptforge_retry(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to retry")],
    ctx: Context,
    strategy: Annotated[str | None, Field(description="Override strategy for the retry. Use the strategies tool for valid values.")] = None,  # noqa: E501
    secondary_frameworks: Annotated[list[str] | None, Field(description="Override secondary frameworks (max 2). Use the strategies tool for valid values.")] = None,  # noqa: E501
    codebase_context: Annotated[dict | None, Field(description="Optional codebase context dict with keys: language, framework, description, conventions, patterns, code_snippets, documentation, test_framework, test_patterns. Grounds the optimization in a real project.")] = None,  # noqa: E501
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

    # Capture original scores for delta computation
    original_scores = extract_raw_scores(opt)

    result = await promptforge_optimize(
        prompt=raw_prompt,
        ctx=ctx,
        project=orig_project,
        tags=orig_tags,
        title=orig_title,
        strategy=strategy if strategy is not None else orig_strategy,
        secondary_frameworks=(
            secondary_frameworks
            if secondary_frameworks is not None
            else orig_secondary
        ),
        prompt_id=orig_prompt_id,
        version=orig_version,
        codebase_context=codebase_context,
    )

    # Set retry_of on the new record
    new_id = result.get("id")
    if new_id:
        async with _repo_session() as (repo, session):
            new_opt = await repo.get_by_id(new_id)
            if new_opt:
                new_opt.retry_of = optimization_id
                await session.commit()

    # Compute and include score deltas (display-scale and raw)
    new_raw_scores = {k: result.get(f"{k}_raw") for k in _SCORE_FIELDS}
    score_deltas, score_deltas_raw = compute_score_deltas(new_raw_scores, original_scores)
    if score_deltas:
        result["score_deltas"] = score_deltas
    if score_deltas_raw:
        result["score_deltas_raw"] = score_deltas_raw
    result["retry_of"] = optimization_id

    return result


# --- Tool 3: get ---

@mcp.tool(
    name="get",
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
@_mcp_tracked("get")
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

        result = with_display_and_raw_scores(optimization_to_dict(opt))

        # Compute score_deltas for retry records (mirrors HTTP GET behavior)
        retry_of = getattr(opt, "retry_of", None)
        if retry_of and opt.status == "completed":
            original = await repo.get_by_id(retry_of)
            if original:
                deltas, deltas_raw = compute_score_deltas(
                    extract_raw_scores(opt), extract_raw_scores(original),
                )
                if deltas:
                    result["score_deltas"] = deltas
                if deltas_raw:
                    result["score_deltas_raw"] = deltas_raw

        return result


# --- Tool 4: list ---

@mcp.tool(
    name="list",
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
@_mcp_tracked("list")
async def promptforge_list(
    project: Annotated[str | None, Field(description="Filter by project name")] = None,
    project_id: Annotated[str | None, Field(description="Filter by project UUID")] = None,
    task_type: Annotated[str | None, Field(description="Filter by task type (e.g. 'coding', 'creative', 'reasoning')")] = None,  # noqa: E501
    min_score: Annotated[float | None, Field(description="Minimum overall score filter (1-10 scale)")] = None,  # noqa: E501
    search: Annotated[str | None, Field(description="Full-text search across prompt text")] = None,  # noqa: E501
    include_archived: Annotated[bool, Field(description="Include items from archived projects")] = True,  # noqa: E501
    limit: Annotated[int, Field(description="Max items to return (1-100)")] = 20,
    offset: Annotated[int, Field(description="Items to skip for pagination")] = 0,
    sort: Annotated[str, Field(description="Sort field: 'created_at', 'overall_score', 'task_type'")] = "created_at",  # noqa: E501
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


# --- Tool 5: get_by_project ---

@mcp.tool(
    name="get_by_project",
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
@_mcp_tracked("get_by_project")
async def promptforge_get_by_project(
    project: Annotated[str, Field(description="Project name to retrieve optimizations for")],
    include_prompts: Annotated[bool, Field(description="Include full prompt text in results")] = True,  # noqa: E501
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
            converted = [with_display_and_raw_scores(optimization_to_dict(opt)) for opt in items]
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


# --- Tool 6: search ---

@mcp.tool(
    name="search",
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
@_mcp_tracked("search")
async def promptforge_search(
    query: Annotated[str, Field(description="Search text (min 2 chars). Matches prompts, titles, tags, projects.")],  # noqa: E501
    include_archived: Annotated[bool, Field(description="Include items from archived projects")] = True,  # noqa: E501
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


# --- Tool 7: tag ---

@mcp.tool(
    name="tag",
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
@_mcp_tracked("tag")
async def promptforge_tag(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to update")],
    add_tags: Annotated[list[str] | None, Field(description="Tags to add (each max 50 chars)")] = None,  # noqa: E501
    remove_tags: Annotated[list[str] | None, Field(description="Tags to remove")] = None,
    project: Annotated[str | None, Field(description="Set project name (max 100 chars; empty string to clear)")] = None,  # noqa: E501
    title: Annotated[str | None, Field(description="Set title (max 200 chars; empty string to clear)")] = None,  # noqa: E501
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
            project_info = await ensure_project_by_name(session, project)
            result["project_id"] = project_info.id if project_info else None

        await session.commit()
        if project is not None:
            invalidate_stats_cache()
        return result


# --- Tool 8: stats ---

@mcp.tool(
    name="stats",
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
@_mcp_tracked("stats")
async def promptforge_stats(
    project: Annotated[str | None, Field(description="Scope statistics to a specific project name")] = None,  # noqa: E501
) -> dict[str, object]:
    """Get usage statistics including totals, averages, and distributions.

    Returns scores on 1-10 scale, improvement rate, strategy distribution, etc.
    """
    async with _repo_session() as (_repo, session):
        raw = await get_stats_cached(project, session)
        # Shallow copy to avoid mutating the cached dict
        stats = dict(raw)
        # Convert per-strategy flat score dict (str→float) before recursive walk
        if stats.get("score_by_strategy"):
            stats["score_by_strategy"] = {
                name: score_to_display(val)
                for name, val in stats["score_by_strategy"].items()
            }
        # Recursively convert all known score fields from 0.0-1.0 to 1-10
        return _convert_scores_recursive(stats)


# --- Tool 9: delete ---

@mcp.tool(
    name="delete",
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
@_mcp_tracked("delete")
async def promptforge_delete(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to permanently delete")],  # noqa: E501
) -> dict[str, object]:
    """Permanently delete an optimization record. Cannot be undone."""
    _validate_uuid(optimization_id, "optimization_id")

    async with _repo_session() as (repo, session):
        deleted = await repo.delete_by_id(optimization_id)

        if not deleted:
            raise ToolError(f"Optimization not found: {optimization_id}")

        await session.commit()
        invalidate_stats_cache()
        return {"deleted": True, "id": optimization_id}


# --- Tool 10: bulk_delete ---

@mcp.tool(
    name="bulk_delete",
    description=(
        "Delete multiple optimization records by ID in a single call. "
        "Returns which IDs were deleted and which were not found. "
        "Accepts 1-100 IDs. This action cannot be undone."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
@_mcp_tracked("bulk_delete")
async def promptforge_bulk_delete(
    ids: Annotated[list[str], Field(description="List of optimization UUIDs to delete (1-100)")],
) -> dict[str, object]:
    """Delete multiple optimization records by ID.

    Returns deleted_count, deleted_ids, and not_found_ids.
    """
    if not ids:
        raise ToolError("ids list must not be empty")
    if len(ids) > 100:
        raise ToolError("ids list must contain 100 or fewer entries")

    async with _repo_session() as (repo, session):
        deleted_ids, not_found_ids = await repo.delete_by_ids(ids)
        await session.commit()
        if deleted_ids:
            invalidate_stats_cache()
        return {
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids,
            "not_found_ids": not_found_ids,
        }


# --- Tool 11: list_projects ---

@mcp.tool(
    name="list_projects",
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
@_mcp_tracked("list_projects")
async def promptforge_list_projects(
    status: Annotated[str | None, Field(description="Filter by status: 'active' or 'archived'. Omit for all non-deleted.")] = None,  # noqa: E501
    search: Annotated[str | None, Field(description="Search by project name or description")] = None,  # noqa: E501
    limit: Annotated[int, Field(description="Max items to return (1-100)")] = 20,
    offset: Annotated[int, Field(description="Items to skip for pagination")] = 0,
    sort: Annotated[str, Field(description="Sort field: 'created_at', 'updated_at', 'name'")] = "created_at",  # noqa: E501
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


# --- Tool 12: get_project ---

@mcp.tool(
    name="get_project",
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
@_mcp_tracked("get_project")
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

        result = _project_to_dict(project, include_context=True)
        result["prompts"] = [_prompt_to_dict(p) for p in (project.prompts or [])]
        return result


# --- Tool 13: strategies ---

@mcp.tool(
    name="strategies",
    description=(
        "List all available optimization strategies with descriptions. "
        "Use this to discover valid strategy names before calling "
        "optimize or retry with a strategy override."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
@_mcp_tracked("strategies")
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


# --- Tool 14: create_project ---

@mcp.tool(
    name="create_project",
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
@_mcp_tracked("create_project")
async def promptforge_create_project(
    name: Annotated[str, Field(description="Unique project name (1-100 chars)")],
    description: Annotated[str | None, Field(description="Project description (max 2000 chars)")] = None,  # noqa: E501
    parent_id: Annotated[str | None, Field(description="Parent folder ID. Null or omit for root-level.")] = None,  # noqa: E501
    context_profile: Annotated[dict | None, Field(description="Codebase context profile dict with keys: language, framework, description, conventions, patterns, code_snippets, documentation, test_framework, test_patterns.")] = None,  # noqa: E501
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

    # Serialize context profile
    ctx_json = None
    if context_profile:
        ctx = codebase_context_from_dict(context_profile)
        ctx_dict = context_to_dict(ctx)
        ctx_json = json.dumps(ctx_dict) if ctx_dict else None

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)

        # Reactivation check only applies to root-level projects
        if parent_id is None:
            existing = await proj_repo.get_by_name(name)

            if existing:
                if existing.status == ProjectStatus.DELETED:
                    # Reactivate soft-deleted project
                    existing.status = ProjectStatus.ACTIVE
                    if description is not None:
                        existing.description = description
                    if ctx_json is not None:
                        existing.context_profile = ctx_json
                    existing.updated_at = datetime.now(timezone.utc)
                    await session.flush()
                    await session.commit()
                    invalidate_stats_cache()
                    return _project_to_dict(existing, include_context=True)
                raise ToolError(f"Project already exists: {name!r}")

        try:
            project = await proj_repo.create(
                name=name, description=description, context_profile=ctx_json,
                parent_id=parent_id,
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        await session.commit()
        invalidate_stats_cache()
        return _project_to_dict(project, include_context=True)


# --- Tool 15: add_prompt ---

@mcp.tool(
    name="add_prompt",
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
@_mcp_tracked("add_prompt")
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


# --- Tool 16: update_prompt ---

@mcp.tool(
    name="update_prompt",
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
@_mcp_tracked("update_prompt")
async def promptforge_update_prompt(
    prompt_id: Annotated[str, Field(description="UUID of the prompt to update")],
    content: Annotated[str, Field(description="New prompt content (1-100,000 chars)")],
    optimization_id: Annotated[str | None, Field(description="UUID of the optimization that inspired this update (for version tracking)")] = None,  # noqa: E501
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


# --- Tool 17: set_project_context ---

@mcp.tool(
    name="set_project_context",
    description=(
        "Set or clear the codebase context profile on a project. "
        "Context profiles are automatically resolved during optimization "
        "when a project name is specified."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
@_mcp_tracked("set_project_context")
async def promptforge_set_project_context(
    project_id: Annotated[str, Field(description="UUID of the project to update")],
    context_profile: Annotated[dict | None, Field(description="Codebase context profile dict. Pass null to clear. Keys: language, framework, description, conventions, patterns, code_snippets, documentation, test_framework, test_patterns.")] = None,  # noqa: E501
) -> dict[str, object]:
    """Set or clear the codebase context profile on a project.

    Returns the updated project record with context_profile included.
    """
    _validate_uuid(project_id, "project_id")

    ctx_json: str | None = None
    if context_profile:
        ctx = codebase_context_from_dict(context_profile)
        ctx_dict = context_to_dict(ctx)
        ctx_json = json.dumps(ctx_dict) if ctx_dict else None

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        project = await proj_repo.get_by_id(project_id, load_prompts=False)

        if not project or project.status == ProjectStatus.DELETED:
            raise ToolError(f"Project not found: {project_id}")
        if project.status == ProjectStatus.ARCHIVED:
            raise ToolError(f"Cannot modify archived project: {project.name}")

        await proj_repo.update(project, context_profile=ctx_json)
        await session.commit()

        return _project_to_dict(project, include_context=True)


# --- Tool 18: batch ---

@mcp.tool(
    name="batch",
    description=(
        "Optimize multiple prompts in a single call. Runs the full pipeline "
        "sequentially on each prompt (1-20). Returns summary with per-prompt "
        "results including scores and optimization IDs."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
@_mcp_tracked("batch")
async def promptforge_batch(
    prompts: Annotated[list[str], Field(description="List of prompts to optimize (1-20)")],
    ctx: Context,
    strategy: Annotated[str | None, Field(description="Strategy override for all prompts")] = None,
    project: Annotated[str | None, Field(description="Project to associate results with")] = None,
    tags: Annotated[list[str] | None, Field(description="Tags for all results")] = None,
    codebase_context: Annotated[
        dict | None,
        Field(description="Codebase context for all prompts in the batch"),
    ] = None,
) -> dict[str, object]:
    """Optimize multiple prompts sequentially. Failed items don't stop the batch.

    Returns total, completed, failed counts and per-item results.
    """
    if not prompts:
        raise ToolError("prompts list must not be empty")
    if len(prompts) > 20:
        raise ToolError("prompts list must contain 20 or fewer entries")
    if tags:
        _validate_tags(tags)
    if project is not None and len(project) > 100:
        raise ToolError("Project name must be 100 characters or fewer")

    valid_strategies = {s.value for s in Strategy}
    if strategy is not None:
        strategy = LEGACY_STRATEGY_ALIASES.get(strategy, strategy)
        if strategy not in valid_strategies:
            raise ToolError(
                f"Unknown strategy {strategy!r}."
                f" Valid: {', '.join(sorted(valid_strategies))}"
            )

    # Resolve project context once for the entire batch (3-layer: workspace → manual → explicit)
    from apps.promptforge.repositories.workspace import WorkspaceRepository
    explicit_context = codebase_context_from_dict(codebase_context)
    resolved_context = None
    if project:
        async with _repo_session() as (_repo, session):
            ws_repo = WorkspaceRepository(session)
            workspace_context = await ws_repo.get_workspace_context_by_project_name(project)
            project_context = await ProjectRepository(session).get_context_by_name(project)
            base_context = merge_contexts(workspace_context, project_context)  # manual wins
            resolved_context = merge_contexts(base_context, explicit_context)  # per-request wins
    elif explicit_context:
        resolved_context = explicit_context

    results: list[dict[str, object]] = []
    completed = 0
    failed = 0

    for i, prompt_text in enumerate(prompts):
        prompt_text = prompt_text.strip()
        if not prompt_text:
            results.append({"index": i, "status": "error", "error": "Empty prompt"})
            failed += 1
            continue

        progress_msg = f"Optimizing prompt {i + 1}/{len(prompts)}"
        await ctx.report_progress(i / len(prompts), 1.0, progress_msg)
        await _emit_tool_progress(i / len(prompts), progress_msg)

        optimization_id = str(uuid.uuid4())
        start_time = time.time()
        batch_tags = tags or ["batch"]

        try:
            async with _repo_session() as (repo, session):
                opt = Optimization(
                    id=optimization_id,
                    raw_prompt=prompt_text,
                    status=OptimizationStatus.RUNNING,
                    project=project,
                    tags=json.dumps(batch_tags),
                    title=f"Batch #{i + 1}",
                )
                # Snapshot resolved context on the record
                if resolved_context:
                    ctx_dict = context_to_dict(resolved_context)
                    if ctx_dict:
                        opt.codebase_context_snapshot = json.dumps(ctx_dict)
                session.add(opt)
                if project:
                    await ensure_project_by_name(session, project)
                await session.commit()

            result = await run_pipeline(
                prompt_text,
                strategy_override=strategy,
                codebase_context=resolved_context,
            )
            _elapsed_ms = int((time.time() - start_time) * 1000)

            await update_optimization_status(
                optimization_id,
                result_data=asdict(result),
                start_time=start_time,
                model_fallback=result.model_used,
            )

            results.append({
                "index": i,
                "optimization_id": optimization_id,
                "overall_score": score_to_display(result.overall_score),
                "status": "completed",
            })
            completed += 1
        except Exception as exc:
            logger.exception("Batch item %d failed: %s", i, exc)
            try:
                await update_optimization_status(optimization_id, error=str(exc)[:500])
            except Exception:
                pass
            results.append({
                "index": i,
                "optimization_id": optimization_id,
                "status": "error",
                "error": str(exc)[:200],
            })
            failed += 1

    if completed > 0:
        invalidate_stats_cache()

    await ctx.report_progress(1.0, 1.0, "Batch complete")
    await _emit_tool_progress(1.0, "Batch complete")

    return {
        "total": len(prompts),
        "completed": completed,
        "failed": failed,
        "results": results,
    }


# --- Tool 19: cancel ---

@mcp.tool(
    name="cancel",
    description=(
        "Cancel a running optimization. Sets its status to CANCELLED "
        "for bookkeeping. Use this when an optimization is stuck or "
        "no longer needed."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
@_mcp_tracked("cancel")
async def promptforge_cancel(
    optimization_id: Annotated[str, Field(description="UUID of the optimization to cancel")],
) -> dict[str, object]:
    """Cancel a running optimization by setting its status to CANCELLED."""
    _validate_uuid(optimization_id, "optimization_id")

    async with _repo_session() as (repo, session):
        opt = await repo.get_by_id(optimization_id)

        if not opt:
            raise ToolError(f"Optimization not found: {optimization_id}")

        if opt.status != OptimizationStatus.RUNNING:
            raise ToolError(f"Cannot cancel optimization in '{opt.status}' status")

        opt.status = OptimizationStatus.CANCELLED
        await session.commit()
        invalidate_stats_cache()

    return {"id": optimization_id, "status": "cancelled"}


# --- Tool 20: sync_workspace ---

@mcp.tool(
    name="sync_workspace",
    description=(
        "Sync workspace context from a local codebase to a PromptForge project. "
        "For Claude Code CLI users: pass repo metadata, file tree, and dependencies. "
        "Creates or updates a workspace link with auto-detected codebase context. "
        "This context serves as the base layer — manual context overrides it."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
@_mcp_tracked("sync_workspace")
async def promptforge_sync_workspace(
    project: Annotated[str, Field(description="Project name (auto-creates if new)")],
    workspace_info: Annotated[
        dict,
        Field(description=(
            "Workspace metadata: {repo_url, git_branch, file_tree (list of paths), "
            "dependencies ({name: version})}"
        )),
    ],
    context: Annotated[
        dict | None,
        Field(
            description="Optional pre-analyzed CodebaseContext dict from Claude Code",
            default=None,
        ),
    ] = None,
) -> dict[str, object]:
    """Sync workspace context from Claude Code to a PromptForge project."""
    if not project or not project.strip():
        raise ToolError("project name must not be empty")
    project = project.strip()
    if len(project) > 100:
        raise ToolError("Project name must be 100 characters or fewer")

    from apps.promptforge.repositories.workspace import WorkspaceRepository
    from apps.promptforge.services.workspace_sync import extract_context_from_workspace_info

    # Extract context from workspace_info or use pre-analyzed context
    if context:
        extracted_context = codebase_context_from_dict(context)
        ctx_dict = context_to_dict(extracted_context) if extracted_context else None
    else:
        extracted = extract_context_from_workspace_info(workspace_info)
        ctx_dict = context_to_dict(extracted) if extracted else None

    repo_url = workspace_info.get("repo_url", "")
    git_branch = workspace_info.get("git_branch", "main")
    file_tree = workspace_info.get("file_tree", [])
    deps = workspace_info.get("dependencies", {})

    # Derive repo_full_name from URL
    repo_full_name = ""
    if repo_url:
        # Extract owner/repo from URL like https://github.com/owner/repo
        parts = repo_url.rstrip("/").split("/")
        if len(parts) >= 2:
            repo_full_name = f"{parts[-2]}/{parts[-1]}"

    async with _repo_session() as (_repo, session):
        ws_repo = WorkspaceRepository(session)

        # Ensure project exists
        project_info = await ensure_project_by_name(session, project)
        if not project_info:
            raise ToolError(f"Failed to create/find project: {project}")

        # Get or create workspace link
        link = await ws_repo.get_link_by_project_id(project_info.id)
        if link:
            # Update existing link
            link.repo_full_name = repo_full_name or link.repo_full_name
            link.repo_url = repo_url or link.repo_url
            link.default_branch = git_branch
            link.sync_source = "claude-code"
        else:
            link = await ws_repo.create_link(
                project_id=project_info.id,
                repo_full_name=repo_full_name or "local/workspace",
                repo_url=repo_url or "",
                default_branch=git_branch,
                sync_source="claude-code",
            )

        await ws_repo.update_sync_status(
            link,
            "synced",
            workspace_context=ctx_dict,
            dependencies_snapshot=deps or None,
            file_tree_snapshot=file_tree[:500] if file_tree else None,
        )
        await session.commit()

    return {
        "id": link.id,
        "project": project,
        "sync_status": "synced",
        "context_fields": list(ctx_dict.keys()) if ctx_dict else [],
    }


# --- Tool 21: get_children ---

@mcp.tool(
    name="get_children",
    description=(
        "List direct children (folders and prompts) of a folder or root. "
        "Returns folder and prompt nodes with type, name, parent_id, depth. "
        "Pass parent_id=null or omit it to list root-level items."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
@_mcp_tracked("get_children")
async def promptforge_get_children(
    parent_id: Annotated[
        str | None,
        Field(description="Parent folder ID. Null or omit for root-level items."),
    ] = None,
) -> dict[str, object]:
    """List folders and prompts under a parent folder (or root)."""
    if parent_id is not None:
        _validate_uuid(parent_id, "parent_id")

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)

        if parent_id is not None:
            parent = await proj_repo.get_by_id(parent_id, load_prompts=False)
            if not parent:
                raise ToolError(f"Folder not found: {parent_id}")

        folders, prompts = await proj_repo.get_children(parent_id)

        folder_nodes = [
            {
                "id": f.id,
                "name": f.name,
                "type": "folder",
                "parent_id": f.parent_id,
                "depth": f.depth,
            }
            for f in folders
        ]
        prompt_nodes = [
            {
                "id": p.id,
                "name": (
                    p.content[:60].replace("\n", " ") if p.content else "Untitled"
                ),
                "type": "prompt",
                "parent_id": p.project_id,
                "version": p.version,
            }
            for p in prompts
        ]

        path: list[dict[str, str]] = []
        if parent_id is not None:
            raw_path = await proj_repo.get_path(parent_id)
            path = raw_path

        return {
            "nodes": folder_nodes + prompt_nodes,
            "path": path,
            "total": len(folder_nodes) + len(prompt_nodes),
        }


# --- Tool 22: move ---

@mcp.tool(
    name="move",
    description=(
        "Move a folder or prompt to a new parent folder (or root). "
        "Validates depth limits, circular references, and name uniqueness."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
@_mcp_tracked("move")
async def promptforge_move(
    type: Annotated[
        str,
        Field(description="Type of node to move: 'project' (folder) or 'prompt'"),
    ],
    id: Annotated[str, Field(description="ID of the node to move")],
    new_parent_id: Annotated[
        str | None,
        Field(description="Target folder ID. Null or omit to move to root/desktop."),
    ] = None,
) -> dict[str, object]:
    """Move a folder or prompt to a new location in the hierarchy."""
    if type not in ("project", "prompt"):
        raise ToolError("type must be 'project' or 'prompt'")
    _validate_uuid(id, "id")
    if new_parent_id is not None:
        _validate_uuid(new_parent_id, "new_parent_id")

    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)

        try:
            if type == "project":
                project = await proj_repo.move_project(id, new_parent_id)
                node = _project_to_dict(project)
            else:
                prompt = await proj_repo.move_prompt(id, new_parent_id)
                node = _prompt_to_dict(prompt)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        await session.commit()
        return {"success": True, "node": node}


# --- MCP Resources ---
# Expose PromptForge data for bi-directional context flow with Claude Code.


@mcp.resource("promptforge://projects")
async def resource_projects() -> str:
    """JSON list of active projects with context profile indicators."""
    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        filters = ProjectFilters(status="active")
        pagination = ProjectPagination(sort="updated_at", order="desc", offset=0, limit=100)
        projects, _total = await proj_repo.list(filters=filters, pagination=pagination)
        items = [_project_to_dict(p, include_context=True) for p in projects]
        return json.dumps(items, indent=2)


@mcp.resource("promptforge://projects/{project_id}/context")
async def resource_project_context(project_id: str) -> str:
    """Single project's codebase context profile as JSON."""
    _validate_uuid(project_id, "project_id")
    async with async_session_factory() as session:
        proj_repo = ProjectRepository(session)
        project = await proj_repo.get_by_id(project_id, load_prompts=False)
        if not project:
            return json.dumps({"error": f"Project not found: {project_id}"})
        if project.context_profile:
            try:
                return project.context_profile  # Already JSON string
            except Exception:
                return json.dumps({"error": "Invalid context profile"})
        return json.dumps({"info": "No context profile set for this project"})


@mcp.resource("promptforge://optimizations/{optimization_id}")
async def resource_optimization(optimization_id: str) -> str:
    """Full optimization result with display scores as JSON."""
    _validate_uuid(optimization_id, "optimization_id")
    async with _repo_session() as (repo, _session):
        opt = await repo.get_by_id(optimization_id)
        if not opt:
            return json.dumps({"error": f"Optimization not found: {optimization_id}"})
        return json.dumps(with_display_and_raw_scores(optimization_to_dict(opt)), indent=2)


@mcp.resource("promptforge://workspaces")
async def resource_workspaces() -> str:
    """JSON list of all workspace links with sync status and context completeness."""
    async with async_session_factory() as session:
        from apps.promptforge.repositories.workspace import WorkspaceRepository
        statuses = await WorkspaceRepository(session).get_all_workspace_statuses()
        return json.dumps(statuses, indent=2)


# --- ASGI app for HTTP transport (SSE) ---
# Used by: uvicorn apps.promptforge.mcp_server:app --reload --port 8001
# Provides hot-reload in dev, unlike stdio which loads code once.
#
# The SSE app is wrapped in a Starlette parent to add a /health endpoint
# for connectivity probes from the main backend.

from starlette.applications import Starlette  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402


async def mcp_health(request):
    """Zero-state health probe — confirms the MCP process is alive."""
    return JSONResponse({"status": "ok", "server": "promptforge_mcp"})


from app.middleware.mcp_auth import MCPAuthMiddleware  # noqa: E402
from app.middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402

_mcp_sse = mcp.sse_app()
app = Starlette(routes=[
    Route("/health", mcp_health),
    Mount("/", _mcp_sse),
])

# Security middleware — order: outer (first to run) → inner (closest to handler)
# 1. Security headers on all responses
app.add_middleware(SecurityHeadersMiddleware)
# 2. Bearer token auth (skips /health; disabled when MCP_AUTH_TOKEN is empty)
from app import config as _app_config  # noqa: E402

app.add_middleware(MCPAuthMiddleware, token=_app_config.MCP_AUTH_TOKEN)


# --- Main entry point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
