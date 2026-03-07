import logging
from fastapi import APIRouter

from app.config import settings
from app.database import check_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

# Will be set by main.py lifespan
_provider = None


def set_provider(provider):
    global _provider
    _provider = provider


@router.get("/api/health")
async def health_check():
    """Health check endpoint returning system status."""
    db_ok = await check_db_connection()

    github_oauth_enabled = bool(
        settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET
    )

    provider_name = _provider.name if _provider else "none"

    return {
        "status": "ok" if db_ok else "degraded",
        "provider": provider_name,
        "github_oauth_enabled": github_oauth_enabled,
        "db_connected": db_ok,
        "version": "2.0.0",
    }
