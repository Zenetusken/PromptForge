"""Database setup with SQLAlchemy async engine and session management."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


_MIGRATIONS: list[str] = [
    "ALTER TABLE optimizations ADD COLUMN strategy_reasoning TEXT",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_status ON optimizations (status)",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_overall_score ON optimizations (overall_score)",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_status_created_at"
    " ON optimizations (status, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_task_type_project"
    " ON optimizations (task_type, project)",
]


async def _run_migrations(conn) -> None:
    """Apply column-add and index migrations, skipping any that already exist."""
    for stmt in _MIGRATIONS:
        try:
            await conn.execute(text(stmt))
            logger.info("Migration applied: %s", stmt[:60])
        except OperationalError:
            logger.debug("Migration skipped (already applied): %s", stmt[:60])


async def init_db() -> None:
    """Create all tables and apply pending migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)


async def get_db() -> AsyncSession:
    """Dependency that provides an async database session.

    Yields an AsyncSession and ensures it is closed after use.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
