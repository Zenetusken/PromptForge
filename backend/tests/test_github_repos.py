"""Tests for bounded _repo_cache in github_repos router (Task 9)."""
import time
from importlib import reload

import pytest


def _get_module():
    import app.routers.github_repos as m
    return reload(m)


def test_repo_cache_bounded():
    """Filling cache beyond MAX_REPO_CACHE_SIZE and evicting keeps it within bounds."""
    m = _get_module()
    cap = m.MAX_REPO_CACHE_SIZE

    # Overfill by 10
    for i in range(cap + 10):
        m._repo_cache[f"session-{i}"] = (time.time(), [])

    m._evict_repo_cache_if_full()

    assert len(m._repo_cache) <= cap, (
        f"Cache should be <= {cap} after eviction, got {len(m._repo_cache)}"
    )


def test_repo_cache_evicts_oldest():
    """Eviction removes the oldest (insertion-order first) entries."""
    m = _get_module()
    cap = m.MAX_REPO_CACHE_SIZE

    # Fill exactly to cap
    for i in range(cap):
        m._repo_cache[f"session-{i}"] = (time.time(), [])

    # Add one more new entry — now over cap
    m._repo_cache["session-new"] = (time.time(), [])
    m._evict_repo_cache_if_full()

    assert "session-0" not in m._repo_cache, "Oldest entry 'session-0' should have been evicted"
    assert "session-new" in m._repo_cache, "Newest entry 'session-new' should still be present"
