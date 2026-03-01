"""Tests for three-tier context resolution: schema utilities, merge, and repository."""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.models.project import Project
from apps.promptforge.repositories.project import ProjectRepository
from apps.promptforge.schemas.context import (
    MAX_CONTEXT_CHARS,
    CodebaseContext,
    codebase_context_from_dict,
    context_from_json,
    context_to_dict,
    merge_contexts,
)

# ---------------------------------------------------------------------------
# Bug 1: codebase_context_from_dict crashes on non-dict input
# ---------------------------------------------------------------------------


class TestFromDictNonDictInput:
    def test_list_returns_none(self):
        assert codebase_context_from_dict([1, 2, 3]) is None

    def test_int_returns_none(self):
        assert codebase_context_from_dict(42) is None

    def test_string_returns_none(self):
        assert codebase_context_from_dict("hello") is None

    def test_tuple_returns_none(self):
        assert codebase_context_from_dict((1, 2)) is None

    def test_true_returns_none(self):
        assert codebase_context_from_dict(True) is None

    def test_none_returns_none(self):
        assert codebase_context_from_dict(None) is None

    def test_empty_dict_returns_none(self):
        assert codebase_context_from_dict({}) is None


class TestFromJsonArray:
    def test_json_array_returns_none(self):
        assert context_from_json("[1, 2, 3]") is None

    def test_json_string_returns_none(self):
        assert context_from_json('"just a string"') is None

    def test_json_number_returns_none(self):
        assert context_from_json("42") is None


# ---------------------------------------------------------------------------
# Bug 5: codebase_context_from_dict doesn't validate field types
# ---------------------------------------------------------------------------


class TestFromDictCoercesScalarTypes:
    def test_int_language_becomes_str(self):
        ctx = codebase_context_from_dict({"language": 42})
        assert ctx is not None
        assert ctx.language == "42"
        assert isinstance(ctx.language, str)

    def test_int_framework_becomes_str(self):
        ctx = codebase_context_from_dict({"framework": 3})
        assert ctx is not None
        assert ctx.framework == "3"

    def test_bool_description_becomes_str(self):
        ctx = codebase_context_from_dict({"description": True})
        assert ctx is not None
        assert ctx.description == "True"

    def test_none_scalar_preserved(self):
        ctx = codebase_context_from_dict({"language": None, "framework": "svelte"})
        assert ctx is not None
        assert ctx.language is None
        assert ctx.framework == "svelte"


class TestFromDictCoercesListTypes:
    def test_string_conventions_becomes_list(self):
        ctx = codebase_context_from_dict({"conventions": "use ruff"})
        assert ctx is not None
        assert ctx.conventions == ["use ruff"]

    def test_list_items_coerced_to_str(self):
        ctx = codebase_context_from_dict({"conventions": [1, 2, 3]})
        assert ctx is not None
        assert ctx.conventions == ["1", "2", "3"]

    def test_none_items_filtered_from_list(self):
        ctx = codebase_context_from_dict({"patterns": ["mvc", None, "rest"]})
        assert ctx is not None
        assert ctx.patterns == ["mvc", "rest"]

    def test_dict_conventions_dropped(self):
        ctx = codebase_context_from_dict({
            "language": "python",
            "conventions": {"a": 1},
        })
        assert ctx is not None
        assert ctx.language == "python"
        assert ctx.conventions == []  # default_factory=list

    def test_int_list_field_dropped(self):
        ctx = codebase_context_from_dict({
            "language": "go",
            "patterns": 42,
        })
        assert ctx is not None
        assert ctx.patterns == []  # default_factory=list


# ---------------------------------------------------------------------------
# Merge contexts
# ---------------------------------------------------------------------------


