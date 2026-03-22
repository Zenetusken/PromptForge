"""Tests for synthesis_match MCP tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp_server import synthesis_match
from app.schemas.mcp_models import MatchOutput

pytestmark = pytest.mark.asyncio


async def test_match_no_taxonomy_engine():
    """Returns match_level='none' when taxonomy engine is unavailable."""
    with patch("app.tools.match.get_taxonomy_engine", return_value=None):
        result = await synthesis_match(
            prompt_text="Write a Python function that validates email addresses.",
        )

    assert isinstance(result, MatchOutput)
    assert result.match_level == "none"
    assert result.similarity == 0.0
    assert result.cluster_id is None
    assert result.meta_patterns == []


async def test_match_rejects_short_prompt():
    """Prompts under 10 characters are rejected."""
    with pytest.raises(ValueError, match="too short"):
        await synthesis_match(prompt_text="short")


async def test_match_cluster_found():
    """Returns cluster info when a match is found."""
    mock_cluster = MagicMock()
    mock_cluster.id = "cluster-123"
    mock_cluster.label = "API validation patterns"
    mock_cluster.preferred_strategy = "structured-output"

    mock_pattern = MagicMock()
    mock_pattern.id = "mp-001"
    mock_pattern.pattern_text = "Use type hints for validation"
    mock_pattern.source_count = 5

    mock_result = MagicMock()
    mock_result.match_level = "cluster"
    mock_result.similarity = 0.85
    mock_result.cluster = mock_cluster
    mock_result.meta_patterns = [mock_pattern]
    mock_result.taxonomy_breadcrumb = ["coding", "backend", "validation"]

    with (
        patch("app.tools.match.get_taxonomy_engine", return_value=MagicMock()),
        patch("app.services.embedding_service.EmbeddingService"),
        patch("app.services.taxonomy.matching.match_prompt", new_callable=AsyncMock, return_value=mock_result),
        patch("app.tools.match.async_session_factory") as mock_factory,
    ):
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await synthesis_match(
            prompt_text="Write a Python function that validates email addresses using regex.",
        )

    assert result.match_level == "cluster"
    assert result.similarity == 0.85
    assert result.cluster_id == "cluster-123"
    assert result.cluster_label == "API validation patterns"
    assert result.recommended_strategy == "structured-output"
    assert len(result.meta_patterns) == 1
    assert result.meta_patterns[0].id == "mp-001"
    assert result.taxonomy_breadcrumb == ["coding", "backend", "validation"]


async def test_match_no_match_returned():
    """Returns match_level='none' when match_prompt finds nothing."""
    mock_result = MagicMock()
    mock_result.match_level = "none"
    mock_result.similarity = 0.3
    mock_result.cluster = None
    mock_result.meta_patterns = []
    mock_result.taxonomy_breadcrumb = []

    with (
        patch("app.tools.match.get_taxonomy_engine", return_value=MagicMock()),
        patch("app.services.embedding_service.EmbeddingService"),
        patch("app.services.taxonomy.matching.match_prompt", new_callable=AsyncMock, return_value=mock_result),
        patch("app.tools.match.async_session_factory") as mock_factory,
    ):
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await synthesis_match(
            prompt_text="A completely novel prompt that matches nothing in the taxonomy.",
        )

    assert result.match_level == "none"
    assert result.similarity == 0.3
