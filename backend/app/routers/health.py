"""Health check endpoint for monitoring service status."""

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.database import get_db_readonly
from app.providers import get_provider
from app.services.token_budget import token_budget

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Persistent client for MCP health probes — avoids TCP setup on every poll
_mcp_client = httpx.AsyncClient(timeout=1.5)


async def _check_db(db: AsyncSession) -> bool:
    """Check database connectivity."""
    try:
        result = await db.execute(text("SELECT 1"))
        return result.scalar() == 1
    except SQLAlchemyError:
        return False


async def _probe_mcp() -> bool:
    """Probe the MCP server health endpoint.

    Returns True if the MCP server responds with {"status": "ok"} within 1.5s.
    Returns False on any error (connection refused, timeout, bad response).
    """
    try:
        resp = await _mcp_client.get(
            f"http://{config.MCP_HOST}:{config.MCP_PORT}/health"
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("status") == "ok"
    except Exception:
        pass
    return False


async def _workspace_health(db: AsyncSession) -> dict:
    """Check workspace health — wrapped to never fail the health endpoint."""
    try:
        from app.repositories.workspace import WorkspaceRepository
        return await WorkspaceRepository(db).get_health_summary()
    except Exception:
        return {"github_connected": False, "total_links": 0, "synced": 0, "stale": 0, "errors": 0}


async def _health_response(db: AsyncSession):
    """Shared health check logic."""
    db_connected, mcp_connected, workspace = await asyncio.gather(
        _check_db(db), _probe_mcp(), _workspace_health(db),
    )

    try:
        provider = get_provider()
        llm_available = provider.is_available()
        llm_provider = provider.provider_name
        llm_model = provider.model_name
    except Exception:
        llm_available = False
        llm_provider = "none"
        llm_model = ""

    return {
        "status": "ok",
        "claude_available": llm_available,  # backward compat
        "llm_available": llm_available,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "db_connected": db_connected,
        "mcp_connected": mcp_connected,
        "version": config.APP_VERSION,
        "token_budgets": token_budget.to_dict(),
        "workspace": workspace,
    }


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db_readonly)):
    """Check the health of the API, database connection, and LLM provider availability.

    Returns a JSON object with status information for each component.
    """
    return await _health_response(db)


@router.head("/api/health", include_in_schema=False)
async def health_check_head(db: AsyncSession = Depends(get_db_readonly)):
    """HEAD variant of the health check."""
    return await _health_response(db)


@router.get("/health", include_in_schema=False)
async def health_check_alias(db: AsyncSession = Depends(get_db_readonly)):
    """Alias for /api/health at the root path.

    Some monitoring tools expect health checks at /health.
    """
    return await _health_response(db)


@router.head("/health", include_in_schema=False)
async def health_check_alias_head(db: AsyncSession = Depends(get_db_readonly)):
    """HEAD variant of the health alias."""
    return await _health_response(db)