class TestMergeContexts:
    def test_both_none(self):
        assert merge_contexts(None, None) is None

    def test_base_only_returns_copy(self):
        """merge_contexts(base, None) returns a shallow copy, not the original."""
        base = CodebaseContext(language="python")
        result = merge_contexts(base, None)
        assert result is not base
        assert result.language == "python"

    def test_override_only_returns_copy(self):
        """merge_contexts(None, override) returns a shallow copy, not the original."""
        override = CodebaseContext(language="go")
        result = merge_contexts(None, override)
        assert result is not override
        assert result.language == "go"

    def test_base_only_mutation_safe(self):
        """Mutating the merged result must not affect the original base."""
        base = CodebaseContext(language="python")
        result = merge_contexts(base, None)
        result.language = "MUTATED"
        assert base.language == "python"

    def test_override_only_mutation_safe(self):
        """Mutating the merged result must not affect the original override."""
        override = CodebaseContext(language="go")
        result = merge_contexts(None, override)
        result.language = "MUTATED"
        assert override.language == "go"

    def test_override_replaces_scalar(self):
        base = CodebaseContext(language="python", framework="fastapi")
        override = CodebaseContext(language="go")
        result = merge_contexts(base, override)
        assert result is not None
        assert result.language == "go"
        assert result.framework == "fastapi"  # preserved from base

    def test_override_replaces_list(self):
        base = CodebaseContext(conventions=["pep8", "ruff"])
        override = CodebaseContext(conventions=["gofmt"])
        result = merge_contexts(base, override)
        assert result is not None
        assert result.conventions == ["gofmt"]

    def test_empty_override_list_keeps_base(self):
        base = CodebaseContext(conventions=["pep8"])
        override = CodebaseContext(conventions=[])
        result = merge_contexts(base, override)
        assert result is not None
        assert result.conventions == ["pep8"]


# ---------------------------------------------------------------------------
# context_to_dict
# ---------------------------------------------------------------------------


class TestContextToDict:
    def test_filters_empty_fields(self):
        ctx = CodebaseContext(language="python")
        d = context_to_dict(ctx)
        assert d == {"language": "python"}

    def test_none_returns_none(self):
        assert context_to_dict(None) is None

    def test_all_empty_returns_none(self):
        ctx = CodebaseContext()
        assert context_to_dict(ctx) is None


# ---------------------------------------------------------------------------
# Render truncation
# ---------------------------------------------------------------------------


class TestRender:
    def test_truncates_at_max_chars(self):
        long_desc = "A" * (MAX_CONTEXT_CHARS + 100)
        ctx = CodebaseContext(description=long_desc)
        rendered = ctx.render()
        assert rendered is not None
        assert len(rendered) <= MAX_CONTEXT_CHARS + 50  # room for "... (truncated)"
        assert rendered.endswith("... (truncated)")

    def test_empty_context_renders_none(self):
        ctx = CodebaseContext()
        assert ctx.render() is None


