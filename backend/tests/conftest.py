"""Shared test fixtures for PromptForge backend tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import config
from app.database import Base, get_db, get_db_readonly
from app.main import app


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
