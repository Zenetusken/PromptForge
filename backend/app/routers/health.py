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
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"http://localhost:{config.MCP_PORT}/health")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("status") == "ok"
    except Exception:
        pass
    return False


async def _health_response(db: AsyncSession):
    """Shared health check logic."""
    db_connected, mcp_connected = await asyncio.gather(
        _check_db(db), _probe_mcp()
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
