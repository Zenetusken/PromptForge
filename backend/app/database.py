"""Database setup with SQLAlchemy async engine and session management."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import event, text
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


# Enable SQLite foreign key enforcement on every connection.
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


_MIGRATIONS: list[str] = [
    # Column additions for databases created before the column existed.
    "ALTER TABLE optimizations ADD COLUMN strategy_reasoning TEXT",
    "ALTER TABLE optimizations ADD COLUMN input_tokens INTEGER",
    "ALTER TABLE optimizations ADD COLUMN output_tokens INTEGER",
    "ALTER TABLE optimizations ADD COLUMN strategy_confidence REAL",
    # Indexes for databases created before the model defined them in
    # __table_args__. New databases get these at CREATE TABLE time;
    # IF NOT EXISTS makes them no-ops in that case.
    "CREATE INDEX IF NOT EXISTS ix_optimizations_status"
    " ON optimizations (status)",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_overall_score"
    " ON optimizations (overall_score)",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_status_created_at"
    " ON optimizations (status, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_task_type_project"
    " ON optimizations (task_type, project)",
    # --- Projects & Prompts tables ---
    "CREATE TABLE IF NOT EXISTS projects ("
    "  id TEXT PRIMARY KEY,"
    "  name TEXT NOT NULL UNIQUE,"
    "  description TEXT,"
    "  status TEXT NOT NULL DEFAULT 'active',"
    "  created_at TIMESTAMP NOT NULL,"
    "  updated_at TIMESTAMP NOT NULL"
    ")",
    "CREATE TABLE IF NOT EXISTS prompts ("
    "  id TEXT PRIMARY KEY,"
    "  content TEXT NOT NULL,"
    "  version INTEGER NOT NULL DEFAULT 1,"
    "  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,"
    "  order_index INTEGER NOT NULL DEFAULT 0,"
    "  created_at TIMESTAMP NOT NULL,"
    "  updated_at TIMESTAMP NOT NULL"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_projects_status ON projects (status)",
    "CREATE INDEX IF NOT EXISTS ix_projects_created_at ON projects (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_projects_updated_at ON projects (updated_at)",
    "CREATE INDEX IF NOT EXISTS ix_prompts_project_id ON prompts (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_prompts_order_index ON prompts (project_id, order_index)",
    # --- Prompt version history ---
    "CREATE TABLE IF NOT EXISTS prompt_versions ("
    "  id TEXT PRIMARY KEY,"
    "  prompt_id TEXT NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,"
    "  version INTEGER NOT NULL,"
    "  content TEXT NOT NULL,"
    "  optimization_id TEXT REFERENCES optimizations(id) ON DELETE SET NULL,"
    "  created_at TIMESTAMP NOT NULL"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_prompt_versions_prompt_id"
    " ON prompt_versions (prompt_id)",
    "CREATE INDEX IF NOT EXISTS ix_prompt_versions_prompt_version"
    " ON prompt_versions (prompt_id, version)",
    # --- Forge result linking ---
    "ALTER TABLE optimizations ADD COLUMN prompt_id TEXT REFERENCES prompts(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS ix_optimizations_prompt_id ON optimizations (prompt_id)",
    # --- Strategy column (audit fix #3) ---
    "ALTER TABLE optimizations ADD COLUMN strategy TEXT",
    # --- Secondary frameworks for multi-framework combinations ---
    "ALTER TABLE optimizations ADD COLUMN secondary_frameworks TEXT",
]


async def _run_migrations(conn) -> None:
    """Apply column-add and index migrations, skipping any that already exist."""
    for stmt in _MIGRATIONS:
        try:
            await conn.execute(text(stmt))
            logger.info("Migration applied: %s", stmt[:60])
        except OperationalError:
            logger.debug("Migration skipped (already applied): %s", stmt[:60])


async def _migrate_legacy_projects(conn) -> None:
    """Seed the projects table from legacy optimization.project string values.

    For each distinct project name in the optimizations table that doesn't
    already have a matching projects record, creates a Project and imports
    unique raw_prompt values as Prompt entries.

    Idempotent: safe to run on every startup.
    """
    # Find project names that don't already have a matching projects record
    result = await conn.execute(
        text(
            "SELECT DISTINCT o.project FROM optimizations o "
            "WHERE o.project IS NOT NULL AND o.project != '' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM projects p WHERE p.name = o.project AND p.status != 'deleted'"
            ")"
        )
    )
    project_names = [row[0] for row in result.fetchall()]

    if not project_names:
        return

    logger.info("Migrating %d legacy project(s): %s", len(project_names), project_names)
    now = datetime.now(timezone.utc)

    for name in project_names:
        project_id = str(uuid.uuid4())

        # Use earliest optimization date as project created_at
        earliest_result = await conn.execute(
            text("SELECT MIN(created_at) FROM optimizations WHERE project = :name"),
            {"name": name},
        )
        earliest_date = earliest_result.scalar() or now

        await conn.execute(
            text(
                "INSERT INTO projects (id, name, description, status, created_at, updated_at) "
                "VALUES (:id, :name, :desc, 'active', :created, :updated)"
            ),
            {
                "id": project_id,
                "name": name,
                "desc": "Migrated from optimization history",
                "created": earliest_date,
                "updated": now,
            },
        )

        # Import unique raw_prompts as Prompt entries, ordered by first use
        prompts_result = await conn.execute(
            text(
                "SELECT raw_prompt, MIN(created_at) AS first_used "
                "FROM optimizations "
                "WHERE project = :name AND raw_prompt IS NOT NULL AND raw_prompt != '' "
                "GROUP BY raw_prompt "
                "ORDER BY first_used"
            ),
            {"name": name},
        )
        prompt_rows = prompts_result.fetchall()

        for idx, (content, _first_used) in enumerate(prompt_rows):
            await conn.execute(
                text(
                    "INSERT INTO prompts "
                    "(id, content, version, project_id, order_index, created_at, updated_at) "
                    "VALUES (:id, :content, 1, :project_id, :order_index, :created, :updated)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "content": content,
                    "project_id": project_id,
                    "order_index": idx,
                    "created": now,
                    "updated": now,
                },
            )

        logger.info(
            "Migrated project %r: created with %d prompt(s)", name, len(prompt_rows),
        )


async def _backfill_prompt_ids(conn) -> None:
    """Link existing optimizations to project prompts by matching content.

    For each optimization with no prompt_id, find a prompt whose content
    matches ``raw_prompt`` within the same project name, then set the FK.
    Idempotent: only touches rows where prompt_id IS NULL.
    """
    result = await conn.execute(
        text(
            "UPDATE optimizations SET prompt_id = ("
            "  SELECT p.id FROM prompts p"
            "  JOIN projects pj ON p.project_id = pj.id"
            "  WHERE pj.name = optimizations.project"
            "  AND p.content = optimizations.raw_prompt"
            "  LIMIT 1"
            ") WHERE prompt_id IS NULL"
            " AND project IS NOT NULL AND project != ''"
            " AND EXISTS ("
            "  SELECT 1 FROM prompts p2"
            "  JOIN projects pj2 ON p2.project_id = pj2.id"
            "  WHERE pj2.name = optimizations.project"
            "  AND p2.content = optimizations.raw_prompt"
            ")"
        )
    )
    if result.rowcount:
        logger.info("Backfilled prompt_id on %d optimization(s)", result.rowcount)


async def _backfill_missing_prompts(conn) -> None:
    """Create Prompt records for optimizations whose raw_prompt has no match.

    Covers the gap where an optimization was added to an existing project
    (e.g. before auto-linking was implemented, or via direct DB insert)
    and no Prompt record was ever created for its content.

    Idempotent: only creates prompts for content not already present.
    """
    # Find distinct (project_id, raw_prompt) pairs that have no matching
    # Prompt record in the corresponding project.
    result = await conn.execute(
        text(
            "SELECT DISTINCT p.id, o.raw_prompt "
            "FROM optimizations o "
            "JOIN projects p ON p.name = o.project AND p.status != 'deleted' "
            "WHERE o.project IS NOT NULL AND o.project != '' "
            "AND o.raw_prompt IS NOT NULL AND o.raw_prompt != '' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM prompts pr "
            "  WHERE pr.project_id = p.id AND pr.content = o.raw_prompt"
            ")"
        )
    )
    orphans = result.fetchall()

    if not orphans:
        return

    now = datetime.now(timezone.utc)
    created = 0

    for project_id, raw_prompt in orphans:
        # Determine next order_index
        max_result = await conn.execute(
            text("SELECT MAX(order_index) FROM prompts WHERE project_id = :pid"),
            {"pid": project_id},
        )
        max_order = max_result.scalar()
        next_order = 0 if max_order is None else max_order + 1

        prompt_id = str(uuid.uuid4())
        await conn.execute(
            text(
                "INSERT INTO prompts "
                "(id, content, version, project_id, order_index, created_at, updated_at) "
                "VALUES (:id, :content, 1, :project_id, :order_index, :created, :updated)"
            ),
            {
                "id": prompt_id,
                "content": raw_prompt,
                "project_id": project_id,
                "order_index": next_order,
                "created": now,
                "updated": now,
            },
        )
        created += 1

    logger.info("Backfilled %d missing prompt record(s)", created)


async def _cleanup_stale_running(conn) -> None:
    """Mark orphaned RUNNING records older than 30 minutes as ERROR."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    result = await conn.execute(
        text(
            "UPDATE optimizations SET status = 'error', error_message = 'Server interrupted'"
            " WHERE status = 'running' AND created_at < :cutoff"
        ),
        {"cutoff": cutoff},
    )
    if result.rowcount:
        logger.info("Cleaned up %d stale RUNNING records", result.rowcount)


async def init_db() -> None:
    """Create all tables and apply pending migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)
        await _migrate_legacy_projects(conn)
        await _backfill_prompt_ids(conn)
        await _backfill_missing_prompts(conn)
        # Re-run backfill to link newly created prompts
        await _backfill_prompt_ids(conn)
        await _cleanup_stale_running(conn)


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
