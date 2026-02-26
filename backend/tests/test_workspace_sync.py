"""Tests for workspace sync context extraction."""

import json

from app.schemas.context import CodebaseContext, merge_contexts
from app.services.workspace_sync import (
    _README_MAX_CHARS,
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
        assert "TypeScript configured" in ctx.conventions

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


class TestReadmeExtraction:
    """Test README.md content extraction into documentation field."""

    def test_readme_populates_documentation(self):
        """README in file_contents → documentation field set."""
        ctx = extract_context_from_repo(
            repo_metadata={"language": "Python"},
            file_tree=["README.md", "app/main.py"],
            file_contents={"README.md": "# My Project\n\nA cool project."},
        )
        assert ctx.documentation is not None
        assert "My Project" in ctx.documentation

    def test_readme_truncation(self):
        """Long README is truncated to _README_MAX_CHARS."""
        long_readme = "x" * (_README_MAX_CHARS + 500)
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["README.md"],
            file_contents={"README.md": long_readme},
        )
        assert ctx.documentation is not None
        assert len(ctx.documentation) <= _README_MAX_CHARS + 20  # allow for suffix
        assert ctx.documentation.endswith("(truncated)")

    def test_readme_html_stripped(self):
        """HTML tags in README are removed."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["README.md"],
            file_contents={"README.md": "<h1>Title</h1>\n<p>Content</p>"},
        )
        assert "<h1>" not in ctx.documentation
        assert "Title" in ctx.documentation

    def test_no_readme_leaves_documentation_none(self):
        """Missing README leaves documentation as None."""
        ctx = extract_context_from_repo(
            repo_metadata={"language": "Go"},
            file_tree=["main.go"],
            file_contents={},
        )
        assert ctx.documentation is None


class TestDualLanguageDetection:
    """Test dual-language detection for multi-ecosystem projects."""

    def test_python_and_typescript(self):
        """Both pyproject.toml and package.json → combined language string."""
        pkg = json.dumps({"dependencies": {"react": "^18.0.0"}})
        toml = '[project]\ndependencies = ["fastapi>=0.100"]'
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["backend/main.py", "frontend/index.ts", "tsconfig.json"],
            file_contents={"pyproject.toml": toml, "package.json": pkg, "tsconfig.json": "{}"},
        )
        assert "Python" in ctx.language
        assert "TypeScript" in ctx.language
        # Framework detection still works for dual-language projects
        assert ctx.framework is not None
        assert "React" in ctx.framework or "FastAPI" in ctx.framework

    def test_python_and_javascript_no_tsconfig(self):
        """Python + package.json without tsconfig → JavaScript (not TypeScript)."""
        pkg = json.dumps({"dependencies": {"express": "^4.0.0"}})
        toml = '[project]\ndependencies = ["flask>=2.0"]'
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["app.py", "index.js"],
            file_contents={"pyproject.toml": toml, "package.json": pkg},
        )
        assert "Python" in ctx.language
        assert "JavaScript" in ctx.language
        assert "TypeScript" not in ctx.language

    def test_single_language_not_dual(self):
        """Only Python markers → no dual language."""
        toml = '[project]\ndependencies = ["fastapi>=0.100"]'
        ctx = extract_context_from_repo(
            repo_metadata={"language": "Python"},
            file_tree=["app/main.py"],
            file_contents={"pyproject.toml": toml},
        )
        assert ctx.language == "Python"


class TestLinterConfigParsing:
    """Test richer convention extraction from actual linter config content."""

    def test_tsconfig_strict_convention(self):
        """tsconfig with strict:true → 'TypeScript strict mode enabled' convention."""
        tsconfig = json.dumps({"compilerOptions": {"strict": True, "target": "ES2022"}})
        ctx = extract_context_from_repo(
            repo_metadata={"language": "TypeScript"},
            file_tree=["tsconfig.json"],
            file_contents={"tsconfig.json": tsconfig},
        )
        assert "TypeScript strict mode enabled" in ctx.conventions
        assert "TypeScript target: ES2022" in ctx.conventions

    def test_ruff_line_length(self):
        """pyproject.toml [tool.ruff] line-length → convention."""
        toml = '[project]\ndependencies = []\n\n[tool.ruff]\nline-length = 100\ntarget-version = "py312"'
        ctx = extract_context_from_repo(
            repo_metadata={"language": "Python"},
            file_tree=[],
            file_contents={"pyproject.toml": toml},
        )
        assert "Ruff line-length: 100" in ctx.conventions
        assert "Ruff target: py312" in ctx.conventions

    def test_prettier_settings(self):
        """Prettier config → formatting convention string."""
        prettierrc = json.dumps({"semi": False, "singleQuote": True, "tabWidth": 2})
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=[".prettierrc"],
            file_contents={".prettierrc": prettierrc},
        )
        assert any("no semicolons" in c for c in ctx.conventions)
        assert any("single quotes" in c for c in ctx.conventions)

    def test_eslint_typescript_plugin(self):
        """ESLint config with @typescript-eslint → convention detected."""
        eslint = json.dumps({"extends": ["@typescript-eslint/recommended"]})
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=[".eslintrc.json"],
            file_contents={".eslintrc.json": eslint},
        )
        assert "@typescript-eslint plugin active" in ctx.conventions


class TestInfraPatterns:
    """Test Docker/CI/monorepo pattern detection."""

    def test_dockerfile_detected(self):
        """Dockerfile in tree → Containerized deployment pattern."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["Dockerfile", "src/main.py"],
        )
        assert "Containerized deployment" in ctx.patterns

    def test_docker_compose_detected(self):
        """docker-compose.yml → Docker Compose pattern."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["docker-compose.yml", "Dockerfile"],
        )
        assert "Docker Compose orchestration" in ctx.patterns

    def test_github_actions_detected(self):
        """GitHub Actions workflow files → CI/CD pattern."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=[".github/workflows/ci.yml", "src/main.py"],
        )
        assert "GitHub Actions CI/CD" in ctx.patterns

    def test_monorepo_nx_detected(self):
        """nx.json → Monorepo pattern."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["nx.json", "packages/app/src/main.ts"],
        )
        assert "Monorepo (Nx)" in ctx.patterns

    def test_makefile_detected(self):
        """Makefile → Make-based build system."""
        ctx = extract_context_from_repo(
            repo_metadata={},
            file_tree=["Makefile", "src/main.go"],
        )
        assert "Make-based build system" in ctx.patterns
