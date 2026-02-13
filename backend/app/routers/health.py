"""Health check endpoint for monitoring service status."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.database import get_db

router = APIRouter(tags=["health"])


async def _health_response(db: AsyncSession):
    """Shared health check logic."""
    db_connected = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_connected = result.scalar() == 1
    except Exception:
        db_connected = False

    # SDK uses CLI auth (MAX subscription), no API key needed
    from app.services.claude_client import ClaudeClient

    claude_available = ClaudeClient().is_available()

    return {
        "status": "ok",
        "claude_available": claude_available,
        "db_connected": db_connected,
        "version": config.APP_VERSION,
    }


@router.api_route("/api/health", methods=["GET", "HEAD"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check the health of the API, database connection, and Claude availability.

    Returns a JSON object with status information for each component.
    """
    return await _health_response(db)


@router.api_route("/health", methods=["GET", "HEAD"])
async def health_check_alias(db: AsyncSession = Depends(get_db)):
    """Alias for /api/health at the root path.

    Some monitoring tools expect health checks at /health.
    """
    return await _health_response(db)
