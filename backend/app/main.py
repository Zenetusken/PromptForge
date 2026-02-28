"""FastAPI application entry point for PromptForge."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app import config
from app.database import init_db
from app.middleware.audit import AuditMiddleware
from app.middleware.auth import AuthMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import (
    filesystem,
    github,
    health,
    history,
    mcp_activity,
    optimize,
    projects,
    providers,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - initializes database on startup."""
    await init_db()
    # Validate configured LLM provider early so operators get immediate feedback
    env_provider = config.LLM_PROVIDER
    if env_provider:
        try:
            from app.providers import get_provider
            from app.providers.errors import ProviderError
            get_provider(env_provider)
            logger.info("Startup: LLM_PROVIDER=%r is valid and available", env_provider)
        except (ValueError, RuntimeError, ImportError, ProviderError) as exc:
            logger.warning(
                "Startup: LLM_PROVIDER=%r is invalid or unavailable: %s",
                env_provider, exc,
            )
    yield
    # Shutdown: close persistent HTTP clients
    from app.routers.health import _mcp_client
    await _mcp_client.aclose()


app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware stack (outermost → innermost)
# Order: GZip → SecurityHeaders → CORS → CSRF → RateLimit → Auth → Audit → Router
# ---------------------------------------------------------------------------

# Audit (innermost — logs after route handling)
app.add_middleware(AuditMiddleware)

# Auth
app.add_middleware(AuthMiddleware)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# CSRF — Origin-based validation for state-changing requests
app.add_middleware(CSRFMiddleware)

# CORS — explicit methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.FRONTEND_URL.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-LLM-API-Key",
        "X-LLM-Model",
        "X-LLM-Provider",
        "X-Confirm-Delete",
        "If-Unmodified-Since",
    ],
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# GZip compression (outermost — compresses responses ≥4KB, avoids CPU waste on small payloads)
app.add_middleware(GZipMiddleware, minimum_size=4096)

# Include routers
app.include_router(health.router)
app.include_router(optimize.router)
app.include_router(history.router)
app.include_router(projects.router)
app.include_router(filesystem.router)
app.include_router(providers.router)
app.include_router(mcp_activity.router)
app.include_router(github.router)


@app.get("/")
async def root():
    """Root endpoint redirecting to API docs."""
    return {
        "name": config.APP_TITLE,
        "version": config.APP_VERSION,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
