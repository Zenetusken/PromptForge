"""Shared text cleanup utilities for LLM output normalization.

Strips meta-commentary artifacts (preambles, code fences, headers) and
separates change rationale from optimized prompt content.  Used by the
sampling pipeline, MCP save_result, and REST passthrough save paths.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import re

__all__ = [
    "strip_meta_header",
    "split_prompt_and_changes",
    "sanitize_optimization_result",
    "title_case_label",
    "parse_domain",
]

# Words that should stay uppercase (acronyms, initialisms)
_UPPERCASE_WORDS = frozenset({
    "api", "css", "html", "js", "ts", "sql", "ui", "ux", "cli", "sdk",
    "ssr", "ssg", "jwt", "oauth", "crud", "rest", "graphql", "db", "ai",
    "llm", "mcp", "http", "https", "json", "yaml", "xml", "csv", "pdf",
    "aws", "gcp", "ci", "cd", "devops", "gpu", "cpu", "ram", "ssd",
})


def title_case_label(text: str) -> str:
    """Title-case a short label, preserving known acronyms.

    Examples:
        >>> title_case_label("design auth API service")
        'Design Auth API Service'
        >>> title_case_label("refactor CSS architecture")
        'Refactor CSS Architecture'
    """
    words: list[str] = []
    for w in text.split():
        if w.lower() in _UPPERCASE_WORDS:
            words.append(w.upper())
        else:
            words.append(w.capitalize())
    return " ".join(words)


def strip_meta_header(text: str) -> str:
    """Remove LLM-added preambles, meta-headers, and code fences from the prompt.

    LLMs in sampling/passthrough mode often:
    1. Add a preamble like "Here is the optimized prompt using..."
    2. Prepend a title like '# Optimized Prompt' before the actual content
    3. Wrap the entire prompt in a markdown code fence (```markdown ... ```)

    All are meta-commentary artifacts, not part of the prompt.
    """
    # 0. Strip preamble sentences like "Here is the optimized prompt..."
    text = re.sub(
        r"^(?:here\s+is|below\s+is)[^`\n]*(?:prompt|version)[^`\n]*:?\s*\n+",
        "", text, count=1, flags=re.IGNORECASE,
    )

    # 1. Strip markdown code fence wrapping the entire content.
    #    LLMs sometimes return: ```markdown\n<actual prompt>\n```
    stripped = text.strip()
    if re.match(r"^```(?:markdown|md)?\s*\n", stripped, re.IGNORECASE):
        # Remove opening fence
        stripped = re.sub(r"^```(?:markdown|md)?\s*\n", "", stripped, count=1, flags=re.IGNORECASE)
        # Remove closing fence (at end)
        stripped = re.sub(r"\n```\s*$", "", stripped)
        text = stripped

    # 2. Strip meta-header line
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines:
        first = lines[0].strip().lower().rstrip(":").rstrip()
        meta_headers = [
            "# optimized prompt", "## optimized prompt", "### optimized prompt",
            "# optimized version", "## optimized version", "### optimized version",
            "# improved prompt", "## improved prompt", "### improved prompt",
            "# rewritten prompt", "## rewritten prompt", "### rewritten prompt",
            "# enhanced prompt", "## enhanced prompt", "### enhanced prompt",
        ]
        if any(first == h for h in meta_headers):
            lines.pop(0)
            while lines and not lines[0].strip():
                lines.pop(0)

    # 3. Strip trailing closing fence + orphaned heading markers left by
    #    truncated LLM output (e.g., "```\n\n#" at the end).
    result = "\n".join(lines).rstrip()
    result = re.sub(r"\n```\s*$", "", result)           # trailing ```
    result = re.sub(r"\n#{1,3}\s*$", "", result.rstrip())  # trailing orphaned #/##/###
    return result


_DEFAULT_CHANGES = "Restructured with added specificity and constraints"

# Regex catches markdown headings at any level (#–####), bold markers,
# and plain label variants for changes sections.  Case-insensitive,
# multiline so ^ anchors to line starts.  Optional HR (---) prefix.
_CHANGES_RE = re.compile(
    r"^(?:---\s*\n)?"
    r"(?:"
    # Heading variants: # Changes, ## Changes Made, ### Summary of Changes, etc.
    # Word boundary (?:\s|$) prevents matching "Changelog", "Changed config", etc.
    r"#{1,4}\s+(?:Summary\s+of\s+)?(?:Changes?\s*(?:Made|Summary)?|What\s+Changed(?:\s+and\s+Why)?)(?:\s*$)"
    r"|"
    # Bold variants: **Changes**, **Changes Made**, etc.
    r"\*{2}(?:Summary\s+of\s+)?(?:Changes?\s*(?:Made|Summary)?|What\s+Changed(?:\s+and\s+Why)?)\*{2}"
    r"|"
    # Plain label: "Changes:" or "What changed:"
    r"(?:Changes|What\s+changed)\s*:"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

# Secondary metadata section the LLM may append after the prompt.
_APPLIED_PATTERNS_RE = re.compile(
    r"^(?:---\s*\n)?#{1,4}\s+Applied\s+Patterns",
    re.IGNORECASE | re.MULTILINE,
)


def split_prompt_and_changes(text: str) -> tuple[str, str]:
    """Split an LLM response into optimized prompt and changes summary.

    LLMs often merge their rationale (what changed and why) or
    ``## Applied Patterns`` notes into the optimized prompt text.
    This function detects section markers via regex and splits them
    out so ``changes_summary`` is separate from ``optimized_prompt``.

    Also strips meta-headers like '# Optimized Prompt'.

    Returns:
        (prompt_text, changes_summary) tuple.
    """
    changes_match = _CHANGES_RE.search(text)
    patterns_match = _APPLIED_PATTERNS_RE.search(text)

    # Determine the earliest metadata section — split there.
    split_pos: int | None = None
    changes_text = ""

    if changes_match and patterns_match:
        # Both present — split at whichever comes first
        if changes_match.start() <= patterns_match.start():
            split_pos = changes_match.start()
            changes_text = text[changes_match.end():].strip()
            # Trim Applied Patterns from the tail of changes_text
            ap_tail = _APPLIED_PATTERNS_RE.search(changes_text)
            if ap_tail:
                changes_text = changes_text[:ap_tail.start()].strip()
        else:
            split_pos = patterns_match.start()
            # Changes section is after Applied Patterns
            changes_text = text[changes_match.end():].strip()
    elif changes_match:
        split_pos = changes_match.start()
        changes_text = text[changes_match.end():].strip()
    elif patterns_match:
        split_pos = patterns_match.start()
        # No explicit changes section — just strip the Applied Patterns

    if split_pos is not None:
        prompt_part = text[:split_pos].rstrip()
        # Remove leading markdown decoration from changes
        changes_text = changes_text.lstrip("#").lstrip("*").strip()
        if changes_text:
            return strip_meta_header(prompt_part), changes_text[:500]
        if prompt_part.strip():
            return strip_meta_header(prompt_part), _DEFAULT_CHANGES

    return strip_meta_header(text), _DEFAULT_CHANGES


def sanitize_optimization_result(
    optimized_prompt: str,
    changes_summary: str,
) -> tuple[str, str]:
    """Post-process LLM output to separate leaked metadata sections.

    Even when the LLM returns structured JSON with separate fields, the
    ``optimized_prompt`` value may contain embedded ``## Changes`` or
    ``## Applied Patterns`` sections.  This function strips them and
    merges any extracted changes with the existing ``changes_summary``.

    Applied on ALL pipeline paths (internal, sampling, passthrough) as
    a defense-in-depth measure.

    Returns:
        (cleaned_prompt, changes_summary) tuple.
    """
    cleaned_prompt, extracted_changes = split_prompt_and_changes(optimized_prompt)

    # If we extracted real changes AND the existing summary is
    # empty or just the default placeholder, use the extracted text.
    if extracted_changes and extracted_changes != _DEFAULT_CHANGES:
        if not changes_summary or changes_summary == _DEFAULT_CHANGES:
            changes_summary = extracted_changes

    return cleaned_prompt, changes_summary


def parse_domain(raw: str | None) -> tuple[str, str | None]:
    """Parse a domain string into (primary, qualifier).

    Both primary and qualifier are **lowercased** to match domain node
    labels (which are always lowercase).

    Examples::

        parse_domain("backend")           → ("backend", None)
        parse_domain("Backend: Security") → ("backend", "security")
        parse_domain("REST API design")   → ("rest api design", None)
        parse_domain(None)                → ("general", None)

    Returns ``("general", None)`` for empty/None input.
    """
    if not raw or not raw.strip():
        return ("general", None)
    raw = raw.strip()
    if ":" in raw:
        primary, _, qualifier = raw.partition(":")
        return (primary.strip().lower(), qualifier.strip().lower() or None)
    return (raw.lower(), None)
