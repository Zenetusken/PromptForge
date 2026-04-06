"""Tests for HeuristicScorer — TDD: tests written before implementation."""

from app.services.heuristic_scorer import HeuristicScorer

# ---------------------------------------------------------------------------
# heuristic_structure
# ---------------------------------------------------------------------------


def test_structure_score_with_headers() -> None:
    """Prompt with headers and lists should score > 5.0."""
    prompt = (
        "## Task\n"
        "Summarize the following document.\n\n"
        "## Requirements\n"
        "- Be concise\n"
        "- Use bullet points\n"
        "- Include key facts\n\n"
        "## Output format\n"
        "Return a JSON object with a 'summary' key."
    )
    score = HeuristicScorer.heuristic_structure(prompt)
    assert score > 5.0


def test_structure_score_wall_of_text() -> None:
    """Plain unstructured text should score < 5.0."""
    prompt = (
        "please summarize this document for me and make it short and "
        "also make sure to include the most important points and keep it readable"
    )
    score = HeuristicScorer.heuristic_structure(prompt)
    assert score < 5.0


# ---------------------------------------------------------------------------
# heuristic_conciseness
# ---------------------------------------------------------------------------


def test_conciseness_verbose() -> None:
    """Filler-heavy prompt should score < 6.0."""
    prompt = (
        "Please note that it is very important that you make sure to "
        "basically just essentially try to sort of generally summarize "
        "the text in a way that is kind of helpful and perhaps useful "
        "to the reader as much as possible."
    )
    score = HeuristicScorer.heuristic_conciseness(prompt)
    assert score < 6.0


def test_conciseness_tight() -> None:
    """Concise, non-repetitive prompt should score > 5.0."""
    prompt = "Summarize the document. Output JSON with keys: title, summary, keywords."
    score = HeuristicScorer.heuristic_conciseness(prompt)
    assert score > 5.0


# ---------------------------------------------------------------------------
# heuristic_specificity
# ---------------------------------------------------------------------------


def test_specificity_with_constraints() -> None:
    """Constraint-rich prompt should score > 5.0."""
    prompt = (
        "You must return a JSON object. "
        "The function shall raise ValueError when input is None. "
        "It should handle strings of type str and integers of type int. "
        "Format: {result: string, count: number}. "
        "For example: {result: 'hello', count: 3}. "
        "The output must contain at least 3 items."
    )
    score = HeuristicScorer.heuristic_specificity(prompt)
    assert score > 5.0
