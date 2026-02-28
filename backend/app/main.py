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
from kernel.routers import apps as kernel_apps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - initializes database on startup."""
    # Discover and initialize apps via kernel registry
    from kernel.registry.app_registry import get_app_registry

    registry = get_app_registry()
    registry.discover()

    await init_db(app_registry=registry)

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

    # Mount routers from discovered apps (skip promptforge — its routers are hardcoded below)
    registry.mount_routers(app, exclude={"promptforge"})

    # Call on_startup for all enabled apps
    for rec in registry.list_enabled():
        try:
            await rec.instance.on_startup(None)
        except Exception as exc:
            logger.error("App %r on_startup failed: %s", rec.manifest.id, exc)

    yield

    # Shutdown: call on_shutdown for all enabled apps
    for rec in registry.list_enabled():
        try:
            await rec.instance.on_shutdown(None)
        except Exception as exc:
            logger.error("App %r on_shutdown failed: %s", rec.manifest.id, exc)


app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware stack (outermost -> innermost)
# Order: GZip -> SecurityHeaders -> CORS -> CSRF -> RateLimit -> Auth -> Audit -> Router
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

# GZip compression (outermost — compresses responses >=4KB, avoids CPU waste on small payloads)
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
app.include_router(kernel_apps.router)


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
