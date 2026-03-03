"""Prompt structure extraction — detects sections and template variables.

Python port of frontend/src/lib/utils/promptParser.ts.
Pure regex-based, no LLM calls. Runs in microseconds.
"""

import re

# ---------------------------------------------------------------------------
# Variable extraction
# ---------------------------------------------------------------------------

_DOUBLE_BRACE_RE = re.compile(r"\{\{\s*(\w[\w\s.\-]*?)\s*\}\}")
_SINGLE_BRACE_RE = re.compile(r"\{\s*(\w[\w\s.\-]*?)\s*\}")


def extract_variables(text: str) -> list[dict]:
    """Extract template variables from prompt text.

    Recognizes ``{{variable_name}}`` and ``{variable_name}`` patterns.
    Skips ``${var}`` (JS template literals) and empty braces ``{}``.

    Returns a list of dicts: ``[{"name": "var_name", "occurrences": 2}]``.
    """
    if not text:
        return []

    counts: dict[str, int] = {}

    # Double-brace variables (higher priority)
    for match in _DOUBLE_BRACE_RE.finditer(text):
        name = match.group(1).strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1

    # Single-brace variables (only if not inside a double-brace)
    for match in _SINGLE_BRACE_RE.finditer(text):
        name = match.group(1).strip()
        if not name:
            continue
        idx = match.start()
        # Skip if inside a double brace (already captured)
        if idx > 0 and text[idx - 1] == "{":
            continue
        end = idx + len(match.group(0))
        if end < len(text) and text[end] == "}":
            continue
        # Skip JS template literals: ${var}
        if idx > 0 and text[idx - 1] == "$":
            continue
        counts[name] = counts.get(name, 0) + 1

    return [{"name": name, "occurrences": count} for name, count in counts.items()]


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^#{1,3}\s*role\b", re.IGNORECASE), "role"),
    (re.compile(r"^role\s*:", re.IGNORECASE), "role"),
    (re.compile(r"^you\s+are\b", re.IGNORECASE), "role"),
    (re.compile(r"^act\s+as\b", re.IGNORECASE), "role"),
    (re.compile(r"^#{1,3}\s*context\b", re.IGNORECASE), "context"),
    (re.compile(r"^context\s*:", re.IGNORECASE), "context"),
    (re.compile(r"^background\s*:", re.IGNORECASE), "context"),
    (re.compile(r"^#{1,3}\s*(?:steps|instructions|procedure)\b", re.IGNORECASE), "steps"),
    (re.compile(r"^steps\s*:", re.IGNORECASE), "steps"),
    (re.compile(r"^instructions\s*:", re.IGNORECASE), "steps"),
    (re.compile(r"^#{1,3}\s*(?:constraints?|rules?|requirements?)\b", re.IGNORECASE), "constraints"),
    (re.compile(r"^constraints?\s*:", re.IGNORECASE), "constraints"),
    (re.compile(r"^rules?\s*:", re.IGNORECASE), "constraints"),
    (re.compile(r"^do\s+not\b", re.IGNORECASE), "constraints"),
    (re.compile(r"^#{1,3}\s*(?:examples?|sample)\b", re.IGNORECASE), "examples"),
    (re.compile(r"^examples?\s*:", re.IGNORECASE), "examples"),
    (re.compile(r"^#{1,3}\s*(?:output|response|format)\b", re.IGNORECASE), "output"),
    (re.compile(r"^output\s*(?:format)?\s*:", re.IGNORECASE), "output"),
    (re.compile(r"^response\s*(?:format)?\s*:", re.IGNORECASE), "output"),
    (re.compile(r"^#{1,3}\s*(?:task|objective|goal)\b", re.IGNORECASE), "task"),
    (re.compile(r"^task\s*:", re.IGNORECASE), "task"),
    (re.compile(r"^objective\s*:", re.IGNORECASE), "task"),
]

_EXPLICIT_HEADER_RE = re.compile(r"^#{1,3}\s|^\w[\w\s]*:\s*")

_LABEL_STRIP_HEADING = re.compile(r"^#{1,3}\s*")
_LABEL_STRIP_COLON = re.compile(r":\s*$")


def detect_sections(text: str) -> list[dict]:
    """Detect structural sections in prompt text.

    Returns detected sections with their line numbers and types.
    Lines immediately following a heading/colon section (before the next blank
    line) are treated as body text and not matched as new sections.

    Returns: ``[{"label": "Role", "line_number": 1, "type": "role"}]``
    """
    if not text:
        return []

    lines = text.split("\n")
    sections: list[dict] = []
    in_section_body = False

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()

        # Blank lines reset "in body" state
        if not line:
            in_section_body = False
            continue

        # If we're in a section body, skip implicit pattern matches
        # but still detect explicit heading/colon patterns
        is_explicit_header = bool(_EXPLICIT_HEADER_RE.match(line))
        if in_section_body and not is_explicit_header:
            continue

        for pattern, section_type in _SECTION_PATTERNS:
            if pattern.search(line):
                label = _LABEL_STRIP_HEADING.sub("", line)
                label = _LABEL_STRIP_COLON.sub("", label)
                sections.append({
                    "label": label,
                    "line_number": i + 1,
                    "type": section_type,
                })
                in_section_body = True
                break  # Only match the first pattern per line

    return sections


# ---------------------------------------------------------------------------
# Combined extraction
# ---------------------------------------------------------------------------


def extract_prompt_structure(text: str) -> dict:
    """Extract both sections and variables from prompt text.

    Returns: ``{"sections": [...], "variables": [...]}``
    """
    return {
        "sections": detect_sections(text),
        "variables": extract_variables(text),
    }
