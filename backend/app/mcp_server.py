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

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine, init_db
from app.models.optimization import Optimization
from app.services.claude_client import ClaudeClient
from app.services.pipeline import run_pipeline


# --- Helpers ---

def _serialize_json_field(value: str | None) -> list[str] | None:
    """Deserialize a JSON string field to a list."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _opt_to_dict(opt: Optimization) -> dict:
    """Convert an Optimization ORM object to a serializable dict."""
    return {
        "id": opt.id,
        "created_at": opt.created_at.isoformat() if opt.created_at else None,
        "raw_prompt": opt.raw_prompt,
        "optimized_prompt": opt.optimized_prompt,
        "task_type": opt.task_type,
        "complexity": opt.complexity,
        "weaknesses": _serialize_json_field(opt.weaknesses),
        "strengths": _serialize_json_field(opt.strengths),
        "changes_made": _serialize_json_field(opt.changes_made),
        "framework_applied": opt.framework_applied,
        "optimization_notes": opt.optimization_notes,
        "clarity_score": opt.clarity_score,
        "specificity_score": opt.specificity_score,
        "structure_score": opt.structure_score,
        "faithfulness_score": opt.faithfulness_score,
        "overall_score": opt.overall_score,
        "is_improvement": opt.is_improvement,
        "verdict": opt.verdict,
        "duration_ms": opt.duration_ms,
        "model_used": opt.model_used,
        "status": opt.status,
        "error_message": opt.error_message,
        "project": opt.project,
        "tags": _serialize_json_field(opt.tags),
        "title": opt.title,
    }


def _opt_to_summary(opt: Optimization) -> dict:
    """Convert an Optimization ORM object to a summary dict (for list views)."""
    raw = opt.raw_prompt or ""
    return {
        "id": opt.id,
        "created_at": opt.created_at.isoformat() if opt.created_at else None,
        "raw_prompt_preview": raw[:100] + ("..." if len(raw) > 100 else ""),
        "task_type": opt.task_type,
        "complexity": opt.complexity,
        "overall_score": _score_to_int(opt.overall_score),
        "status": opt.status,
        "project": opt.project,
        "tags": _serialize_json_field(opt.tags),
        "title": opt.title,
    }


def _score_to_int(score: float | None) -> int | None:
    """Convert a 0.0-1.0 float score to a 1-10 integer scale."""
    if score is None:
        return None
    # Scores may already be on 1-10 scale or 0-1 scale
    if score <= 1.0:
        return max(1, min(10, round(score * 10)))
    return max(1, min(10, round(score)))


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
        "Optimize a raw prompt using the PromptForge 3-step pipeline "
        "(Analyze → Optimize → Validate). Returns the optimized prompt, "
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
) -> dict:
    """Run the full optimization pipeline on a prompt.

    Args:
        prompt: The raw prompt text to optimize.
        project: Optional project name to associate with the optimization.
        tags: Optional list of tags.
        title: Optional title for the optimization.
    """
    start_time = time.time()
    optimization_id = str(uuid.uuid4())

    # Create initial DB record
    async with async_session_factory() as session:
        opt = Optimization(
            id=optimization_id,
            raw_prompt=prompt,
            status="running",
            project=project,
            tags=json.dumps(tags) if tags else None,
            title=title,
        )
        session.add(opt)
        await session.commit()

    # Run pipeline
    try:
        result = await run_pipeline(prompt)
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Update DB record with results
        async with async_session_factory() as session:
            stmt = select(Optimization).where(Optimization.id == optimization_id)
            db_result = await session.execute(stmt)
            opt = db_result.scalar_one_or_none()
            if opt:
                opt.status = "completed"
                opt.optimized_prompt = result.optimized_prompt
                opt.task_type = result.task_type
                opt.complexity = result.complexity
                opt.weaknesses = json.dumps(result.weaknesses)
                opt.strengths = json.dumps(result.strengths)
                opt.changes_made = json.dumps(result.changes_made)
                opt.framework_applied = result.framework_applied
                opt.optimization_notes = result.optimization_notes
                opt.clarity_score = result.clarity_score
                opt.specificity_score = result.specificity_score
                opt.structure_score = result.structure_score
                opt.faithfulness_score = result.faithfulness_score
                opt.overall_score = result.overall_score
                opt.is_improvement = result.is_improvement
                opt.verdict = result.verdict
                opt.duration_ms = elapsed_ms
                opt.model_used = result.model_used
                await session.commit()

        return {
            "id": optimization_id,
            "optimized_prompt": result.optimized_prompt,
            "task_type": result.task_type,
            "complexity": result.complexity,
            "weaknesses": result.weaknesses,
            "strengths": result.strengths,
            "changes_made": result.changes_made,
            "framework_applied": result.framework_applied,
            "optimization_notes": result.optimization_notes,
            "scores": {
                "clarity": _score_to_int(result.clarity_score),
                "specificity": _score_to_int(result.specificity_score),
                "structure": _score_to_int(result.structure_score),
                "faithfulness": _score_to_int(result.faithfulness_score),
                "overall": _score_to_int(result.overall_score),
            },
            "is_improvement": result.is_improvement,
            "verdict": result.verdict,
            "duration_ms": elapsed_ms,
            "status": "completed",
        }
    except Exception as e:
        # Update DB with error
        async with async_session_factory() as session:
            stmt = select(Optimization).where(Optimization.id == optimization_id)
            db_result = await session.execute(stmt)
            opt = db_result.scalar_one_or_none()
            if opt:
                opt.status = "error"
                opt.error_message = str(e)
                await session.commit()
        return {"error": str(e), "id": optimization_id, "status": "error"}


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
async def promptforge_get(optimization_id: str) -> dict:
    """Get a single optimization by ID.

    Args:
        optimization_id: The UUID of the optimization to retrieve.
    """
    async with async_session_factory() as session:
        stmt = select(Optimization).where(Optimization.id == optimization_id)
        result = await session.execute(stmt)
        opt = result.scalar_one_or_none()

        if not opt:
            return {"error": f"Optimization not found: {optimization_id}"}

        return _opt_to_dict(opt)


# --- Tool 3: promptforge_list ---

@mcp.tool(
    name="promptforge_list",
    description=(
        "List optimization records with filtering, sorting, and pagination. "
        "Supports filtering by project, task_type, min_score, and search text. "
        "Returns paginated results with offset-based pagination."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def promptforge_list(
    project: str | None = None,
    task_type: str | None = None,
    min_score: float | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = "created_at",
    order: str = "desc",
) -> dict:
    """List optimizations with optional filters.

    Args:
        project: Filter by project name.
        task_type: Filter by task type (e.g., 'coding', 'creative').
        min_score: Filter to only include items with overall_score >= this value (1-10 scale).
        search: Full-text search across prompt text.
        limit: Maximum number of items to return (default 20).
        offset: Number of items to skip for pagination (default 0).
        sort: Field to sort by ('created_at', 'overall_score', 'task_type'). Default 'created_at'.
        order: Sort order ('asc' or 'desc'). Default 'desc'.
    """
    async with async_session_factory() as session:
        query = select(Optimization).where(Optimization.status == "completed")
        count_query = select(func.count(Optimization.id)).where(Optimization.status == "completed")

        # Apply filters
        if project:
            query = query.where(Optimization.project == project)
            count_query = count_query.where(Optimization.project == project)

        if task_type:
            query = query.where(Optimization.task_type == task_type)
            count_query = count_query.where(Optimization.task_type == task_type)

        if min_score is not None:
            # Scores stored as 0.0-1.0 in DB, but MCP interface uses 1-10 scale
            # Always convert from 1-10 scale to 0.0-1.0 storage scale
            threshold = min_score / 10.0 if min_score >= 1 else min_score
            query = query.where(Optimization.overall_score >= threshold)
            count_query = count_query.where(Optimization.overall_score >= threshold)

        if search:
            search_filter = (
                Optimization.raw_prompt.ilike(f"%{search}%")
                | Optimization.optimized_prompt.ilike(f"%{search}%")
                | Optimization.title.ilike(f"%{search}%")
                | Optimization.tags.ilike(f"%{search}%")
                | Optimization.project.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Get total count
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(Optimization, sort, Optimization.created_at)
        if order == "asc":
            query = query.order_by(sort_column)
        else:
            query = query.order_by(desc(sort_column))

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        optimizations = result.scalars().all()

        items = [_opt_to_summary(opt) for opt in optimizations]
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
) -> dict:
    """Get all optimizations for a project.

    Args:
        project: The project name to filter by.
        include_prompts: Whether to include full prompt text (default True).
        limit: Maximum number of results (default 50).
    """
    async with async_session_factory() as session:
        query = (
            select(Optimization)
            .where(Optimization.project == project)
            .where(Optimization.status == "completed")
            .order_by(desc(Optimization.created_at))
            .limit(limit)
        )
        result = await session.execute(query)
        optimizations = result.scalars().all()

        if include_prompts:
            items = [_opt_to_dict(opt) for opt in optimizations]
        else:
            items = [_opt_to_summary(opt) for opt in optimizations]

        return {
            "project": project,
            "items": items,
            "count": len(items),
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
    limit: int = 20,
) -> dict:
    """Search for optimizations by text.

    Args:
        query: The search query text (minimum 2 characters).
        limit: Maximum number of results (default 20).
    """
    if len(query) < 2:
        return {"error": "Search query must be at least 2 characters", "items": [], "total": 0}

    async with async_session_factory() as session:
        search_filter = (
            Optimization.raw_prompt.ilike(f"%{query}%")
            | Optimization.optimized_prompt.ilike(f"%{query}%")
            | Optimization.title.ilike(f"%{query}%")
            | Optimization.tags.ilike(f"%{query}%")
            | Optimization.project.ilike(f"%{query}%")
        )

        count_stmt = select(func.count(Optimization.id)).where(search_filter)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(Optimization)
            .where(search_filter)
            .order_by(desc(Optimization.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        optimizations = result.scalars().all()

        return {
            "items": [_opt_to_summary(opt) for opt in optimizations],
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
) -> dict:
    """Update tags and metadata on an optimization.

    Args:
        optimization_id: The UUID of the optimization to update.
        add_tags: Tags to add to the optimization.
        remove_tags: Tags to remove from the optimization.
        project: Set the project name (use empty string to clear).
        title: Set the title (use empty string to clear).
    """
    async with async_session_factory() as session:
        stmt = select(Optimization).where(Optimization.id == optimization_id)
        result = await session.execute(stmt)
        opt = result.scalar_one_or_none()

        if not opt:
            return {"error": f"Optimization not found: {optimization_id}"}

        # Handle tags
        current_tags = _serialize_json_field(opt.tags) or []

        if add_tags:
            for tag in add_tags:
                if tag not in current_tags:
                    current_tags.append(tag)

        if remove_tags:
            current_tags = [t for t in current_tags if t not in remove_tags]

        opt.tags = json.dumps(current_tags) if current_tags else None

        # Handle project
        if project is not None:
            opt.project = project if project else None

        # Handle title
        if title is not None:
            opt.title = title if title else None

        await session.commit()

        return {
            "id": optimization_id,
            "tags": current_tags,
            "project": opt.project,
            "title": opt.title,
            "updated": True,
        }


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
async def promptforge_stats(project: str | None = None) -> dict:
    """Get usage statistics.

    Args:
        project: Optional project name to scope statistics to.
    """
    async with async_session_factory() as session:
        base_filter = Optimization.status == "completed"
        if project:
            base_filter = base_filter & (Optimization.project == project)

        # Total optimizations
        total_result = await session.execute(
            select(func.count(Optimization.id)).where(base_filter)
        )
        total_optimizations = total_result.scalar() or 0

        if total_optimizations == 0:
            return {
                "total_optimizations": 0,
                "avg_overall_score": 0,
                "projects": {},
                "task_types": {},
                "top_frameworks": {},
                "optimizations_today": 0,
                "optimizations_this_week": 0,
            }

        # Average overall score
        avg_result = await session.execute(
            select(func.avg(Optimization.overall_score)).where(
                base_filter & Optimization.overall_score.isnot(None)
            )
        )
        avg_raw = avg_result.scalar()
        avg_overall = round(avg_raw * 10, 1) if avg_raw is not None and avg_raw <= 1 else round(avg_raw, 1) if avg_raw else 0

        # Projects breakdown
        projects_result = await session.execute(
            select(Optimization.project, func.count(Optimization.id))
            .where(base_filter & Optimization.project.isnot(None))
            .group_by(Optimization.project)
        )
        projects = {row[0]: row[1] for row in projects_result.all()}

        # Task types breakdown
        task_types_result = await session.execute(
            select(Optimization.task_type, func.count(Optimization.id))
            .where(base_filter & Optimization.task_type.isnot(None))
            .group_by(Optimization.task_type)
        )
        task_types = {row[0]: row[1] for row in task_types_result.all()}

        # Top frameworks
        frameworks_result = await session.execute(
            select(Optimization.framework_applied, func.count(Optimization.id))
            .where(base_filter & Optimization.framework_applied.isnot(None))
            .group_by(Optimization.framework_applied)
        )
        top_frameworks = {row[0]: row[1] for row in frameworks_result.all()}

        # Optimizations today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_result = await session.execute(
            select(func.count(Optimization.id)).where(
                base_filter & (Optimization.created_at >= today_start)
            )
        )
        optimizations_today = today_result.scalar() or 0

        # Optimizations this week (last 7 days)
        from datetime import timedelta
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        week_result = await session.execute(
            select(func.count(Optimization.id)).where(
                base_filter & (Optimization.created_at >= week_start)
            )
        )
        optimizations_this_week = week_result.scalar() or 0

        return {
            "total_optimizations": total_optimizations,
            "avg_overall_score": avg_overall,
            "projects": projects,
            "task_types": task_types,
            "top_frameworks": top_frameworks,
            "optimizations_today": optimizations_today,
            "optimizations_this_week": optimizations_this_week,
        }


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
async def promptforge_delete(optimization_id: str) -> dict:
    """Delete an optimization by ID.

    Args:
        optimization_id: The UUID of the optimization to delete.
    """
    async with async_session_factory() as session:
        stmt = select(Optimization).where(Optimization.id == optimization_id)
        result = await session.execute(stmt)
        opt = result.scalar_one_or_none()

        if not opt:
            return {"error": f"Optimization not found: {optimization_id}"}

        await session.execute(
            delete(Optimization).where(Optimization.id == optimization_id)
        )
        await session.commit()

        return {"deleted": True, "id": optimization_id}


# --- Main entry point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
