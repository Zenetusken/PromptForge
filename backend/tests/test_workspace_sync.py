"""Tests for workspace sync context extraction."""

import json

from app.schemas.context import CodebaseContext, merge_contexts
from app.services.workspace_sync import (
    extract_context_from_repo,
    extract_context_from_workspace_info,
)


class TestExtractContextFromRepo:
    """Test deterministic context extraction from repo data."""

    def test_node_react_project(self):
        """Detect React + Vitest from package.json deps."""
        pkg = json.dumps({
            "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
            "devDependencies": {"vitest": "^1.0.0", "@testing-library/react": "^14.0.0"},
        })
        ctx = extract_context_from_repo(
            repo_metadata={"language": "TypeScript", "description": "My React app"},
            file_tree=["src/App.tsx", "src/components/Button.tsx", "tests/App.test.tsx"],
            file_contents={"package.json": pkg},
        )
        assert ctx.language == "TypeScript"
        assert ctx.framework == "React 18.2.0"
        assert ctx.description == "My React app"
        assert ctx.test_framework == "Vitest"
        assert "Component-based architecture" in ctx.patterns

    def test_python_fastapi_project(self):
        """Detect FastAPI + pytest from pyproject.toml."""
        toml = """
[project]
name = "myapi"
dependencies = [
    "fastapi>=0.100.0",
    "sqlalchemy>=2.0",
    "pytest>=8.0",
]

[tool.ruff]
line-length = 100
"""
        ctx = extract_context_from_repo(
            repo_metadata={"language": "Python"},
            file_tree=[
                "app/main.py", "app/models/user.py", "app/services/auth.py",
                "tests/test_main.py", ".editorconfig",
            ],
            file_contents={"pyproject.toml": toml},
        )
        assert ctx.language == "Python"
        assert "FastAPI" in ctx.framework
        assert ctx.test_framework == "pytest"
        assert "Ruff linter configured" in ctx.conventions
        assert "Service layer pattern" in ctx.patterns

    def test_sveltekit_project(self):
        """Detect SvelteKit from package.json."""
        pkg = json.dumps({
            "dependencies": {"@sveltejs/kit": "^2.0.0"},
            "devDependencies": {"vitest": "^3.0.0", "svelte": "^5.0.0"},
        })
        ctx = extract_context_from_repo(
            repo_metadata={"language": "JavaScript"},
            file_tree=["src/routes/+page.svelte", "src/lib/stores/app.ts"],
            file_contents={"package.json": pkg},
        )
        assert ctx.framework == "SvelteKit 2.0.0"
        assert ctx.test_framework == "Vitest"
        assert "Route-based organization" in ctx.patterns

    def test_empty_repo(self):
        """Empty repo returns context with only language (if available)."""
        ctx = extract_context_from_repo(
            repo_metadata={"language": "Go"},
            file_tree=[],
            file_contents={},
        )
        assert ctx.language == "Go"
        assert ctx.framework is None
        assert ctx.conventions == []

    def test_description_truncation(self):
        """Descriptions over 500 chars are truncated."""
        long_desc = "x" * 600
        ctx = extract_context_from_repo(
            repo_metadata={"description": long_desc},
            file_tree=[],
        )
        assert len(ctx.description) <= 503  # 500 + "..."

    def test_language_detection_from_extensions(self):
        """Language detected from file extension frequency when no API/marker data."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=[
                "src/main.rs", "src/lib.rs", "src/utils.rs",
                "README.md",
            ],
            file_contents={},
        )
        assert ctx.language == "Rust"

    def test_conventions_from_linter_configs(self):
        """Detect conventions from linter config files in tree."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=[".eslintrc.json", ".prettierrc", "tsconfig.json"],
            file_contents={},
        )
        assert "ESLint configured" in ctx.conventions
        assert "Prettier configured" in ctx.conventions
        assert "TypeScript strict mode" in ctx.conventions

    def test_test_patterns_detection(self):
        """Detect test patterns from file naming conventions."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=[
                "src/app.test.ts", "src/utils.spec.js",
                "tests/conftest.py", "tests/test_main.py",
            ],
        )
        assert any("test.{ts,js}" in p for p in ctx.test_patterns)
        assert any("spec.{ts,js}" in p for p in ctx.test_patterns)
        assert any("pytest" in p for p in ctx.test_patterns)


class TestExtractContextFromWorkspaceInfo:
    """Test context extraction from Claude Code sync_workspace payloads."""

    def test_basic_js_workspace(self):
        """Extract context from workspace_info with JS deps."""
        ctx = extract_context_from_workspace_info({
            "file_tree": ["src/index.ts", "src/components/App.svelte"],
            "dependencies": {"svelte": "5.0.0", "@sveltejs/kit": "2.0.0"},
        })
        assert ctx.framework is not None
        assert "SvelteKit" in ctx.framework

    def test_python_workspace(self):
        """Extract context from workspace_info with Python deps."""
        ctx = extract_context_from_workspace_info({
            "file_tree": ["app/main.py", "tests/test_app.py"],
            "dependencies": {"fastapi": "0.100.0"},
        })
        assert ctx.framework is not None
        assert "FastAPI" in ctx.framework

    def test_empty_workspace_info(self):
        """Empty workspace_info produces minimal context."""
        ctx = extract_context_from_workspace_info({})
        assert ctx.language is None
        assert ctx.framework is None


class TestThreeLayerMerge:
    """Test the 3-layer context resolution priority system."""

    def test_manual_overrides_workspace(self):
        """Manual context profile overrides workspace auto-detected context."""
        workspace = CodebaseContext(language="Python", framework="FastAPI 0.100")
        manual = CodebaseContext(framework="FastAPI 0.115")
        result = merge_contexts(workspace, manual)
        assert result.language == "Python"  # from workspace (manual has None)
        assert result.framework == "FastAPI 0.115"  # manual wins

    def test_explicit_overrides_all(self):
        """Per-request explicit context overrides both manual and workspace."""
        workspace = CodebaseContext(language="Python", framework="FastAPI")
        manual = CodebaseContext(description="My API")
        explicit = CodebaseContext(language="TypeScript")

        base = merge_contexts(workspace, manual)
        resolved = merge_contexts(base, explicit)

        assert resolved.language == "TypeScript"  # explicit wins
        # from workspace (neither manual nor explicit set it)
        assert resolved.framework == "FastAPI"
        assert resolved.description == "My API"  # from manual

    def test_workspace_none_does_not_break(self):
        """No workspace link — 2-layer merge still works (backward compatible)."""
        manual = CodebaseContext(language="Go", framework="Gin")
        base = merge_contexts(None, manual)  # workspace=None
        resolved = merge_contexts(base, None)  # explicit=None
        assert resolved.language == "Go"
        assert resolved.framework == "Gin"

    def test_all_none(self):
        """All layers None returns None."""
        base = merge_contexts(None, None)
        resolved = merge_contexts(base, None)
        assert resolved is None
