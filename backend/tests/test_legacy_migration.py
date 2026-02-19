"""Tests for legacy project migration and ensure_project_by_name helper."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ProjectStatus
from app.database import _backfill_missing_prompts, _backfill_prompt_ids, _migrate_legacy_projects
from app.models.project import Project
from app.repositories.project import ProjectRepository, ensure_project_by_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opt(project: str, raw_prompt: str, **kwargs) -> dict:
    """Build Optimization insert params."""
    return {
        "id": str(uuid.uuid4()),
        "raw_prompt": raw_prompt,
        "status": "completed",
        "project": project,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }


# ---------------------------------------------------------------------------
# ensure_project_by_name
# ---------------------------------------------------------------------------

class TestEnsureProjectByName:

    @pytest.mark.asyncio
    async def test_returns_none_for_empty(self, db_session: AsyncSession):
        assert await ensure_project_by_name(db_session, "") is None
        assert await ensure_project_by_name(db_session, "   ") is None

    @pytest.mark.asyncio
    async def test_creates_new_project(self, db_session: AsyncSession):
        pid = await ensure_project_by_name(db_session, "my-project")
        await db_session.commit()

        assert pid is not None
        repo = ProjectRepository(db_session)
        project = await repo.get_by_name("my-project")
        assert project is not None
        assert project.id == pid
        assert project.status == "active"

    @pytest.mark.asyncio
    async def test_returns_existing_project(self, db_session: AsyncSession):
        # Create first
        pid1 = await ensure_project_by_name(db_session, "existing")
        await db_session.flush()

        # Should return same ID
        pid2 = await ensure_project_by_name(db_session, "existing")
        assert pid1 == pid2

    @pytest.mark.asyncio
    async def test_strips_whitespace(self, db_session: AsyncSession):
        pid1 = await ensure_project_by_name(db_session, "  spaced  ")
        await db_session.flush()

        pid2 = await ensure_project_by_name(db_session, "spaced")
        assert pid1 == pid2

    @pytest.mark.asyncio
    async def test_reactivates_deleted_project(self, db_session: AsyncSession):
        # Create and soft-delete
        project = Project(name="deleted-proj", status=ProjectStatus.DELETED)
        db_session.add(project)
        await db_session.flush()

        # Should reactivate the deleted project (name is UNIQUE)
        pid = await ensure_project_by_name(db_session, "deleted-proj")
        assert pid == project.id

        repo = ProjectRepository(db_session)
        reloaded = await repo.get_by_name("deleted-proj")
        assert reloaded is not None
        assert reloaded.status == ProjectStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_reuses_archived_project(self, db_session: AsyncSession):
        project = Project(name="archived-proj", status=ProjectStatus.ARCHIVED)
        db_session.add(project)
        await db_session.flush()

        pid = await ensure_project_by_name(db_session, "archived-proj")
        assert pid == project.id


# ---------------------------------------------------------------------------
# _migrate_legacy_projects
# ---------------------------------------------------------------------------

class TestMigrateLegacyProjects:

    @pytest.mark.asyncio
    async def test_no_op_when_no_legacy_data(self, db_engine):
        """Migration does nothing if optimizations table has no project strings."""
        async with db_engine.begin() as conn:
            await _migrate_legacy_projects(conn)

        # No projects created
        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM projects"))
            assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_creates_projects_from_legacy(self, db_engine):
        """Migration creates Project records from distinct optimization.project values."""
        # Seed legacy optimizations
        async with db_engine.begin() as conn:
            for params in [
                _opt("alpha", "prompt 1"),
                _opt("alpha", "prompt 2"),
                _opt("beta", "prompt 3"),
            ]:
                cols = ", ".join(params.keys())
                vals = ", ".join(f":{k}" for k in params)
                await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)

        # Run migration
        async with db_engine.begin() as conn:
            await _migrate_legacy_projects(conn)

        # Verify 2 projects created
        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM projects ORDER BY name"))
            names = [row[0] for row in result.fetchall()]
            assert names == ["alpha", "beta"]

    @pytest.mark.asyncio
    async def test_imports_unique_prompts(self, db_engine):
        """Migration imports deduplicated raw_prompts as Prompt entries."""
        async with db_engine.begin() as conn:
            for params in [
                _opt("proj", "unique prompt A"),
                _opt("proj", "unique prompt B"),
                _opt("proj", "unique prompt A"),  # duplicate
            ]:
                cols = ", ".join(params.keys())
                vals = ", ".join(f":{k}" for k in params)
                await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)

        async with db_engine.begin() as conn:
            await _migrate_legacy_projects(conn)

        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT content FROM prompts ORDER BY order_index"))
            contents = [row[0] for row in result.fetchall()]
            assert len(contents) == 2
            assert "unique prompt A" in contents
            assert "unique prompt B" in contents

    @pytest.mark.asyncio
    async def test_idempotent(self, db_engine):
        """Running migration twice doesn't create duplicate projects."""
        async with db_engine.begin() as conn:
            params = _opt("idempotent", "a prompt")
            cols = ", ".join(params.keys())
            vals = ", ".join(f":{k}" for k in params)
            await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)

        # Run twice
        async with db_engine.begin() as conn:
            await _migrate_legacy_projects(conn)
        async with db_engine.begin() as conn:
            await _migrate_legacy_projects(conn)

        # Still only 1 project
        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM projects"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_skips_null_and_empty_projects(self, db_engine):
        """Migration ignores NULL and empty-string project values."""
        async with db_engine.begin() as conn:
            for params in [
                _opt("real", "prompt"),
                {**_opt("", "prompt2"), "project": ""},
            ]:
                cols = ", ".join(params.keys())
                vals = ", ".join(f":{k}" for k in params)
                await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)

            # Also insert one with NULL project
            null_params = {
                "id": str(uuid.uuid4()),
                "raw_prompt": "null proj",
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await conn.execute(
                text(
                    "INSERT INTO optimizations (id, raw_prompt, status, created_at)"
                    " VALUES (:id, :raw_prompt, :status, :created_at)"
                ),
                null_params,
            )

        async with db_engine.begin() as conn:
            await _migrate_legacy_projects(conn)

        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM projects"))
            names = [row[0] for row in result.fetchall()]
            assert names == ["real"]


# ---------------------------------------------------------------------------
# _backfill_missing_prompts
# ---------------------------------------------------------------------------

class TestBackfillMissingPrompts:

    @pytest.mark.asyncio
    async def test_creates_prompt_for_orphaned_optimization(self, db_engine):
        """Backfill creates a Prompt when an optimization has no matching prompt."""
        async with db_engine.begin() as conn:
            # First, create project + initial prompts via legacy migration
            params = _opt("proj", "prompt A")
            cols = ", ".join(params.keys())
            vals = ", ".join(f":{k}" for k in params)
            await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)
            await _migrate_legacy_projects(conn)

            # Now add a second optimization with different content (simulates
            # an optimization added after the initial migration)
            params2 = _opt("proj", "prompt B (orphaned)")
            cols2 = ", ".join(params2.keys())
            vals2 = ", ".join(f":{k}" for k in params2)
            await conn.execute(text(f"INSERT INTO optimizations ({cols2}) VALUES ({vals2})"), params2)

        # Run backfill
        async with db_engine.begin() as conn:
            await _backfill_missing_prompts(conn)

        # Verify: 2 prompts now exist
        async with db_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT content FROM prompts ORDER BY order_index")
            )
            contents = [row[0] for row in result.fetchall()]
            assert len(contents) == 2
            assert "prompt A" in contents
            assert "prompt B (orphaned)" in contents

    @pytest.mark.asyncio
    async def test_backfill_links_optimization_after_rerun(self, db_engine):
        """After backfill creates prompts, a second backfill_prompt_ids links them."""
        async with db_engine.begin() as conn:
            params = _opt("proj", "original")
            cols = ", ".join(params.keys())
            vals = ", ".join(f":{k}" for k in params)
            await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)
            await _migrate_legacy_projects(conn)
            await _backfill_prompt_ids(conn)

            # Add orphaned optimization
            orphan = _opt("proj", "orphaned content")
            cols2 = ", ".join(orphan.keys())
            vals2 = ", ".join(f":{k}" for k in orphan)
            await conn.execute(text(f"INSERT INTO optimizations ({cols2}) VALUES ({vals2})"), orphan)

        # Run backfill_missing_prompts + backfill_prompt_ids
        async with db_engine.begin() as conn:
            await _backfill_missing_prompts(conn)
            await _backfill_prompt_ids(conn)

        # Verify: orphaned optimization now has prompt_id set
        async with db_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT prompt_id FROM optimizations WHERE raw_prompt = 'orphaned content'")
            )
            prompt_id = result.scalar()
            assert prompt_id is not None

    @pytest.mark.asyncio
    async def test_idempotent(self, db_engine):
        """Running backfill twice doesn't create duplicate prompts."""
        async with db_engine.begin() as conn:
            params = _opt("proj", "only-prompt")
            cols = ", ".join(params.keys())
            vals = ", ".join(f":{k}" for k in params)
            await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)
            await _migrate_legacy_projects(conn)

            # Add orphan
            orphan = _opt("proj", "orphan-once")
            cols2 = ", ".join(orphan.keys())
            vals2 = ", ".join(f":{k}" for k in orphan)
            await conn.execute(text(f"INSERT INTO optimizations ({cols2}) VALUES ({vals2})"), orphan)

        # Run twice
        async with db_engine.begin() as conn:
            await _backfill_missing_prompts(conn)
        async with db_engine.begin() as conn:
            await _backfill_missing_prompts(conn)

        # Still only 2 prompts total
        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM prompts"))
            assert result.scalar() == 2

    @pytest.mark.asyncio
    async def test_skips_deleted_projects(self, db_engine):
        """Backfill doesn't create prompts for deleted projects."""
        async with db_engine.begin() as conn:
            # Create a project manually as deleted
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                text(
                    "INSERT INTO projects (id, name, status, created_at, updated_at) "
                    "VALUES (:id, :name, 'deleted', :now, :now)"
                ),
                {"id": "del-proj", "name": "deleted-proj", "now": now},
            )
            # Add optimization pointing to deleted project
            params = _opt("deleted-proj", "should-not-create")
            cols = ", ".join(params.keys())
            vals = ", ".join(f":{k}" for k in params)
            await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)

        async with db_engine.begin() as conn:
            await _backfill_missing_prompts(conn)

        # No prompts created
        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM prompts"))
            assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_skips_linked_optimizations(self, db_engine):
        """Backfill should not create prompts for optimizations that already
        have prompt_id set (even if raw_prompt differs from prompt content)."""
        async with db_engine.begin() as conn:
            # Set up project + prompt with edited content
            params = _opt("proj", "original content")
            cols = ", ".join(params.keys())
            vals = ", ".join(f":{k}" for k in params)
            await conn.execute(text(f"INSERT INTO optimizations ({cols}) VALUES ({vals})"), params)
            await _migrate_legacy_projects(conn)
            await _backfill_prompt_ids(conn)

            # Simulate editing the prompt content (diverges from raw_prompt)
            await conn.execute(
                text("UPDATE prompts SET content = 'edited content' WHERE content = 'original content'")
            )

        # Now raw_prompt='original content' doesn't match any prompt content,
        # but the optimization has prompt_id set — backfill should skip it
        async with db_engine.begin() as conn:
            await _backfill_missing_prompts(conn)

        # Should NOT create a new prompt for the old raw_prompt
        async with db_engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM prompts"))
            assert result.scalar() == 1
            result2 = await conn.execute(text("SELECT content FROM prompts"))
            assert result2.scalar() == "edited content"


# ---------------------------------------------------------------------------
# Auto-create via optimize endpoint
# ---------------------------------------------------------------------------

class TestOptimizeAutoCreatesProject:

    @pytest.mark.asyncio
    async def test_optimize_with_project_creates_record(self, client):
        """POST /api/optimize with a project name auto-creates a Project record."""
        response = await client.post(
            "/api/optimize",
            json={"prompt": "Test prompt for auto-create", "project": "new-auto-project"},
        )
        # SSE endpoint returns 200
        assert response.status_code == 200

        # Verify project was created
        resp = await client.get("/api/projects", params={"search": "new-auto-project"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(p["name"] == "new-auto-project" for p in data["items"])

    @pytest.mark.asyncio
    async def test_optimize_without_project_no_creation(self, client):
        """POST /api/optimize without project name doesn't create any project."""
        resp_before = await client.get("/api/projects")
        count_before = resp_before.json()["total"]

        await client.post(
            "/api/optimize",
            json={"prompt": "Test prompt no project"},
        )

        resp_after = await client.get("/api/projects")
        assert resp_after.json()["total"] == count_before
