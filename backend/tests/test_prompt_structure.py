"""Tests for the prompt_structure service — regex-based section/variable extraction."""

from apps.promptforge.services.prompt_structure import (
    detect_sections,
    extract_prompt_structure,
    extract_variables,
)


# ---------------------------------------------------------------------------
# extract_variables
# ---------------------------------------------------------------------------


class TestExtractVariables:
    def test_empty_string(self):
        assert extract_variables("") == []

    def test_double_brace(self):
        result = extract_variables("Hello {{name}}")
        assert len(result) == 1
        assert result[0]["name"] == "name"
        assert result[0]["occurrences"] == 1

    def test_single_brace(self):
        result = extract_variables("Hello {name}")
        assert len(result) == 1
        assert result[0]["name"] == "name"
        assert result[0]["occurrences"] == 1

    def test_dedup_double_brace_multiple_occurrences(self):
        result = extract_variables("{{name}} is {{name}}")
        assert len(result) == 1
        assert result[0]["name"] == "name"
        assert result[0]["occurrences"] == 2

    def test_dots_and_dashes_in_names(self):
        result = extract_variables("{{user.name}} and {{api-key}}")
        names = {v["name"] for v in result}
        assert "user.name" in names
        assert "api-key" in names

    def test_whitespace_trimmed(self):
        result = extract_variables("{{ user  }}")
        assert result[0]["name"] == "user"

    def test_skip_dollar_template_literal(self):
        result = extract_variables("${var} should not match")
        assert result == []

    def test_skip_empty_braces(self):
        result = extract_variables("{} should not match")
        assert result == []

    def test_mixed_single_and_double(self):
        result = extract_variables("{{double}} and {single}")
        names = {v["name"] for v in result}
        assert "double" in names
        assert "single" in names

    def test_single_brace_inside_double_not_duplicated(self):
        """Single-brace match inside {{...}} should be skipped."""
        result = extract_variables("{{name}} only")
        assert len(result) == 1
        assert result[0]["name"] == "name"


# ---------------------------------------------------------------------------
# detect_sections
# ---------------------------------------------------------------------------


class TestDetectSections:
    def test_empty_string(self):
        assert detect_sections("") == []

    def test_markdown_heading(self):
        result = detect_sections("# Role\nYou are a helper")
        assert len(result) == 1
        assert result[0]["label"] == "Role"
        assert result[0]["type"] == "role"
        assert result[0]["line_number"] == 1

    def test_colon_delimited(self):
        result = detect_sections("Context: some background info")
        assert len(result) == 1
        assert result[0]["type"] == "context"
        # Label preserves content after colon (only trailing colon+space stripped)
        assert result[0]["label"] == "Context: some background info"

    def test_colon_only_trailing_stripped(self):
        result = detect_sections("Context:")
        assert len(result) == 1
        assert result[0]["label"] == "Context"

    def test_you_are_role(self):
        result = detect_sections("You are a helpful assistant")
        assert len(result) == 1
        assert result[0]["type"] == "role"

    def test_constraints(self):
        result = detect_sections("# Constraints\n- Do not do X")
        assert result[0]["type"] == "constraints"

    def test_output_format(self):
        result = detect_sections("Output format: JSON")
        assert result[0]["type"] == "output"

    def test_body_text_suppression(self):
        """Lines after a section header (before blank line) are not matched."""
        text = "Role: Assistant\nYou are a helpful bot\n\nContext: Some info"
        result = detect_sections(text)
        # "You are" on line 2 should not create a second role section
        types = [s["type"] for s in result]
        assert types == ["role", "context"]

    def test_blank_line_resets_body(self):
        text = "Role: Assistant\n\nYou are a specialist"
        result = detect_sections(text)
        # After blank line, "You are" can start a new section
        assert len(result) == 2

    def test_explicit_header_overrides_body(self):
        """Even inside a section body, explicit headers start new sections."""
        text = "Role: Writer\nContext: Background info"
        result = detect_sections(text)
        # "Context:" is an explicit header, should override body suppression
        assert len(result) == 2

    def test_multiple_section_types(self):
        text = "# Role\nAssistant\n\n# Context\nInfo\n\n# Steps\n1. Do X\n\n# Output\nJSON"
        result = detect_sections(text)
        types = [s["type"] for s in result]
        assert types == ["role", "context", "steps", "output"]

    def test_task_section(self):
        result = detect_sections("Task: Summarize the document")
        assert result[0]["type"] == "task"

    def test_examples_section(self):
        result = detect_sections("## Examples\nHere is an example")
        assert result[0]["type"] == "examples"

    def test_do_not_constraint(self):
        result = detect_sections("Do not include personal information")
        assert result[0]["type"] == "constraints"

    def test_act_as_role(self):
        result = detect_sections("Act as a senior developer")
        assert result[0]["type"] == "role"


# ---------------------------------------------------------------------------
# extract_prompt_structure (combined)
# ---------------------------------------------------------------------------


class TestExtractPromptStructure:
    def test_combined_output(self):
        text = "# Role\nYou are a helper\n\n{{user}} asks about {{topic}}"
        result = extract_prompt_structure(text)
        assert "sections" in result
        assert "variables" in result
        assert len(result["sections"]) >= 1
        assert len(result["variables"]) == 2
        var_names = {v["name"] for v in result["variables"]}
        assert "user" in var_names
        assert "topic" in var_names

    def test_empty_input(self):
        result = extract_prompt_structure("")
        assert result["sections"] == []
        assert result["variables"] == []
