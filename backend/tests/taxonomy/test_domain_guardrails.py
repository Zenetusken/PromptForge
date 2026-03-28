"""Tests for domain stability guardrails in lifecycle operations."""

from __future__ import annotations

import pytest

from app.models import PromptCluster
from app.services.taxonomy.lifecycle import (
    GuardrailViolationError,
    _assert_domain_guardrails,
)


def _make_domain_node(label: str = "backend") -> PromptCluster:
    return PromptCluster(label=label, state="domain", domain=label, persistence=1.0)


def _make_cluster(label: str = "test") -> PromptCluster:
    return PromptCluster(label=label, state="active", domain="backend")


def test_retire_domain_raises():
    with pytest.raises(GuardrailViolationError, match="retire"):
        _assert_domain_guardrails("retire", _make_domain_node())


def test_merge_domain_raises():
    with pytest.raises(GuardrailViolationError, match="merge"):
        _assert_domain_guardrails("merge", _make_domain_node())


def test_color_assign_domain_raises():
    with pytest.raises(GuardrailViolationError, match="color_assign"):
        _assert_domain_guardrails("color_assign", _make_domain_node())


def test_non_domain_cluster_passes():
    for op in ("retire", "merge", "color_assign", "split", "emerge"):
        _assert_domain_guardrails(op, _make_cluster())


def test_unknown_operation_on_domain_passes():
    # Operations not in the violations map should pass through
    _assert_domain_guardrails("split", _make_domain_node())
    _assert_domain_guardrails("emerge", _make_domain_node())
