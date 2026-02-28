"""Shared test fixtures for PromptForge backend tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import config
from app.database import Base, get_db, get_db_readonly
from app.main import app
from kernel.bus.contracts import ContractRegistry
from kernel.bus.event_bus import EventBus
from kernel.core import Kernel
from kernel.registry.app_registry import get_app_registry
from kernel.services.registry import ServiceRegistry

# Discover and mount app routers once at import time.
# In production, this happens inside the FastAPI lifespan handler,
# but httpx AsyncClient doesn't trigger lifespan events.
_registry = get_app_registry()
_registry.discover()
_registry.mount_routers(app)

# Set up a minimal Kernel on the registry so bus/contracts endpoints work.
# In production this happens in main.py lifespan, which httpx doesn't trigger.
if _registry.kernel is None:
    _services = ServiceRegistry()
    _services.register("bus", EventBus())
    _services.register("contracts", ContractRegistry())
    _registry.kernel = Kernel(
        app_registry=_registry,
        db_session_factory=None,  # type: ignore[arg-type]  # not needed for bus tests
        services=_services,
    )


@pytest.fixture(autouse=True)
def _test_defaults(monkeypatch):
    """Disable rate limiting and webhook auth for all tests.

    Individual tests can override via monkeypatch when testing these features.
    """
    monkeypatch.setattr(config, "RATE_LIMIT_RPM", 100_000)
    monkeypatch.setattr(config, "RATE_LIMIT_OPTIMIZE_RPM", 100_000)
    monkeypatch.setattr(config, "INTERNAL_WEBHOOK_SECRET", "")


@pytest.fixture()
async def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine):
    """Provide an async session bound to the in-memory database."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture()
async def client(db_engine):
    """Provide an httpx AsyncClient wired to the FastAPI app with in-memory DB."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_db_readonly():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_readonly] = override_get_db_readonly
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
