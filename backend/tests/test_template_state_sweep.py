"""Task 25 ward: state='template' must not appear in write-side taxonomy literals.

Historical reads remain tolerated (see audit_log._LegacyClusterState and
taxonomy/event_logger). This test guards against regression of the write-side
sweep: any new SELECT/filter/dict literal that treats 'template' as a live
cluster state should fail here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Files swept in Task 25. Any of these listing 'template' as a state literal
# is a regression.
SWEPT_FILES = [
    "backend/app/services/taxonomy/engine.py",
    "backend/app/services/taxonomy/matching.py",
    "backend/app/services/taxonomy/family_ops.py",
    "backend/app/services/taxonomy/quality.py",
    "backend/app/schemas/clusters.py",
]

# Matches a state.in_([...]) list or _states = [...] list that contains 'template'.
# Keeps us from false-positiving on docstrings or comments that reference the
# historical state name for documentation purposes.
_STATE_LIST_RE = re.compile(
    r"""state[^\n]{0,16}\.in_\(\s*\[[^\]]*['"]template['"][^\]]*\]""",
    re.IGNORECASE,
)
_CANDIDATE_STATES_RE = re.compile(
    r"""_?candidate_states\s*=\s*\[[^\]]*['"]template['"][^\]]*\]""",
    re.IGNORECASE,
)
_COUNTER_RE = re.compile(r"""state_counts\.get\(\s*['"]template['"]""")
_DICT_ENTRY_RE = re.compile(r"""['"]template['"]\s*:\s*template\b""")

# Pydantic Literal containing 'template' in a write-side schema is a regression.
_LITERAL_RE = re.compile(
    r"""Literal\[[^\]]*['"]template['"][^\]]*\]""",
    re.IGNORECASE,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("relpath", SWEPT_FILES)
def test_no_template_state_in_write_side(relpath: str) -> None:
    src = (REPO_ROOT / relpath).read_text()
    assert not _STATE_LIST_RE.search(src), (
        f"{relpath}: found a state.in_([...]) list containing 'template'. "
        "Templates are now a separate table — remove the literal. See Task 25."
    )
    assert not _CANDIDATE_STATES_RE.search(src), (
        f"{relpath}: found a _candidate_states list containing 'template'."
    )
    assert not _COUNTER_RE.search(src), (
        f"{relpath}: found a dead state_counts.get('template', ...) counter."
    )
    assert not _DICT_ENTRY_RE.search(src), (
        f"{relpath}: found a dead 'template': template dict entry."
    )
    assert not _LITERAL_RE.search(src), (
        f"{relpath}: found a Pydantic Literal containing 'template'. "
        "State enum no longer includes template."
    )


def test_cluster_node_counts_no_template_field() -> None:
    """Response schema dropped the template counter."""
    from app.schemas.clusters import ClusterNodeCounts

    counts = ClusterNodeCounts()
    # Either the field is removed entirely or defaults to 0 AND is absent from
    # dumped output. Prefer full removal.
    assert not hasattr(counts, "template"), (
        "ClusterNodeCounts.template must be removed — the engine no longer "
        "emits a template count and the frontend no longer reads it."
    )
