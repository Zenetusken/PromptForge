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
from kernel.routers import kernel_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - initializes database on startup."""
    # Discover and initialize apps via kernel registry
    from kernel.core import Kernel
    from kernel.registry.app_registry import get_app_registry
    from kernel.services.registry import ServiceRegistry

    from app.database import async_session_factory

    registry = get_app_registry()
    registry.discover()

    await init_db(app_registry=registry)

    # Restore persisted app enable/disable states from the database.
    # Disabled apps won't get routers mounted or on_startup() called.
    await registry.restore_app_states(async_session_factory)

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

    # Construct kernel object with service registry
    services = ServiceRegistry()
    kernel = Kernel(
        app_registry=registry,
        db_session_factory=async_session_factory,
        services=services,
    )

    # Store kernel reference on registry for access by kernel routers
    registry.kernel = kernel

    # Register core services.
    # Note: "storage" and "vfs" are registered as *classes* (not instances)
    # because they require a per-request AsyncSession. Apps and routers
    # instantiate them via RepoClass(session) in each request handler.
    services.register("llm", kernel.get_provider)
    services.register("db", async_session_factory)

    from kernel.repositories.app_storage import AppStorageRepository
    services.register("storage", AppStorageRepository)

    from kernel.repositories.vfs import VfsRepository
    services.register("vfs", VfsRepository)

    from kernel.bus.event_bus import EventBus
    from kernel.bus.contracts import ContractRegistry
    contract_registry = ContractRegistry()
    event_bus = EventBus(contract_registry=contract_registry)
    services.register("bus", event_bus)
    services.register("contracts", contract_registry)

    # Create and register the background job queue
    from kernel.services.job_queue import JobQueue
    job_queue = JobQueue(max_workers=3, bus=event_bus, db_session_factory=async_session_factory)
    services.register("jobs", job_queue)

    # Validate each app's requires_services against registry
    for rec in registry.list_enabled():
        missing = services.validate_requirements(rec.manifest.requires_services)
        if missing:
            logger.warning(
                "App %r requires services %s which are not registered",
                rec.manifest.id, missing,
            )

    # Mount routers from discovered apps
    registry.mount_routers(app)

    # Call on_startup for all enabled apps and wire event bus
    for rec in registry.list_enabled():
        try:
            await rec.instance.on_startup(kernel)
        except Exception as exc:
            logger.error("App %r on_startup failed: %s", rec.manifest.id, exc)

        # Auto-register event contracts from apps
        for contract in rec.instance.get_event_contracts():
            contract_registry.register(contract)

        # Auto-register event handlers from apps
        for event_type, handler in rec.instance.get_event_handlers().items():
            event_bus.subscribe(event_type, handler, app_id=rec.manifest.id)

        # Auto-register job handlers from apps
        for job_type, handler in rec.instance.get_job_handlers().items():
            job_queue.register_handler(job_type, handler)

    # Start the job queue workers and recover any pending jobs from DB
    await job_queue.start()
    await job_queue.recover_pending()

    yield

    # Shutdown: call on_shutdown for all enabled apps before stopping the
    # job queue, since apps may have running jobs that need to finish.
    for rec in registry.list_enabled():
        try:
            await rec.instance.on_shutdown(kernel)
        except Exception as exc:
            logger.error("App %r on_shutdown failed: %s", rec.manifest.id, exc)

    # Stop the job queue after apps have shut down
    await job_queue.stop()


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

# Include kernel router (app routers are auto-mounted via registry)
app.include_router(kernel_router)


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
