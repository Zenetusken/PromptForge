"""Tests for taxonomy constants."""

from app.services.taxonomy._constants import EXCLUDED_STRUCTURAL_STATES


def test_excluded_structural_states_contains_required():
    """The constant must contain domain, archived, and project."""
    assert "domain" in EXCLUDED_STRUCTURAL_STATES
    assert "archived" in EXCLUDED_STRUCTURAL_STATES
    assert "project" in EXCLUDED_STRUCTURAL_STATES


def test_excluded_structural_states_is_frozenset():
    """Must be frozenset (immutable) to prevent accidental mutation."""
    assert isinstance(EXCLUDED_STRUCTURAL_STATES, frozenset)


def test_excluded_structural_states_is_list_compatible():
    """Can be passed to SQLAlchemy .notin_() which expects a sequence."""
    as_list = list(EXCLUDED_STRUCTURAL_STATES)
    assert len(as_list) == 3
