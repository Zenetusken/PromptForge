"""Tests for three-tier context resolution: schema utilities, merge, and repository."""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.models.project import Project
from apps.promptforge.repositories.project import ProjectRepository
from apps.promptforge.schemas.context import (
    _SNAPSHOT_SOURCE_CONTENT_CHARS,
    MAX_CONTEXT_CHARS,
    CodebaseContext,
    SourceDocument,
    codebase_context_from_dict,
    codebase_context_from_kernel,
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

    def test_render_has_project_identity_section(self):
        ctx = CodebaseContext(
            description="An AI-powered prompt optimizer",
            language="TypeScript",
            framework="SvelteKit 2",
        )
        rendered = ctx.render()
        assert rendered is not None
        assert "## Project Identity" in rendered
        assert "Project description: An AI-powered prompt optimizer" in rendered
        assert "Language: TypeScript" in rendered
        assert "Framework: SvelteKit 2" in rendered

    def test_render_has_technical_details_section(self):
        ctx = CodebaseContext(
            conventions=["PEP 8", "ruff"],
            patterns=["repository pattern"],
        )
        rendered = ctx.render()
        assert rendered is not None
        assert "## Technical Details" in rendered
        assert "Conventions:" in rendered
        assert "Architectural patterns:" in rendered

    def test_render_identity_only_no_technical(self):
        ctx = CodebaseContext(description="A cool product")
        rendered = ctx.render()
        assert rendered is not None
        assert "## Project Identity" in rendered
        assert "## Technical Details" not in rendered

    def test_render_technical_only_no_identity(self):
        ctx = CodebaseContext(conventions=["use strict"])
        rendered = ctx.render()
        assert rendered is not None
        assert "## Technical Details" in rendered
        assert "## Project Identity" not in rendered

    def test_render_both_sections_present(self):
        ctx = CodebaseContext(
            description="PromptForge",
            language="Python",
            conventions=["ruff", "pytest"],
            test_framework="pytest",
        )
        rendered = ctx.render()
        assert rendered is not None
        assert "## Project Identity" in rendered
        assert "## Technical Details" in rendered
        # Identity section comes first
        identity_pos = rendered.index("## Project Identity")
        tech_pos = rendered.index("## Technical Details")
        assert identity_pos < tech_pos

    def test_documentation_in_identity_tier(self):
        """Documentation alone should appear under Project Identity, not Technical Details."""
        ctx = CodebaseContext(documentation="Full API reference for the platform.")
        rendered = ctx.render()
        assert rendered is not None
        assert "## Project Identity" in rendered
        assert "## Technical Details" not in rendered
        assert "Documentation:" in rendered
        assert "Full API reference for the platform." in rendered

    def test_documentation_before_technical_details(self):
        """When both documentation and conventions are present, documentation should
        appear in Project Identity (before Technical Details)."""
        ctx = CodebaseContext(
            documentation="Architecture overview and design decisions.",
            conventions=["PEP 8", "ruff"],
        )
        rendered = ctx.render()
        assert rendered is not None
        assert "## Project Identity" in rendered
        assert "## Technical Details" in rendered
        # Documentation should be in the Identity section (before Technical Details)
        doc_pos = rendered.index("Architecture overview and design decisions.")
        tech_pos = rendered.index("## Technical Details")
        assert doc_pos < tech_pos


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


# ---------------------------------------------------------------------------
# Knowledge Sources: render, serialization, and from_dict
# ---------------------------------------------------------------------------


class TestRenderWithSources:
    def test_sources_section_rendered(self):
        ctx = CodebaseContext(
            sources=[
                SourceDocument(title="Architecture Doc", content="The system uses a pipeline..."),
                SourceDocument(title="API Reference", content="GET /api/users"),
            ],
        )
        rendered = ctx.render()
        assert rendered is not None
        assert "## Knowledge Sources" in rendered
        assert "### [1] Architecture Doc" in rendered
        assert "### [2] API Reference" in rendered

    def test_sources_between_identity_and_technical(self):
        ctx = CodebaseContext(
            description="A prompt optimizer",
            language="Python",
            conventions=["PEP 8"],
            sources=[SourceDocument(title="Design Doc", content="Design details here.")],
        )
        rendered = ctx.render()
        assert rendered is not None
        identity_pos = rendered.index("## Project Identity")
        sources_pos = rendered.index("## Knowledge Sources")
        tech_pos = rendered.index("## Technical Details")
        assert identity_pos < sources_pos < tech_pos

    def test_source_budget_proportional_truncation(self):
        """Each source gets an equal share of the 50K source budget."""
        long_content = "X" * 60_000
        ctx = CodebaseContext(
            sources=[
                SourceDocument(title="Big Doc", content=long_content),
                SourceDocument(title="Other Doc", content="Short content"),
            ],
        )
        rendered = ctx.render()
        assert rendered is not None
        # Big Doc should be truncated (each gets 25K of 50K budget)
        assert "... (truncated)" in rendered
        # Short content should be intact
        assert "Short content" in rendered

    def test_disabled_sources_excluded(self):
        """Empty content sources are filtered out during rendering."""
        ctx = CodebaseContext(
            sources=[
                SourceDocument(title="Active", content="Real content"),
                SourceDocument(title="Empty", content=""),
            ],
        )
        rendered = ctx.render()
        assert rendered is not None
        assert "Active" in rendered
        assert "Empty" not in rendered

    def test_empty_sources_no_section(self):
        ctx = CodebaseContext(sources=[])
        assert ctx.render() is None

    def test_max_context_chars_increased(self):
        assert MAX_CONTEXT_CHARS == 80_000


class TestContextSerializationWithSources:
    def test_context_to_dict_includes_sources(self):
        ctx = CodebaseContext(
            language="python",
            sources=[
                SourceDocument(title="Doc A", content="Short content"),
            ],
        )
        d = context_to_dict(ctx)
        assert d is not None
        assert "sources" in d
        assert len(d["sources"]) == 1
        assert d["sources"][0]["title"] == "Doc A"

    def test_codebase_context_from_dict_parses_sources(self):
        data = {
            "language": "python",
            "sources": [
                {"title": "My Doc", "content": "Doc content", "source_type": "document"},
                {"title": "API Ref", "content": "GET /users"},
            ],
        }
        ctx = codebase_context_from_dict(data)
        assert ctx is not None
        assert len(ctx.sources) == 2
        assert ctx.sources[0].title == "My Doc"
        assert ctx.sources[1].title == "API Ref"
        assert ctx.sources[1].source_type == "document"  # default

    def test_snapshot_truncates_source_content(self):
        long_content = "A" * 10_000
        ctx = CodebaseContext(
            sources=[SourceDocument(title="Big", content=long_content)],
        )
        d = context_to_dict(ctx)
        assert d is not None
        assert len(d["sources"][0]["content"]) == _SNAPSHOT_SOURCE_CONTENT_CHARS

    def test_from_dict_ignores_invalid_source_entries(self):
        data = {
            "language": "go",
            "sources": [
                {"title": "Valid", "content": "Content"},
                {"no_title": True},  # invalid — missing title+content
                "just a string",  # invalid — not a dict
            ],
        }
        ctx = codebase_context_from_dict(data)
        assert ctx is not None
        assert len(ctx.sources) == 1
        assert ctx.sources[0].title == "Valid"

    def test_roundtrip_serialize_deserialize(self):
        original = CodebaseContext(
            language="rust",
            sources=[
                SourceDocument(
                    title="Spec", content="Specification content",
                    source_type="specification",
                ),
            ],
        )
        d = context_to_dict(original)
        restored = codebase_context_from_dict(d)
        assert restored is not None
        assert restored.language == "rust"
        assert len(restored.sources) == 1
        assert restored.sources[0].title == "Spec"
        assert restored.sources[0].source_type == "specification"


# ---------------------------------------------------------------------------
# Kernel Knowledge Base → CodebaseContext factory
# ---------------------------------------------------------------------------


class TestCodebaseContextFromKernel:
    """Test codebase_context_from_kernel() factory function."""

    def test_none_returns_none(self):
        assert codebase_context_from_kernel(None) is None

    def test_empty_dict_returns_none(self):
        assert codebase_context_from_kernel({}) is None

    def test_all_empty_returns_none(self):
        resolved = {"profile": {}, "metadata": {}, "sources": []}
        assert codebase_context_from_kernel(resolved) is None

    def test_identity_fields_mapped(self):
        resolved = {
            "profile": {
                "language": "Python",
                "framework": "FastAPI",
                "description": "An API server",
                "test_framework": "pytest",
            },
            "metadata": {},
            "sources": [],
        }
        ctx = codebase_context_from_kernel(resolved)
        assert ctx is not None
        assert ctx.language == "Python"
        assert ctx.framework == "FastAPI"
        assert ctx.description == "An API server"
        assert ctx.test_framework == "pytest"

    def test_metadata_fields_mapped(self):
        resolved = {
            "profile": {"language": "Go"},
            "metadata": {
                "conventions": ["gofmt", "golint"],
                "patterns": ["clean architecture"],
                "test_patterns": ["table-driven"],
            },
            "sources": [],
        }
        ctx = codebase_context_from_kernel(resolved)
        assert ctx is not None
        assert ctx.conventions == ["gofmt", "golint"]
        assert ctx.patterns == ["clean architecture"]
        assert ctx.test_patterns == ["table-driven"]

    def test_sources_mapped(self):
        resolved = {
            "profile": {"language": "Rust"},
            "metadata": {},
            "sources": [
                {"title": "API Docs", "content": "GET /users", "source_type": "api_reference"},
                {"title": "Spec", "content": "System spec", "source_type": "specification"},
            ],
        }
        ctx = codebase_context_from_kernel(resolved)
        assert ctx is not None
        assert len(ctx.sources) == 2
        assert ctx.sources[0].title == "API Docs"
        assert ctx.sources[0].source_type == "api_reference"
        assert ctx.sources[1].title == "Spec"

    def test_empty_title_or_content_sources_filtered(self):
        resolved = {
            "profile": {"language": "Rust"},
            "metadata": {},
            "sources": [
                {"title": "Valid", "content": "Real content"},
                {"title": "", "content": "No title"},
                {"title": "No content", "content": ""},
            ],
        }
        ctx = codebase_context_from_kernel(resolved)
        assert ctx is not None
        assert len(ctx.sources) == 1
        assert ctx.sources[0].title == "Valid"

    def test_documentation_and_code_snippets_not_populated(self):
        """Deprecated fields should not appear in kernel-resolved context."""
        resolved = {
            "profile": {"language": "Python"},
            "metadata": {},
            "sources": [],
        }
        ctx = codebase_context_from_kernel(resolved)
        assert ctx is not None
        assert ctx.documentation is None
        assert ctx.code_snippets == []

    def test_full_resolution_with_all_fields(self):
        resolved = {
            "profile": {
                "language": "TypeScript",
                "framework": "SvelteKit",
                "description": "A web app",
                "test_framework": "vitest",
            },
            "metadata": {
                "conventions": ["eslint"],
                "patterns": ["component-driven"],
            },
            "auto_detected": {
                "language": "TypeScript",
            },
            "sources": [
                {"title": "README", "content": "Project readme", "source_type": "document"},
            ],
        }
        ctx = codebase_context_from_kernel(resolved)
        assert ctx is not None
        assert ctx.language == "TypeScript"
        assert ctx.framework == "SvelteKit"
        assert ctx.conventions == ["eslint"]
        assert len(ctx.sources) == 1


# ---------------------------------------------------------------------------
# resolve_project_context() integration tests (kernel-first + legacy fallback)
# ---------------------------------------------------------------------------


class TestResolveProjectContext:
    """Integration tests for the shared context resolver.

    Exercises the full kernel-first-then-legacy-fallback flow in
    ``context_resolver.py:resolve_project_context()`` against real DB state.
    """

    @pytest.mark.asyncio
    async def test_no_project_returns_explicit_only(self, db_session: AsyncSession):
        """When project_name is None, only explicit override is returned."""
        from apps.promptforge.services.context_resolver import resolve_project_context

        result = await resolve_project_context(
            db_session, None, {"language": "Go"},
        )
        assert result is not None
        assert result.language == "Go"

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_explicit_only(
        self, db_session: AsyncSession,
    ):
        from apps.promptforge.services.context_resolver import resolve_project_context

        result = await resolve_project_context(
            db_session, "nonexistent-project", {"framework": "Express"},
        )
        assert result is not None
        assert result.framework == "Express"

    @pytest.mark.asyncio
    async def test_kernel_profile_resolved(self, db_session: AsyncSession):
        """When a kernel profile exists, its data is used."""
        from apps.promptforge.services.context_resolver import resolve_project_context
        from kernel.repositories.knowledge import KnowledgeRepository

        # Create a PF project
        project = Project(name="kernel-test", description="Test project")
        db_session.add(project)
        await db_session.flush()

        # Create a kernel knowledge profile
        knowledge_repo = KnowledgeRepository(db_session)
        kp = await knowledge_repo.get_or_create_profile(
            "promptforge", project.id, "kernel-test",
        )
        await knowledge_repo.update_profile(
            kp["id"], language="Python", framework="FastAPI",
        )
        await knowledge_repo.create_source(
            kp["id"], "API Docs", "GET /users", "api_reference",
        )

        result = await resolve_project_context(db_session, "kernel-test")
        assert result is not None
        assert result.language == "Python"
        assert result.framework == "FastAPI"
        assert len(result.sources) == 1
        assert result.sources[0].title == "API Docs"

    @pytest.mark.asyncio
    async def test_explicit_override_wins(self, db_session: AsyncSession):
        """Per-request explicit override takes precedence over kernel data."""
        from apps.promptforge.services.context_resolver import resolve_project_context
        from kernel.repositories.knowledge import KnowledgeRepository

        project = Project(name="override-test", description="")
        db_session.add(project)
        await db_session.flush()

        knowledge_repo = KnowledgeRepository(db_session)
        kp = await knowledge_repo.get_or_create_profile(
            "promptforge", project.id, "override-test",
        )
        await knowledge_repo.update_profile(kp["id"], language="Python")

        result = await resolve_project_context(
            db_session, "override-test", {"language": "Rust"},
        )
        assert result is not None
        assert result.language == "Rust"

    @pytest.mark.asyncio
    async def test_legacy_fallback_when_no_kernel_profile(
        self, db_session: AsyncSession,
    ):
        """When no kernel profile exists, falls back to legacy resolution."""
        from apps.promptforge.services.context_resolver import resolve_project_context

        # Create project with legacy context_profile but no kernel profile
        project = Project(
            name="legacy-test",
            description="A legacy project",
            context_profile=json.dumps({"language": "Java", "framework": "Spring"}),
        )
        db_session.add(project)
        await db_session.flush()

        result = await resolve_project_context(db_session, "legacy-test")
        assert result is not None
        assert result.language == "Java"
        assert result.framework == "Spring"

    @pytest.mark.asyncio
    async def test_no_context_returns_none(self, db_session: AsyncSession):
        """When no project, no kernel, no explicit -- returns None."""
        from apps.promptforge.services.context_resolver import resolve_project_context

        result = await resolve_project_context(db_session, None, None)
        assert result is None
