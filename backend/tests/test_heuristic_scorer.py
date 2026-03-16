"""Tests for HeuristicScorer — TDD: tests written before implementation."""

import pytest

from app.services.heuristic_scorer import HeuristicScorer

# ---------------------------------------------------------------------------
# apply_bias_correction
# ---------------------------------------------------------------------------


def test_applies_default_discount() -> None:
    """8.0 * 0.85 = 6.8 with default factor."""
    scores = {"clarity": 8.0, "specificity": 8.0}
    result = HeuristicScorer.apply_bias_correction(scores)
    assert result["clarity"] == pytest.approx(6.8, abs=0.01)
    assert result["specificity"] == pytest.approx(6.8, abs=0.01)


def test_custom_factor() -> None:
    """10.0 * 0.9 = 9.0 with explicit factor."""
    scores = {"clarity": 10.0}
    result = HeuristicScorer.apply_bias_correction(scores, factor=0.9)
    assert result["clarity"] == pytest.approx(9.0, abs=0.01)


def test_scores_clamped_to_minimum() -> None:
    """1.0 * 0.85 = 0.85 → clamped to 1.0."""
    scores = {"clarity": 1.0}
    result = HeuristicScorer.apply_bias_correction(scores, factor=0.85)
    assert result["clarity"] == pytest.approx(1.0, abs=0.01)


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


# ---------------------------------------------------------------------------
# detect_divergence
# ---------------------------------------------------------------------------


def test_divergence_detection() -> None:
    """Flags dimensions where |llm - heuristic| > 2.0."""
    llm_scores = {"clarity": 9.0, "specificity": 5.0, "structure": 8.0}
    heuristic_scores = {"clarity": 6.0, "specificity": 5.5, "structure": 5.5}
    diverged = HeuristicScorer.detect_divergence(llm_scores, heuristic_scores)
    assert "clarity" in diverged
    assert "specificity" not in diverged
    assert "structure" in diverged
