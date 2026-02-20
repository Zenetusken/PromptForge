"""Codebase context schema for enriching prompt optimization with project awareness."""

from dataclasses import dataclass, field

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


def codebase_context_from_dict(data: dict | None) -> CodebaseContext | None:
    """Convert a raw dict (from MCP/API) to a CodebaseContext, or None.

    Unknown keys are silently ignored so callers can evolve freely.
    """
    if not data:
        return None
    known_fields = {f.name for f in CodebaseContext.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    if not filtered:
        return None
    return CodebaseContext(**filtered)
