"""Tests for kernel Knowledge Base data migration (schema v3).

Verifies that ``migrate_context_to_kernel`` correctly migrates:
- projects.context_profile → kernel_knowledge_profiles (identity + metadata_json)
- workspace_links.workspace_context → auto_detected_json
- project_sources → kernel_knowledge_sources
- documentation field → Knowledge Source (type=document)
- code_snippets entries → Knowledge Sources (type=paste)
"""

import json

import pytest
from sqlalchemy import text

from apps.promptforge.database import migrate_context_to_kernel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_project(conn, *, project_id, name, description=None, context_profile=None,
                        status="active"):
    """Insert a minimal project row."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await conn.execute(
        text(
            "INSERT INTO projects (id, name, description, status, context_profile, "
            "  depth, created_at, updated_at) "
            "VALUES (:id, :name, :desc, :status, :ctx, 0, :now, :now)"
        ),
        {
            "id": project_id,
            "name": name,
            "desc": description,
            "status": status,
            "ctx": json.dumps(context_profile) if context_profile else None,
            "now": now,
        },
    )


async def _seed_workspace_link(conn, *, project_id, workspace_context):
    """Insert a workspace_links row."""
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await conn.execute(
        text(
            "INSERT INTO workspace_links (id, project_id, repo_full_name, repo_url, "
            "  default_branch, sync_status, sync_source, workspace_context, "
            "  created_at, updated_at) "
            "VALUES (:id, :pid, 'owner/repo', 'https://github.com/owner/repo', "
            "  'main', 'synced', 'claude-code', :ws_ctx, :now, :now)"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": project_id,
            "ws_ctx": json.dumps(workspace_context) if workspace_context else None,
            "now": now,
        },
    )


async def _seed_project_source(conn, *, project_id, title, content, source_type="document",
                               order_index=0, enabled=True):
    """Insert a project_sources row."""
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await conn.execute(
        text(
            "INSERT INTO project_sources "
            "(id, project_id, title, content, source_type, char_count, "
            " enabled, order_index, created_at, updated_at) "
            "VALUES (:id, :pid, :title, :content, :stype, :chars, "
            " :enabled, :order_idx, :now, :now)"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": project_id,
            "title": title,
            "content": content,
            "stype": source_type,
            "chars": len(content),
            "enabled": enabled,
            "order_idx": order_index,
            "now": now,
        },
    )


async def _get_profile(conn, entity_id):
    """Fetch a kernel profile by entity_id."""
    result = await conn.execute(
        text(
            "SELECT id, name, language, framework, description, test_framework, "
            "  metadata_json, auto_detected_json "
            "FROM kernel_knowledge_profiles "
            "WHERE app_id = 'promptforge' AND entity_id = :eid"
        ),
        {"eid": entity_id},
    )
    return result.fetchone()


async def _get_sources(conn, profile_id):
    """Fetch kernel sources for a profile, ordered by order_index."""
    result = await conn.execute(
        text(
            "SELECT title, content, source_type, char_count, enabled, order_index "
            "FROM kernel_knowledge_sources WHERE profile_id = :pid "
            "ORDER BY order_index"
        ),
        {"pid": profile_id},
    )
    return result.fetchall()


async def _clear_schema_version(conn, version):
    """Remove a schema version guard so migration re-runs."""
    await conn.execute(
        text("DELETE FROM _schema_version WHERE version = :v"),
        {"v": version},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestMigrateContextToKernel:
    """Test data fidelity of the schema v3 migration."""

    async def test_basic_profile_migration(self, db_engine):
        """Context profile identity fields migrate to kernel profile."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-1", name="My Project",
                context_profile={
                    "language": "Python",
                    "framework": "FastAPI",
                    "description": "A web API",
                    "test_framework": "pytest",
                },
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-1")
            assert row is not None
            assert row[1] == "My Project"      # name
            assert row[2] == "Python"          # language
            assert row[3] == "FastAPI"         # framework
            assert row[4] == "A web API"       # description
            assert row[5] == "pytest"          # test_framework

    async def test_metadata_json_migration(self, db_engine):
        """App-specific fields (conventions, patterns, test_patterns) go to metadata_json."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-meta", name="Meta Project",
                context_profile={
                    "conventions": ["PEP 8", "ruff"],
                    "patterns": ["repository pattern"],
                    "test_patterns": ["arrange-act-assert"],
                },
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-meta")
            assert row is not None
            metadata = json.loads(row[6])  # metadata_json
            assert metadata["conventions"] == ["PEP 8", "ruff"]
            assert metadata["patterns"] == ["repository pattern"]
            assert metadata["test_patterns"] == ["arrange-act-assert"]

    async def test_description_fallback_from_project(self, db_engine):
        """When context_profile has no description, Project.description is used."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-desc", name="Desc Project",
                description="Project-level description",
                context_profile={"language": "Go"},
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-desc")
            assert row is not None
            assert row[4] == "Project-level description"  # description

    async def test_workspace_context_migration(self, db_engine):
        """workspace_links.workspace_context migrates to auto_detected_json."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-ws", name="WS Project",
            )
            await _seed_workspace_link(
                conn, project_id="proj-ws",
                workspace_context={
                    "language": "TypeScript",
                    "framework": "SvelteKit",
                },
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-ws")
            assert row is not None
            auto = json.loads(row[7])  # auto_detected_json
            assert auto["language"] == "TypeScript"
            assert auto["framework"] == "SvelteKit"

    async def test_project_sources_migration(self, db_engine):
        """Existing project_sources rows migrate to kernel_knowledge_sources."""
        async with db_engine.begin() as conn:
            await _seed_project(conn, project_id="proj-src", name="Source Project")
            await _seed_project_source(
                conn, project_id="proj-src", title="API Docs",
                content="GET /users", source_type="api_reference", order_index=0,
            )
            await _seed_project_source(
                conn, project_id="proj-src", title="Spec",
                content="System spec content", source_type="specification",
                order_index=1, enabled=False,
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-src")
            assert row is not None
            sources = await _get_sources(conn, row[0])
            assert len(sources) == 2
            # Source 1
            assert sources[0][0] == "API Docs"       # title
            assert sources[0][1] == "GET /users"      # content
            assert sources[0][2] == "api_reference"   # source_type
            assert sources[0][3] == len("GET /users")  # char_count
            assert sources[0][4] == 1                 # enabled (True)
            assert sources[0][5] == 0                 # order_index
            # Source 2
            assert sources[1][0] == "Spec"
            assert sources[1][4] == 0                 # enabled (False)
            assert sources[1][5] == 1                 # order_index

    async def test_documentation_promoted_to_source(self, db_engine):
        """Non-empty documentation field becomes a Knowledge Source."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-doc", name="Doc Project",
                context_profile={
                    "language": "Python",
                    "documentation": "Full API reference here.",
                },
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-doc")
            assert row is not None
            sources = await _get_sources(conn, row[0])
            assert len(sources) == 1
            assert sources[0][0] == "Documentation"
            assert sources[0][1] == "Full API reference here."
            assert sources[0][2] == "document"

    async def test_code_snippets_promoted_to_sources(self, db_engine):
        """Each code_snippets entry becomes a Knowledge Source (type=paste)."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-snip", name="Snippet Project",
                context_profile={
                    "code_snippets": ["def hello(): pass", "class Foo: pass"],
                },
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-snip")
            assert row is not None
            sources = await _get_sources(conn, row[0])
            assert len(sources) == 2
            assert sources[0][0] == "Code Snippet 1"
            assert sources[0][1] == "def hello(): pass"
            assert sources[0][2] == "paste"
            assert sources[1][0] == "Code Snippet 2"
            assert sources[1][1] == "class Foo: pass"

    async def test_combined_sources_and_promoted_fields(self, db_engine):
        """Existing sources + documentation + code_snippets all migrate correctly."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-combo", name="Combo Project",
                context_profile={
                    "documentation": "Architecture overview",
                    "code_snippets": ["import os"],
                },
            )
            await _seed_project_source(
                conn, project_id="proj-combo", title="Existing Source",
                content="Existing content", order_index=0,
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-combo")
            assert row is not None
            sources = await _get_sources(conn, row[0])
            assert len(sources) == 3
            # order: existing source (0) → documentation (1) → code snippet (2)
            assert sources[0][0] == "Existing Source"
            assert sources[0][5] == 0  # order_index
            assert sources[1][0] == "Documentation"
            assert sources[1][5] == 1
            assert sources[2][0] == "Code Snippet 1"
            assert sources[2][5] == 2

    async def test_empty_documentation_skipped(self, db_engine):
        """Whitespace-only documentation field should not create a source."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-empty-doc", name="Empty Doc Project",
                context_profile={"documentation": "   "},
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-empty-doc")
            assert row is not None
            sources = await _get_sources(conn, row[0])
            assert len(sources) == 0

    async def test_deleted_projects_skipped(self, db_engine):
        """Deleted projects should not be migrated."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-del", name="Deleted",
                context_profile={"language": "Rust"}, status="deleted",
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-del")
            assert row is None


@pytest.mark.asyncio
class TestMigrationIdempotency:
    """Verify the migration is safe to run multiple times."""

    async def test_second_run_is_noop(self, db_engine):
        """Running migration twice should not duplicate profiles or sources."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-idem", name="Idempotent Project",
                context_profile={"language": "Go"},
            )
            await _seed_project_source(
                conn, project_id="proj-idem", title="Doc",
                content="Content", order_index=0,
            )
            await migrate_context_to_kernel(conn)

        # Run again — should be a no-op (schema_version=3 guard)
        async with db_engine.begin() as conn:
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM kernel_knowledge_profiles "
                    "WHERE entity_id = 'proj-idem'"
                )
            )
            assert result.scalar() == 1

            row = await _get_profile(conn, "proj-idem")
            sources = await _get_sources(conn, row[0])
            assert len(sources) == 1

    async def test_per_profile_idempotency(self, db_engine):
        """Even without schema_version guard, existing profiles are skipped."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-guard", name="Guard Project",
                context_profile={"language": "Rust"},
            )
            await migrate_context_to_kernel(conn)

        # Clear schema version and run again
        async with db_engine.begin() as conn:
            await _clear_schema_version(conn, 3)
            await _seed_project(
                conn, project_id="proj-new", name="New Project",
                context_profile={"language": "Zig"},
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            # Original profile untouched
            guard = await _get_profile(conn, "proj-guard")
            assert guard is not None
            assert guard[2] == "Rust"  # language
            # New profile created
            new = await _get_profile(conn, "proj-new")
            assert new is not None
            assert new[2] == "Zig"

    async def test_no_context_profile_creates_minimal_profile(self, db_engine):
        """Project without context_profile should still get a kernel profile."""
        async with db_engine.begin() as conn:
            await _seed_project(
                conn, project_id="proj-bare", name="Bare Project",
            )
            await migrate_context_to_kernel(conn)

        async with db_engine.begin() as conn:
            row = await _get_profile(conn, "proj-bare")
            assert row is not None
            assert row[1] == "Bare Project"  # name
            assert row[2] is None            # language
