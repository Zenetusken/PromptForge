"""Prompt injection detection middleware (warn-only).

PromptForge is a prompt optimizer — it intentionally processes arbitrary
prompt text.  This middleware does NOT block requests.  It:

1. Strips null bytes and control characters from the request body
2. Pattern-matches known injection techniques
3. Logs warnings for monitoring
4. Adds a warning to the response headers when patterns are detected

The caller (optimize router) can read the warning and emit it as an SSE event.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that suggest prompt injection attempts (compiled once)
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an|in)\s+", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\|?system\|?>", re.I),
    re.compile(r"\[INST\]", re.I),
    re.compile(r"###\s*(system|instruction|admin)", re.I),
]

# Control characters to strip (except common whitespace)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text: str) -> tuple[str, list[str]]:
    """Sanitize input text and return (cleaned_text, warnings).

    Warnings are human-readable strings describing detected patterns.
    The text is always returned — never blocked.
    """
    warnings: list[str] = []

    # Strip null bytes and control characters
    cleaned = _CONTROL_CHAR_RE.sub("", text)
    if cleaned != text:
        warnings.append("Control characters were stripped from input")
        logger.warning("Stripped control characters from prompt input")

    # Check for injection patterns
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            warnings.append(f"Potential prompt injection pattern detected: '{match.group()}'")
            logger.warning("Injection pattern detected in input: %s", match.group())

    return cleaned, warnings
