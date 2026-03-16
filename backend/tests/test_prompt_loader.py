import json
import pytest
from pathlib import Path
from app.services.prompt_loader import PromptLoader


@pytest.fixture
def tmp_prompts(tmp_path):
    """Create a temporary prompts directory with test templates."""
    (tmp_path / "test.md").write_text(
        "<user-prompt>\n{{raw_prompt}}\n</user-prompt>\n\n"
        "<context>\n{{codebase_context}}\n</context>\n\n"
        "## Instructions\nDo the thing."
    )
    (tmp_path / "static.md").write_text("You are a helpful assistant.")
    manifest = {
        "test.md": {"required": ["raw_prompt"], "optional": ["codebase_context"]},
        "static.md": {"required": [], "optional": []},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


class TestPromptLoader:
    def test_load_static(self, tmp_prompts):
        loader = PromptLoader(tmp_prompts)
        result = loader.load("static.md")
        assert result == "You are a helpful assistant."

    def test_render_with_variables(self, tmp_prompts):
        loader = PromptLoader(tmp_prompts)
        result = loader.render("test.md", {"raw_prompt": "Write a function", "codebase_context": "file.py: def foo():"})
        assert "Write a function" in result
        assert "file.py: def foo():" in result

    def test_optional_var_removed_with_empty_tags(self, tmp_prompts):
        loader = PromptLoader(tmp_prompts)
        result = loader.render("test.md", {"raw_prompt": "test"})
        assert "<context>" not in result
        assert "test" in result

    def test_missing_required_var_raises(self, tmp_prompts):
        loader = PromptLoader(tmp_prompts)
        with pytest.raises(ValueError, match="Required variable.*raw_prompt"):
            loader.render("test.md", {})

    def test_unknown_template_raises(self, tmp_prompts):
        loader = PromptLoader(tmp_prompts)
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent.md")

    def test_hot_reload(self, tmp_prompts):
        loader = PromptLoader(tmp_prompts)
        result1 = loader.load("static.md")
        (tmp_prompts / "static.md").write_text("Updated content")
        result2 = loader.load("static.md")
        assert result2 == "Updated content"


class TestStartupValidation:
    def test_validate_all_passes(self, tmp_prompts):
        loader = PromptLoader(tmp_prompts)
        loader.validate_all()  # should not raise

    def test_validate_all_fails_missing_file(self, tmp_prompts):
        manifest = json.loads((tmp_prompts / "manifest.json").read_text())
        manifest["nonexistent.md"] = {"required": ["foo"], "optional": []}
        (tmp_prompts / "manifest.json").write_text(json.dumps(manifest))
        loader = PromptLoader(tmp_prompts)
        with pytest.raises(RuntimeError, match="Template file missing"):
            loader.validate_all()

    def test_validate_all_fails_missing_placeholder(self, tmp_prompts):
        (tmp_prompts / "broken.md").write_text("No placeholders here.")
        manifest = json.loads((tmp_prompts / "manifest.json").read_text())
        manifest["broken.md"] = {"required": ["missing_var"], "optional": []}
        (tmp_prompts / "manifest.json").write_text(json.dumps(manifest))
        loader = PromptLoader(tmp_prompts)
        with pytest.raises(RuntimeError, match="missing required variable"):
            loader.validate_all()

    def test_validate_all_skips_empty_required(self, tmp_prompts):
        (tmp_prompts / "static2.md").write_text("Just text.")
        manifest = json.loads((tmp_prompts / "manifest.json").read_text())
        manifest["static2.md"] = {"required": [], "optional": []}
        (tmp_prompts / "manifest.json").write_text(json.dumps(manifest))
        loader = PromptLoader(tmp_prompts)
        loader.validate_all()
