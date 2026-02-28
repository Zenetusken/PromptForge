"""Database setup with SQLAlchemy async engine and session management."""

import logging
import os
from pathlib import Path

from sqlalchemy import event
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


# Enable SQLite foreign keys and performance PRAGMAs on every connection.
# WAL mode eliminates reader/writer blocking during SSE streaming.
# synchronous=NORMAL is safe with WAL. Cache/mmap reduce syscalls.
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA cache_size = -65536")  # 64 MB
    cursor.execute("PRAGMA mmap_size = 67108864")  # 64 MB
    cursor.execute("PRAGMA temp_store = MEMORY")
    cursor.execute("PRAGMA busy_timeout = 5000")  # 5s retry on lock contention
    cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _harden_data_dir() -> None:
    """Set restrictive permissions on the data directory and database file.

    data/ → 0o700 (owner-only access)
    data/promptforge.db → 0o600 (owner-only read/write)
    """
    # Extract path from SQLAlchemy URL (sqlite+aiosqlite:///path/to/db)
    if ":///" in DATABASE_URL:
        db_path_str = DATABASE_URL.split(":///", 1)[1]
        db_path = Path(db_path_str)
        data_dir = db_path.parent
        try:
            if data_dir.is_dir():
                os.chmod(data_dir, 0o700)
            if db_path.is_file():
                os.chmod(db_path, 0o600)
        except OSError as exc:
            logger.warning("Could not set data directory permissions: %s", exc)


async def init_db(app_registry=None) -> None:
    """Create all tables and apply pending migrations.

    Args:
        app_registry: Optional AppRegistry instance. If provided, calls
            ``run_migrations()`` on each enabled app after kernel migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Kernel-owned tables first (app_settings, app_collections, app_documents)
        from kernel.database import run_kernel_migrations
        await run_kernel_migrations(conn)

        # Run per-app migrations after kernel migrations
        if app_registry is not None:
            for rec in app_registry.list_enabled():
                try:
                    await rec.instance.run_migrations(conn)
                    logger.info("App %r migrations completed", rec.manifest.id)
                except Exception as exc:
                    logger.error("App %r migrations failed: %s", rec.manifest.id, exc)

    _harden_data_dir()


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


async def get_db_readonly() -> AsyncSession:
    """Lightweight read-only session dependency for GET/HEAD endpoints.

    Skips the commit() call since no writes occur, avoiding an unnecessary
    flush of the session identity map on every read request.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
