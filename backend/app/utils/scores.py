"""Score normalization utilities.

The application uses three score representations:

- **DB / LLM layer**: 0.0–1.0 floats (stored in SQLite, returned by the validator).
- **MCP tools**: 1–10 integers (``score_to_display``), suitable for quick textual summaries.
- **Frontend**: 0–100 integers (``normalizeScore`` in ``frontend/src/lib/utils/format.ts``),
  used in the web UI for user-facing score displays and color thresholds.
"""


def score_to_display(score: float | None) -> int | None:
    """Convert DB score (0.0-1.0) to display (1-10)."""
    if score is None:
        return None
    return max(1, min(10, round(score * 10)))


def score_threshold_to_db(display_score: float) -> float:
    """Convert display score (1-10) to DB threshold (0.0-1.0)."""
    return display_score / 10.0


def round_score(value: float | None, digits: int = 4) -> float | None:
    """Round a float score value, or return None."""
    if value is None:
        return None
    return round(value, digits)
