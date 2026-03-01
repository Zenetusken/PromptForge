"""Project context schema for enriching prompt optimization with project knowledge.

The class is named ``CodebaseContext`` for backward compatibility with existing API
field names, DB columns, and Python parameter names. Despite the name, it serves as
a general-purpose **project knowledge source** — like NotebookLM's "sources" — that
can fuel any type of prompt: coding, essays, marketing copy, technical blogs, etc.
"""

import json
from dataclasses import asdict, dataclass, field, replace

MAX_CONTEXT_CHARS = 80_000

# Budget allocated to Knowledge Sources within the total context budget.
_SOURCE_BUDGET_CHARS = 50_000

# Max chars per source stored in the optimization snapshot (prevents DB bloat).
_SNAPSHOT_SOURCE_CONTENT_CHARS = 5_000


@dataclass
class SourceDocument:
    """A named knowledge source document attached to a project."""

    title: str
    content: str
    source_type: str = "document"


@dataclass
class CodebaseContext:
    """Project knowledge source provided by the caller (e.g. Claude Code, MCP, REST API).

    Despite the ``CodebaseContext`` class name (kept for backward compatibility),
    this is a general-purpose knowledge base — like uploaded reference documents in
    NotebookLM. All fields are optional. When provided, ``render()`` produces a
    formatted text block that pipeline stages inject into their LLM user messages
    so the optimizer can reference actual project knowledge, patterns, and identity.
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
    sources: list[SourceDocument] = field(default_factory=list)

    def render(self) -> str | None:
        """Format all present fields into a multi-tier text block for LLM injection.

        **Project Identity** (description, language, framework, documentation) is
        always relevant — it tells the LLM what product/project this optimization
        is for, even for non-coding prompts like marketing copy or creative writing.
        Documentation is the richest knowledge source, akin to "uploaded documents"
        in NotebookLM.

        **Knowledge Sources** (named reference documents) are inserted between
        Identity and Technical Details. Each source gets a proportional share of
        the source budget (50K chars).

        **Technical Details** (conventions, patterns, code snippets, tests) are
        relevant primarily for coding and technical tasks.

        Returns ``None`` when every field is empty/falsy (no-op for callers).
        Truncates at ``MAX_CONTEXT_CHARS`` to avoid oversized payloads.
        """
        top_sections: list[str] = []

        # --- Project Identity (always relevant) ---
        identity: list[str] = []
        if self.description:
            identity.append(f"Project description: {self.description}")
        if self.language:
            identity.append(f"Language: {self.language}")
        if self.framework:
            identity.append(f"Framework: {self.framework}")
        if self.documentation:
            identity.append(f"Documentation:\n{self.documentation}")
        if identity:
            top_sections.append("## Project Identity\n" + "\n".join(identity))

        # --- Knowledge Sources (reference documents) ---
        if self.sources:
            enabled_sources = [s for s in self.sources if s.content]
            if enabled_sources:
                per_source = _SOURCE_BUDGET_CHARS // len(enabled_sources)
                source_parts: list[str] = []
                for i, src in enumerate(enabled_sources, 1):
                    text = src.content[:per_source]
                    if len(src.content) > per_source:
                        text += "\n... (truncated)"
                    source_parts.append(f"### [{i}] {src.title}\n{text}")
                insert_pos = 1 if identity else 0
                top_sections.insert(
                    insert_pos,
                    "## Knowledge Sources\n" + "\n\n".join(source_parts),
                )

        # --- Technical Details (relevant for coding/technical tasks) ---
        tech: list[str] = []
        if self.conventions:
            items = "\n".join(f"  - {c}" for c in self.conventions)
            tech.append(f"Conventions:\n{items}")
        if self.patterns:
            items = "\n".join(f"  - {p}" for p in self.patterns)
            tech.append(f"Architectural patterns:\n{items}")
        if self.code_snippets:
            snippets = "\n---\n".join(self.code_snippets)
            tech.append(f"Code snippets:\n{snippets}")
        if self.test_framework:
            tech.append(f"Test framework: {self.test_framework}")
        if self.test_patterns:
            items = "\n".join(f"  - {t}" for t in self.test_patterns)
            tech.append(f"Test patterns:\n{items}")
        if tech:
            top_sections.append("## Technical Details\n" + "\n\n".join(tech))

        if not top_sections:
            return None

        rendered = "\n\n".join(top_sections)
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
    """Convert a CodebaseContext to a dict, filtering out empty/None fields.

    Sources are included with content truncated to prevent DB bloat in snapshots.
    """
    if ctx is None:
        return None
    raw = asdict(ctx)
    # Truncate source content for snapshots
    if raw.get("sources"):
        raw["sources"] = [
            {
                "title": s["title"],
                "content": s["content"][:_SNAPSHOT_SOURCE_CONTENT_CHARS],
                "source_type": s["source_type"],
            }
            for s in raw["sources"]
        ]
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


def codebase_context_from_kernel(resolved: dict | None) -> CodebaseContext | None:
    """Build a CodebaseContext from a kernel Knowledge Base resolution result.

    Maps kernel profile identity fields + metadata_json + sources → CodebaseContext.
    The ``resolved`` dict comes from ``KnowledgeRepository.resolve()`` and has the shape:
    ``{"profile": {...}, "metadata": {...}, "auto_detected": {...}, "sources": [...]}``.

    Fields ``documentation`` and ``code_snippets`` are deprecated in the kernel model
    (replaced by Knowledge Sources). They are not populated from kernel data.
    """
    if not resolved:
        return None
    profile = resolved.get("profile", {})
    metadata = resolved.get("metadata", {})
    sources_raw = resolved.get("sources", [])

    ctx = CodebaseContext(
        language=profile.get("language"),
        framework=profile.get("framework"),
        description=profile.get("description"),
        test_framework=profile.get("test_framework"),
        conventions=metadata.get("conventions", []),
        patterns=metadata.get("patterns", []),
        test_patterns=metadata.get("test_patterns", []),
    )

    if sources_raw:
        ctx.sources = [
            SourceDocument(
                title=s.get("title", ""),
                content=s.get("content", ""),
                source_type=s.get("source_type", "document"),
            )
            for s in sources_raw
            if s.get("title") and s.get("content")
        ]

    # Return None if every field is empty
    if not any(getattr(ctx, f.name) for f in CodebaseContext.__dataclass_fields__.values()):
        return None
    return ctx


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

    # Parse sources list: list of dicts → list of SourceDocument
    sources_raw = filtered.pop("sources", None)
    if sources_raw and isinstance(sources_raw, list):
        sources = []
        for item in sources_raw:
            if isinstance(item, dict) and item.get("title") and item.get("content"):
                sources.append(SourceDocument(
                    title=str(item["title"]),
                    content=str(item["content"]),
                    source_type=str(item.get("source_type", "document")),
                ))
        if sources:
            filtered["sources"] = sources

    return CodebaseContext(**filtered)
