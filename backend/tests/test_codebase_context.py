"""Tests for CodebaseContext dataclass — render(), truncation, and dict conversion."""


from app.schemas.context import (
    MAX_CONTEXT_CHARS,
    CodebaseContext,
    codebase_context_from_dict,
)

# ---------------------------------------------------------------------------
# TestCodebaseContextRender
# ---------------------------------------------------------------------------

class TestCodebaseContextRender:
    def test_empty_context_returns_none(self):
        ctx = CodebaseContext()
        assert ctx.render() is None

    def test_language_only(self):
        ctx = CodebaseContext(language="Python 3.14")
        rendered = ctx.render()
        assert rendered is not None
        assert "Language: Python 3.14" in rendered

    def test_framework_only(self):
        ctx = CodebaseContext(framework="FastAPI / SQLAlchemy 2.0")
        rendered = ctx.render()
        assert "Framework: FastAPI / SQLAlchemy 2.0" in rendered

    def test_description(self):
        ctx = CodebaseContext(description="An AI-powered prompt optimizer")
        rendered = ctx.render()
        assert "Project description: An AI-powered prompt optimizer" in rendered

    def test_conventions_list(self):
        ctx = CodebaseContext(conventions=["PEP 8", "Google docstrings"])
        rendered = ctx.render()
        assert "Conventions:" in rendered
        assert "  - PEP 8" in rendered
        assert "  - Google docstrings" in rendered

    def test_patterns_list(self):
        ctx = CodebaseContext(patterns=["repository pattern", "async ORM"])
        rendered = ctx.render()
        assert "Architectural patterns:" in rendered
        assert "  - repository pattern" in rendered
        assert "  - async ORM" in rendered

    def test_code_snippets(self):
        ctx = CodebaseContext(code_snippets=["def foo(): pass", "class Bar: ..."])
        rendered = ctx.render()
        assert "Code snippets:" in rendered
        assert "def foo(): pass" in rendered
        assert "class Bar: ..." in rendered
        # Snippets separated by ---
        assert "---" in rendered

    def test_documentation(self):
        ctx = CodebaseContext(documentation="# README\nProject docs here.")
        rendered = ctx.render()
        assert "Documentation:" in rendered
        assert "# README" in rendered

    def test_test_framework(self):
        ctx = CodebaseContext(test_framework="pytest + pytest-asyncio")
        rendered = ctx.render()
        assert "Test framework: pytest + pytest-asyncio" in rendered

    def test_test_patterns(self):
        ctx = CodebaseContext(test_patterns=["FakeProvider mocking", "_seed() helpers"])
        rendered = ctx.render()
        assert "Test patterns:" in rendered
        assert "  - FakeProvider mocking" in rendered

    def test_full_context(self):
        ctx = CodebaseContext(
            language="Python 3.14",
            framework="FastAPI",
            description="Web API",
            conventions=["PEP 8"],
            patterns=["repository pattern"],
            code_snippets=["async def main(): ..."],
            documentation="See CLAUDE.md",
            test_framework="pytest",
            test_patterns=["FakeProvider"],
        )
        rendered = ctx.render()
        assert rendered is not None
        # All sections present
        assert "Language:" in rendered
        assert "Framework:" in rendered
        assert "Project description:" in rendered
        assert "Conventions:" in rendered
        assert "Architectural patterns:" in rendered
        assert "Code snippets:" in rendered
        assert "Documentation:" in rendered
        assert "Test framework:" in rendered
        assert "Test patterns:" in rendered

    def test_empty_lists_ignored(self):
        ctx = CodebaseContext(
            language="Python",
            conventions=[],
            patterns=[],
            code_snippets=[],
            test_patterns=[],
        )
        rendered = ctx.render()
        assert rendered is not None
        assert "Conventions:" not in rendered
        assert "Architectural patterns:" not in rendered
        assert "Code snippets:" not in rendered
        assert "Test patterns:" not in rendered


# ---------------------------------------------------------------------------
# TestCodebaseContextTruncation
# ---------------------------------------------------------------------------

class TestCodebaseContextTruncation:
    def test_truncation_at_max_chars(self):
        # Create a context that exceeds MAX_CONTEXT_CHARS
        long_doc = "x" * (MAX_CONTEXT_CHARS + 1000)
        ctx = CodebaseContext(documentation=long_doc)
        rendered = ctx.render()
        assert rendered is not None
        assert len(rendered) <= MAX_CONTEXT_CHARS + 50  # +50 for "... (truncated)" suffix
        assert rendered.endswith("... (truncated)")

    def test_within_limit_no_truncation(self):
        ctx = CodebaseContext(language="Python", framework="FastAPI")
        rendered = ctx.render()
        assert rendered is not None
        assert "truncated" not in rendered


# ---------------------------------------------------------------------------
# TestCodebaseContextFromDict
# ---------------------------------------------------------------------------

class TestCodebaseContextFromDict:
    def test_none_returns_none(self):
        assert codebase_context_from_dict(None) is None

    def test_empty_dict_returns_none(self):
        assert codebase_context_from_dict({}) is None

    def test_full_dict(self):
        data = {
            "language": "Python 3.14",
            "framework": "FastAPI",
            "description": "Web API",
            "conventions": ["PEP 8"],
            "patterns": ["repository"],
            "code_snippets": ["def foo(): ..."],
            "documentation": "Docs here",
            "test_framework": "pytest",
            "test_patterns": ["FakeProvider"],
        }
        ctx = codebase_context_from_dict(data)
        assert ctx is not None
        assert ctx.language == "Python 3.14"
        assert ctx.framework == "FastAPI"
        assert ctx.conventions == ["PEP 8"]
        assert ctx.code_snippets == ["def foo(): ..."]

    def test_unknown_keys_ignored(self):
        data = {
            "language": "Rust",
            "unknown_field": "should be ignored",
            "another_unknown": 42,
        }
        ctx = codebase_context_from_dict(data)
        assert ctx is not None
        assert ctx.language == "Rust"
        assert not hasattr(ctx, "unknown_field")

    def test_partial_dict(self):
        data = {"language": "Go", "framework": "Gin"}
        ctx = codebase_context_from_dict(data)
        assert ctx is not None
        assert ctx.language == "Go"
        assert ctx.framework == "Gin"
        assert ctx.conventions == []  # default
        assert ctx.description is None  # default

    def test_only_unknown_keys_returns_none(self):
        data = {"foo": "bar", "baz": 123}
        assert codebase_context_from_dict(data) is None
