"""Handler for synthesis_explain MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Optimization
from app.schemas.mcp_models import ExplainResult

logger = logging.getLogger(__name__)

# Strategy names → lay-audience descriptions
_STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "auto": "automatically chose the best approach for this prompt",
    "chain-of-thought": "broke the request into clear, logical steps",
    "few-shot": "added concrete examples to guide the response",
    "meta-prompting": "restructured how the request communicates its goal",
    "role-playing": "gave the AI a specific expert perspective to work from",
    "structured-output": "organized the expected response into a clear format",
}

# Technical phrases → plain-English replacements (longest-first to avoid
# partial matches — e.g. "structured-output constraints" before "structured output").
# Each entry is (compiled regex, replacement).  Patterns use word boundaries
# so "token" won't match inside "tokenization".
_PLAIN_ENGLISH: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bstructured[- ]output constraints\b", re.I), "a clearer response format"),
    (re.compile(r"\bstructured[- ]output\b", re.I), "a clearer response format"),
    (re.compile(r"\brole framing\b", re.I), "a specific expert perspective"),
    (re.compile(r"\bchain[- ]of[- ]thought\b", re.I), "step-by-step reasoning"),
    (re.compile(r"\bfew[- ]shot examples?\b", re.I), "concrete examples"),
    (re.compile(r"\bmeta[- ]prompting\b", re.I), "clearer goal communication"),
    (re.compile(r"\bprompt engineering\b", re.I), "request improvement"),
    (re.compile(r"\btokens?\b", re.I), "words"),
    (re.compile(r"\bcontext window\b", re.I), "available space"),
    (re.compile(r"\bhallucinations?\b", re.I), "inaccuracies"),
    (re.compile(r"\bgrounding\b", re.I), "keeping responses factual"),
    (re.compile(r"\bembeddings?\b", re.I), "meaning representations"),
    (re.compile(r"\blatency\b", re.I), "response time"),
    (re.compile(r"\binference\b", re.I), "processing"),
]


def _to_plain_english(text: str) -> str:
    """Replace common technical jargon with plain-English equivalents."""
    result = text
    for pattern, replacement in _PLAIN_ENGLISH:
        result = pattern.sub(replacement, result)
    return result


_TABLE_SEP_RE = re.compile(r"^\|?[\s\-:|]+\|?$")
_TABLE_HEADER_RE = re.compile(r"^\|?\s*(change|what|modification)\s*\|", re.I)


def _extract_table_cells(text: str) -> list[str]:
    """Extract meaningful content from markdown table rows.

    Skips header rows, separator rows, and empty cells.  For rows with
    multiple columns (e.g. Change | Reason) joins them with " — ".
    """
    items: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or _TABLE_SEP_RE.match(stripped):
            continue
        if _TABLE_HEADER_RE.match(stripped):
            continue
        # Split pipe-delimited cells, strip markdown bold
        cells = [
            c.strip().strip("*").strip()
            for c in stripped.strip("|").split("|")
            if c.strip().strip("*").strip()
        ]
        if cells:
            items.append(" — ".join(cells))
    return items


def _build_changes(changes_summary: str | None) -> list[str]:
    """Extract 3-5 change bullets from changes_summary, rewritten in plain English."""
    if not changes_summary:
        return ["Made the request clearer and easier to follow"]

    # Detect markdown tables (pipe-delimited lines)
    if "|" in changes_summary and changes_summary.count("|") >= 4:
        lines = _extract_table_cells(changes_summary)
    else:
        # Split on common delimiters: numbered lists, bullet points, newlines
        lines = []
        for line in changes_summary.replace("\r\n", "\n").split("\n"):
            stripped = line.strip().lstrip("0123456789.-•*) ").strip()
            if stripped:
                lines.append(stripped)

    if not lines:
        return ["Made the request clearer and easier to follow"]

    # Rewrite each line in plain English and cap at 5
    plain = [_to_plain_english(line) for line in lines[:5]]

    # Pad to minimum 3 if needed
    if len(plain) < 3:
        defaults = [
            "Made the request clearer and more specific",
            "Improved the overall structure and flow",
            "Reduced ambiguity so the response stays on track",
        ]
        for d in defaults:
            if len(plain) >= 3:
                break
            if d not in plain:
                plain.append(d)

    return plain


def _build_summary(
    task_type: str | None,
    score_delta: float,
    strategy_desc: str,
) -> str:
    """Build a 1-2 sentence plain-English summary."""
    task = task_type or "general"
    task_label = task if task != "general" else "this"

    if score_delta > 0:
        direction = "improved"
        delta_str = f"by {score_delta:+.1f} points"
    elif score_delta < 0:
        direction = "adjusted"
        delta_str = f"({score_delta:+.1f} points)"
    else:
        direction = "refined"
        delta_str = "without changing the overall score"

    return (
        f"This optimization {direction} your {task_label} prompt {delta_str} "
        f"by using an approach that {strategy_desc}."
    )


async def handle_explain(
    optimization_id: str,
) -> ExplainResult:
    """Build a plain-English explanation from stored optimization fields."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Optimization).where(Optimization.id == optimization_id)
        )
        opt = result.scalar_one_or_none()

        if not opt:
            # Try trace_id fallback
            result = await db.execute(
                select(Optimization).where(
                    Optimization.trace_id == optimization_id
                )
            )
            opt = result.scalar_one_or_none()

        if not opt:
            raise ValueError(f"Optimization not found: {optimization_id}")

        if not opt.optimized_prompt:
            raise ValueError(
                f"Optimization {optimization_id} has no optimized prompt yet — "
                "it may still be in progress or only analyzed."
            )

        # Extract all needed fields while session is open
        opt_id = opt.id
        task_type = opt.task_type
        strategy_used = opt.strategy_used
        overall_score = opt.overall_score
        original_scores = opt.original_scores
        changes_summary = opt.changes_summary

    # Compute score delta (outside session — only uses extracted scalars)
    original_overall: float = 0.0
    if original_scores and isinstance(original_scores, dict):
        from app.schemas.pipeline_contracts import DIMENSION_WEIGHTS
        vals = {k: v for k, v in original_scores.items() if isinstance(v, (int, float))}
        if vals:
            original_overall = round(
                sum(vals.get(d, 5.0) * w for d, w in DIMENSION_WEIGHTS.items()), 2,
            )

    optimized_overall = overall_score or 0.0
    score_delta = round(optimized_overall - original_overall, 2)

    # Strategy description
    strategy_name = strategy_used or "auto"
    strategy_desc = _STRATEGY_DESCRIPTIONS.get(
        strategy_name, f"applied the '{strategy_name}' approach"
    )
    strategy_display = f"{strategy_name} — {strategy_desc}"

    # Build explanation
    summary = _build_summary(task_type, score_delta, strategy_desc)
    changes = _build_changes(changes_summary)

    logger.info(
        "synthesis_explain completed: id=%s delta=%+.2f",
        opt_id,
        score_delta,
    )

    return ExplainResult(
        summary=summary,
        changes=changes,
        strategy_used=strategy_display,
        score_delta=score_delta,
    )
