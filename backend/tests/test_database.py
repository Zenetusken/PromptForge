"""Tests for database initialization, migrations, and stale record cleanup."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.constants import OptimizationStatus
from app.database import Base, _backfill_prompt_ids, _cleanup_stale_running, _run_migrations
from app.models.optimization import Optimization
from app.models.project import Project, Prompt


@pytest.fixture()
async def fresh_engine():
    """Create a fresh in-memory SQLite engine with tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


class TestRunMigrations:
    @pytest.mark.asyncio
    async def test_migrations_idempotent(self, fresh_engine):
        """Running migrations twice should not raise errors."""
        async with fresh_engine.begin() as conn:
            await _run_migrations(conn)
        # Second run — all should be silently skipped
        async with fresh_engine.begin() as conn:
            await _run_migrations(conn)


class TestCleanupStaleRunning:
    @pytest.mark.asyncio
    async def test_marks_old_running_as_error(self, fresh_engine):
        """Records running for >30 minutes should be marked as error."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        factory = async_sessionmaker(
            fresh_engine, class_=AsyncSession, expire_on_commit=False,
        )
        async with factory() as session:
            session.add(Optimization(
                id="stale-001", raw_prompt="test",
                status=OptimizationStatus.RUNNING, created_at=old_time,
            ))
            await session.commit()

        async with fresh_engine.begin() as conn:
            await _cleanup_stale_running(conn)

        async with factory() as session:
            row = (await session.execute(
                text("SELECT status, error_message FROM optimizations WHERE id = 'stale-001'")
            )).one()
            assert row.status == "error"
            assert row.error_message == "Server interrupted"

    @pytest.mark.asyncio
    async def test_recent_running_not_cleaned(self, fresh_engine):
        """Records running for <30 minutes should be left alone."""
        factory = async_sessionmaker(
            fresh_engine, class_=AsyncSession, expire_on_commit=False,
        )
        async with factory() as session:
            session.add(Optimization(
                id="fresh-001", raw_prompt="test",
                status=OptimizationStatus.RUNNING,
                created_at=datetime.now(timezone.utc),
            ))
            await session.commit()

        async with fresh_engine.begin() as conn:
            await _cleanup_stale_running(conn)

        async with factory() as session:
            row = (await session.execute(
                text("SELECT status FROM optimizations WHERE id = 'fresh-001'")
            )).one()
            assert row.status == "running"

    @pytest.mark.asyncio
    async def test_completed_records_not_affected(self, fresh_engine):
        """Only RUNNING records should be cleaned up."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        factory = async_sessionmaker(
            fresh_engine, class_=AsyncSession, expire_on_commit=False,
        )
        async with factory() as session:
            session.add(Optimization(
                id="done-001", raw_prompt="test",
                status=OptimizationStatus.COMPLETED, created_at=old_time,
            ))
            await session.commit()

        async with fresh_engine.begin() as conn:
            await _cleanup_stale_running(conn)

        async with factory() as session:
            row = (await session.execute(
                text("SELECT status FROM optimizations WHERE id = 'done-001'")
            )).one()
            assert row.status == "completed"


class TestBackfillPromptIds:
    @pytest.mark.asyncio
    async def test_links_matching_optimizations(self, fresh_engine):
        """Backfill should set prompt_id where raw_prompt matches prompt content."""
        factory = async_sessionmaker(
            fresh_engine, class_=AsyncSession, expire_on_commit=False,
        )
        async with factory() as session:
            proj = Project(id="proj-1", name="myproj")
            session.add(proj)
            prompt = Prompt(
                id="prompt-1", content="optimize me", project_id="proj-1",
            )
            session.add(prompt)
            session.add(Optimization(
                id="opt-1", raw_prompt="optimize me",
                project="myproj", status=OptimizationStatus.COMPLETED,
            ))
            await session.commit()

        async with fresh_engine.begin() as conn:
            await _backfill_prompt_ids(conn)

        async with factory() as session:
            row = (await session.execute(
                text("SELECT prompt_id FROM optimizations WHERE id = 'opt-1'")
            )).one()
            assert row.prompt_id == "prompt-1"

    @pytest.mark.asyncio
    async def test_idempotent(self, fresh_engine):
        """Running backfill twice should not change already-linked records."""
        factory = async_sessionmaker(
            fresh_engine, class_=AsyncSession, expire_on_commit=False,
        )
        async with factory() as session:
            proj = Project(id="proj-2", name="proj2")
            session.add(proj)
            prompt = Prompt(
                id="prompt-2", content="already linked", project_id="proj-2",
            )
            session.add(prompt)
            session.add(Optimization(
                id="opt-2", raw_prompt="already linked",
                project="proj2", status=OptimizationStatus.COMPLETED,
                prompt_id="prompt-2",
            ))
            await session.commit()

        async with fresh_engine.begin() as conn:
            await _backfill_prompt_ids(conn)

        async with factory() as session:
            row = (await session.execute(
                text("SELECT prompt_id FROM optimizations WHERE id = 'opt-2'")
            )).one()
            assert row.prompt_id == "prompt-2"

    @pytest.mark.asyncio
    async def test_no_match_left_null(self, fresh_engine):
        """Optimizations without matching prompts keep prompt_id NULL."""
        factory = async_sessionmaker(
            fresh_engine, class_=AsyncSession, expire_on_commit=False,
        )
        async with factory() as session:
            session.add(Optimization(
                id="opt-orphan", raw_prompt="no matching prompt",
                project="unknown", status=OptimizationStatus.COMPLETED,
            ))
            await session.commit()

        async with fresh_engine.begin() as conn:
            await _backfill_prompt_ids(conn)

        async with factory() as session:
            row = (await session.execute(
                text("SELECT prompt_id FROM optimizations WHERE id = 'opt-orphan'")
            )).one()
            assert row.prompt_id is None

    @pytest.mark.asyncio
    async def test_skips_null_project(self, fresh_engine):
        """Optimizations without a project name are not touched."""
        factory = async_sessionmaker(
            fresh_engine, class_=AsyncSession, expire_on_commit=False,
        )
        async with factory() as session:
            proj = Project(id="proj-3", name="proj3")
            session.add(proj)
            session.add(Prompt(
                id="prompt-3", content="some content", project_id="proj-3",
            ))
            session.add(Optimization(
                id="opt-noproject", raw_prompt="some content",
                project=None, status=OptimizationStatus.COMPLETED,
            ))
            await session.commit()

        async with fresh_engine.begin() as conn:
            await _backfill_prompt_ids(conn)

        async with factory() as session:
            row = (await session.execute(
                text("SELECT prompt_id FROM optimizations WHERE id = 'opt-noproject'")
            )).one()
            assert row.prompt_id is None
