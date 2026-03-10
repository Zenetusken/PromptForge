"""Tests for the rewritten explore phase (semantic retrieval + single-shot synthesis)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.codebase_explorer import (
    CodebaseContext,
    _deduplicate_files,
    _get_anchor_paths,
    _keyword_fallback,
)
from app.services.repo_index_service import IndexStatus, RankedFile


class TestAnchorPaths:
    """Test deterministic anchor file detection."""

    def test_finds_readme(self):
        tree = [{"path": "README.md"}, {"path": "src/main.py"}]
        anchors = _get_anchor_paths(tree)
        assert "README.md" in anchors

    def test_finds_manifests(self):
        tree = [
            {"path": "package.json"},
            {"path": "Dockerfile"},
            {"path": "src/index.ts"},
        ]
        anchors = _get_anchor_paths(tree)
        assert "package.json" in anchors
        assert "Dockerfile" in anchors

    def test_ignores_non_anchor_files(self):
        tree = [{"path": "src/utils.py"}, {"path": "tests/test_foo.py"}]
        anchors = _get_anchor_paths(tree)
        assert len(anchors) == 0

    def test_finds_nested_anchor(self):
        """Anchor detection uses filename, not full path."""
        tree = [{"path": "docs/README.md"}]
        anchors = _get_anchor_paths(tree)
        assert "docs/README.md" in anchors


class TestDeduplicateFiles:
    """Test file deduplication and capping."""

    def test_basic_dedup(self):
        ranked = [
            RankedFile(path="src/auth.py", score=0.9),
            RankedFile(path="src/main.py", score=0.8),
        ]
        anchors = ["README.md", "package.json"]
        result = _deduplicate_files(ranked, anchors, cap=10)

        # Anchors first, then ranked
        assert result[0] == "README.md"
        assert result[1] == "package.json"
        assert "src/auth.py" in result
        assert "src/main.py" in result

    def test_dedup_overlap(self):
        """Overlapping files between ranked and anchors are deduplicated."""
        ranked = [
            RankedFile(path="README.md", score=0.9),  # also an anchor
            RankedFile(path="src/auth.py", score=0.8),
        ]
        anchors = ["README.md"]
        result = _deduplicate_files(ranked, anchors, cap=10)

        # README.md should only appear once
        assert result.count("README.md") == 1
        assert len(result) == 2

    def test_cap_enforced(self):
        ranked = [RankedFile(path=f"file_{i}.py", score=0.5) for i in range(50)]
        anchors = ["README.md"]
        result = _deduplicate_files(ranked, anchors, cap=5)
        assert len(result) == 5


class TestKeywordFallback:
    """Test keyword-based file ranking."""

    def test_matches_keywords_in_path(self):
        tree = [
            {"path": "src/auth/middleware.py", "sha": "a", "size_bytes": 100},
            {"path": "src/database.py", "sha": "b", "size_bytes": 100},
            {"path": "tests/test_auth.py", "sha": "c", "size_bytes": 100},
        ]
        results = _keyword_fallback(tree, "authentication middleware handler")

        # auth/middleware should score highest
        assert len(results) > 0
        paths = [r.path for r in results]
        assert "src/auth/middleware.py" in paths

    def test_empty_prompt(self):
        tree = [{"path": "src/main.py", "sha": "a", "size_bytes": 100}]
        results = _keyword_fallback(tree, "")
        assert results == []

    def test_no_matches(self):
        tree = [{"path": "src/main.py", "sha": "a", "size_bytes": 100}]
        results = _keyword_fallback(tree, "authentication")
        assert results == []

    def test_stopwords_filtered(self):
        tree = [
            {"path": "src/the_handler.py", "sha": "a", "size_bytes": 100},
            {"path": "src/auth.py", "sha": "b", "size_bytes": 100},
        ]
        # "the" is a stopword, "auth" is a keyword
        results = _keyword_fallback(tree, "the auth handler")
        paths = [r.path for r in results]
        assert "src/auth.py" in paths


class TestExploreFlow:
    """Test the full explore flow with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_immediately(self):
        """Cached result is returned without any GitHub or LLM calls."""
        from app.services.codebase_explorer import run_explore

        cached_result = {
            "tech_stack": ["Python"],
            "key_files_read": ["main.py"],
            "relevant_snippets": [],
            "observations": ["cached"],
            "grounding_notes": [],
            "coverage_pct": 10,
            "files_read_count": 1,
            "explore_quality": "complete",
        }

        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=cached_result)

        mock_provider = MagicMock()

        with (
            patch("app.services.codebase_explorer.get_cache", return_value=mock_cache),
            patch("anyio.to_thread.run_sync", new_callable=AsyncMock),  # branch check
        ):
            events = []
            async for event in run_explore(
                provider=mock_provider,
                raw_prompt="test prompt",
                repo_full_name="owner/repo",
                repo_branch="main",
                github_token="fake-token",
            ):
                events.append(event)

        # Should have explore_result event with cached data
        result_events = [e for e in events if e[0] == "explore_result"]
        assert len(result_events) == 1
        assert result_events[0][1] == cached_result

        # LLM should NOT have been called
        mock_provider.complete_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_resolution_error(self):
        """Missing token yields a failed explore_result."""
        from app.services.codebase_explorer import run_explore

        mock_provider = MagicMock()

        events = []
        async for event in run_explore(
            provider=mock_provider,
            raw_prompt="test",
            repo_full_name="owner/repo",
            repo_branch="main",
            # No token or session_id provided
        ):
            events.append(event)

        result_events = [e for e in events if e[0] == "explore_result"]
        assert len(result_events) == 1
        assert result_events[0][1]["explore_quality"] == "failed"
        assert result_events[0][1]["explore_failed"] is True

    @pytest.mark.asyncio
    async def test_sse_event_sequence(self):
        """Explore emits the expected SSE event types in order."""
        from app.services.codebase_explorer import run_explore

        mock_provider = MagicMock()
        mock_provider.complete_json = AsyncMock(return_value={
            "tech_stack": ["Python"],
            "key_files_read": ["main.py"],
            "relevant_code_snippets": [],
            "codebase_observations": ["test observation"],
            "prompt_grounding_notes": ["test grounding"],
        })

        mock_tree = [
            {"path": "README.md", "sha": "abc", "size_bytes": 500},
            {"path": "main.py", "sha": "def", "size_bytes": 200},
        ]

        mock_index_status = IndexStatus(status="none")

        with (
            patch("anyio.to_thread.run_sync", new_callable=AsyncMock),
            patch("app.services.codebase_explorer.get_cache", return_value=None),
            patch(
                "app.services.codebase_explorer.get_repo_tree",
                new_callable=AsyncMock,
                return_value=mock_tree,
            ),
            patch(
                "app.services.codebase_explorer.get_repo_index_service"
            ) as mock_idx_svc,
            patch(
                "app.services.codebase_explorer.read_file_content",
                new_callable=AsyncMock,
                return_value="# README\nHello",
            ),
        ):
            mock_idx_svc.return_value.get_index_status = AsyncMock(
                return_value=mock_index_status
            )

            events = []
            async for event in run_explore(
                provider=mock_provider,
                raw_prompt="test prompt",
                repo_full_name="owner/repo",
                repo_branch="main",
                github_token="fake-token",
            ):
                events.append(event)

        event_types = [e[0] for e in events]

        # Should have progress events and final result
        assert "agent_text" in event_types
        assert "tool_call" in event_types
        assert "explore_result" in event_types

        # explore_result should be last
        assert event_types[-1] == "explore_result"

        # The result should have the expected structure
        result = events[-1][1]
        assert "tech_stack" in result
        assert "key_files_read" in result
        assert "observations" in result
        assert "explore_quality" in result


class TestCodebaseContext:
    """Test CodebaseContext dataclass."""

    def test_default_values(self):
        ctx = CodebaseContext()
        assert ctx.repo == ""
        assert ctx.branch == "main"
        assert ctx.tech_stack == []
        assert ctx.explore_quality == "complete"

    def test_custom_values(self):
        ctx = CodebaseContext(
            repo="owner/repo",
            branch="develop",
            tech_stack=["Python", "FastAPI"],
            explore_quality="partial",
        )
        assert ctx.repo == "owner/repo"
        assert ctx.branch == "develop"
        assert len(ctx.tech_stack) == 2
