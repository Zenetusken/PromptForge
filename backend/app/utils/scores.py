"""Score normalization. DB stores 0.0-1.0, API/display uses 1-10 integers."""


def score_to_display(score: float | None) -> int | None:
    """Convert DB score (0.0-1.0) to display (1-10)."""
    if score is None:
        return None
    if score <= 1.0:
        return max(1, min(10, round(score * 10)))
    return max(1, min(10, round(score)))


def score_threshold_to_db(display_score: float) -> float:
    """Convert display score (1-10) to DB threshold (0.0-1.0)."""
    if display_score >= 1:
        return display_score / 10.0
    return display_score


def round_score(value: float | None, digits: int = 4) -> float | None:
    """Round a float score value, or return None."""
    if value is None:
        return None
    return round(value, digits)
