"""Health check endpoint for monitoring service status."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.database import get_db
from app.providers import get_provider

router = APIRouter(tags=["health"])


async def _health_response(db: AsyncSession):
    """Shared health check logic."""
    db_connected = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_connected = result.scalar() == 1
    except SQLAlchemyError:
        db_connected = False

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
        "version": config.APP_VERSION,
    }


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check the health of the API, database connection, and LLM provider availability.

    Returns a JSON object with status information for each component.
    """
    return await _health_response(db)


@router.head("/api/health", include_in_schema=False)
async def health_check_head(db: AsyncSession = Depends(get_db)):
    """HEAD variant of the health check."""
    return await _health_response(db)


@router.get("/health", include_in_schema=False)
async def health_check_alias(db: AsyncSession = Depends(get_db)):
    """Alias for /api/health at the root path.

    Some monitoring tools expect health checks at /health.
    """
    return await _health_response(db)


@router.head("/health", include_in_schema=False)
async def health_check_alias_head(db: AsyncSession = Depends(get_db)):
    """HEAD variant of the health alias."""
    return await _health_response(db)