# ---------------------------------------------------------------------------
# Bug 4: get_context_by_name excludes nested projects (integration tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNestedProjectContextResolution:
    async def test_nested_project_context_resolved(self, db_session: AsyncSession):
        """A project with parent_id should still have its context resolved."""
        # Create parent folder
        parent = Project(name="parent-folder")
        db_session.add(parent)
        await db_session.flush()

        # Create nested project with context profile
        ctx_data = {"language": "typescript", "framework": "svelte"}
        child = Project(
            name="my-app",
            parent_id=parent.id,
            depth=1,
            context_profile=json.dumps(ctx_data),
        )
        db_session.add(child)
        await db_session.flush()

        repo = ProjectRepository(db_session)
        result = await repo.get_context_by_name("my-app")
        assert result is not None
        assert result.language == "typescript"
        assert result.framework == "svelte"

    async def test_deleted_project_excluded(self, db_session: AsyncSession):
        """Deleted projects should not be resolved."""
        project = Project(
            name="deleted-proj",
            status="deleted",
            context_profile=json.dumps({"language": "rust"}),
        )
        db_session.add(project)
        await db_session.flush()

        repo = ProjectRepository(db_session)
        result = await repo.get_context_by_name("deleted-proj")
        assert result is None

    async def test_root_project_still_resolves(self, db_session: AsyncSession):
        """Root-level projects (parent_id=None) should still resolve."""
        project = Project(
            name="root-proj",
            context_profile=json.dumps({"language": "python"}),
        )
        db_session.add(project)
        await db_session.flush()

        repo = ProjectRepository(db_session)
        result = await repo.get_context_by_name("root-proj")
        assert result is not None
        assert result.language == "python"

    async def test_description_fallback(self, db_session: AsyncSession):
        """Project description injects as CodebaseContext.description fallback."""
        project = Project(
            name="desc-proj",
            description="A cool project",
        )
        db_session.add(project)
        await db_session.flush()

        repo = ProjectRepository(db_session)
        result = await repo.get_context_by_name("desc-proj")
        assert result is not None
        assert result.description == "A cool project"

    async def test_most_recently_updated_wins(self, db_session: AsyncSession):
        """When duplicate names exist, the most recently updated project wins."""
        from datetime import datetime, timezone

        old = Project(
            name="dup-proj",
            context_profile=json.dumps({"language": "old"}),
            updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        new = Project(
            name="dup-proj",
            parent_id=None,
            context_profile=json.dumps({"language": "new"}),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add_all([old, new])
        await db_session.flush()

        repo = ProjectRepository(db_session)
        result = await repo.get_context_by_name("dup-proj")
        assert result is not None
        assert result.language == "new"

    async def test_description_fallback_does_not_mutate_original(
        self, db_session: AsyncSession,
    ):
        """The description fallback must not mutate the context_profile data."""
        ctx_data = {"language": "python"}
        project = Project(
            name="desc-alias-proj",
            description="Project description here",
            context_profile=json.dumps(ctx_data),
        )
        db_session.add(project)
        await db_session.flush()

        repo = ProjectRepository(db_session)
        result1 = await repo.get_context_by_name("desc-alias-proj")
        result2 = await repo.get_context_by_name("desc-alias-proj")
        # Both calls should return consistent results (no aliasing mutation)
        assert result1 is not None and result2 is not None
        assert result1.description == "Project description here"
        assert result2.description == "Project description here"


# ---------------------------------------------------------------------------
# Bug 6: workspace link query safety with duplicate project names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWorkspaceLinkDuplication:
    async def test_duplicate_project_names_do_not_crash(self, db_session: AsyncSession):
        """get_link_by_project_name must not raise MultipleResultsFound."""
        from apps.promptforge.models.workspace import WorkspaceLink
        from apps.promptforge.repositories.workspace import WorkspaceRepository

        # Create two projects with the same name
        p1 = Project(name="dupe-ws", description="first")
        p2 = Project(name="dupe-ws", description="second")
        db_session.add_all([p1, p2])
        await db_session.flush()

        # Create a workspace link for one of them
        link = WorkspaceLink(
            project_id=p1.id,
            repo_full_name="owner/repo",
            repo_url="https://github.com/owner/repo",
            sync_source="claude-code",
            workspace_context=json.dumps({"language": "python"}),
        )
        db_session.add(link)
        await db_session.flush()

        ws_repo = WorkspaceRepository(db_session)
        # Should not crash with MultipleResultsFound
        result = await ws_repo.get_link_by_project_name("dupe-ws")
        assert result is not None

    async def test_no_link_returns_none(self, db_session: AsyncSession):
        """No workspace link → None (not crash)."""
        from apps.promptforge.repositories.workspace import WorkspaceRepository

        project = Project(name="no-link-proj")
        db_session.add(project)
        await db_session.flush()

        ws_repo = WorkspaceRepository(db_session)
        result = await ws_repo.get_workspace_context_by_project_name("no-link-proj")
        assert result is None


# ---------------------------------------------------------------------------
# Bug 10: merge_contexts aliasing — description fallback injection safety
# ---------------------------------------------------------------------------


class TestMergeContextsAliasingSafety:
    def test_description_injection_safe(self):
        """Simulates the get_context_by_name description fallback pattern.

        If merge_contexts returned identity references, the fallback would
        mutate the original workspace context object.
        """
        workspace = CodebaseContext(language="python")
        manual = None
        # Layer 1+2 merge — when manual is None, returns copy of workspace
        base = merge_contexts(workspace, manual)
        # Simulate description fallback injection
        base.description = "Injected"
        # Original workspace must not be mutated
        assert workspace.description is None
