"""FastAPI application entry point for PromptForge."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.database import init_db
from app.routers import health, history, optimize, projects, providers

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


app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.FRONTEND_URL.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(optimize.router)
app.include_router(history.router)
app.include_router(projects.router)
app.include_router(providers.router)


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
