"""Codebase context schema for enriching prompt optimization with project awareness."""

import json
from dataclasses import asdict, dataclass, field, replace

MAX_CONTEXT_CHARS = 50_000


@dataclass
class CodebaseContext:
    """Optional codebase context provided by the caller (e.g. Claude Code).

    All fields are optional. When provided, ``render()`` produces a formatted
    text block that pipeline stages inject into their LLM user messages so the
    optimizer can reference actual project patterns, conventions, and architecture.
    """

    language: str | None = None
    framework: str | None = None
    description: str | None = None
    conventions: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    code_snippets: list[str] = field(default_factory=list)
    documentation: str | None = None
    test_framework: str | None = None
    test_patterns: list[str] = field(default_factory=list)

    def render(self) -> str | None:
        """Format all present fields into a text block for LLM injection.

        Returns ``None`` when every field is empty/falsy (no-op for callers).
        Truncates at ``MAX_CONTEXT_CHARS`` to avoid oversized payloads.
        """
        sections: list[str] = []

        if self.language:
            sections.append(f"Language: {self.language}")
        if self.framework:
            sections.append(f"Framework: {self.framework}")
        if self.description:
            sections.append(f"Project description: {self.description}")
        if self.conventions:
            items = "\n".join(f"  - {c}" for c in self.conventions)
            sections.append(f"Conventions:\n{items}")
        if self.patterns:
            items = "\n".join(f"  - {p}" for p in self.patterns)
            sections.append(f"Architectural patterns:\n{items}")
        if self.code_snippets:
            snippets = "\n---\n".join(self.code_snippets)
            sections.append(f"Code snippets:\n{snippets}")
        if self.documentation:
            sections.append(f"Documentation:\n{self.documentation}")
        if self.test_framework:
            sections.append(f"Test framework: {self.test_framework}")
        if self.test_patterns:
            items = "\n".join(f"  - {t}" for t in self.test_patterns)
            sections.append(f"Test patterns:\n{items}")

        if not sections:
            return None

        rendered = "\n\n".join(sections)
        if len(rendered) > MAX_CONTEXT_CHARS:
            rendered = rendered[:MAX_CONTEXT_CHARS] + "\n... (truncated)"
        return rendered


def merge_contexts(
    base: CodebaseContext | None, override: CodebaseContext | None,
) -> CodebaseContext | None:
    """Merge two CodebaseContext objects with field-level replacement.

    Override's non-empty scalar fields replace base's; override's non-empty
    list fields replace base's entirely (no concatenation — avoids duplicates).
    Returns None if both inputs are None.
    """
    if base is None and override is None:
        return None
    if base is None:
        # Return a shallow copy to prevent aliasing — callers may mutate the result
        # (e.g. get_context_by_name injects Project.description as fallback).
        return replace(override)
    if override is None:
        return replace(base)

    merged_kwargs = {}
    for f in CodebaseContext.__dataclass_fields__.values():
        base_val = getattr(base, f.name)
        override_val = getattr(override, f.name)
        # For lists: override replaces if non-empty
        if isinstance(override_val, list):
            merged_kwargs[f.name] = override_val if override_val else base_val
        else:
            # For scalars: override replaces if truthy (non-None, non-empty)
            merged_kwargs[f.name] = override_val if override_val else base_val
    return CodebaseContext(**merged_kwargs)


def context_to_dict(ctx: CodebaseContext | None) -> dict | None:
    """Convert a CodebaseContext to a dict, filtering out empty/None fields."""
    if ctx is None:
        return None
    raw = asdict(ctx)
    return {k: v for k, v in raw.items() if v} or None


def context_from_json(json_str: str | None) -> CodebaseContext | None:
    """Parse a JSON string back to a CodebaseContext.

    Returns None if the string is None, empty, or invalid JSON.
    """
    if not json_str:
        return None
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None
    return codebase_context_from_dict(data)


def codebase_context_from_dict(data: dict | None) -> CodebaseContext | None:
    """Convert a raw dict (from MCP/API) to a CodebaseContext, or None.

    Unknown keys are silently ignored so callers can evolve freely.
    Scalar fields are coerced to str; list fields accept str or list[str].
    Non-dict input (e.g. from ``json.loads("[1,2]")``) returns None.
    """
    if not data or not isinstance(data, dict):
        return None
    known_fields = {f.name for f in CodebaseContext.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    if not filtered:
        return None

    # Coerce scalar fields to str (guards against e.g. {"language": 42})
    _scalar_fields = {"language", "framework", "description", "documentation", "test_framework"}
    for k in _scalar_fields:
        if k in filtered and filtered[k] is not None:
            filtered[k] = str(filtered[k])

    # Coerce list fields: str → [str], list items → str, invalid types dropped
    _list_fields = {"conventions", "patterns", "code_snippets", "test_patterns"}
    for k in _list_fields:
        val = filtered.get(k)
        if val is None:
            continue
        if isinstance(val, str):
            filtered[k] = [val]
        elif isinstance(val, list):
            filtered[k] = [str(item) for item in val if item is not None]
        else:
            del filtered[k]

    return CodebaseContext(**filtered)
