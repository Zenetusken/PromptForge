"""Health check endpoint for monitoring service status."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check the health of the API, database connection, and Claude availability.

    Returns a JSON object with status information for each component.
    """
    db_connected = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_connected = result.scalar() == 1
    except Exception:
        db_connected = False

    claude_available = bool(config.ANTHROPIC_API_KEY)

    return {
        "status": "ok",
        "claude_available": claude_available,
        "db_connected": db_connected,
        "version": config.APP_VERSION,
    }
