"""Tests for MCP server tool functions — all 8 tools exercised via direct calls."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import OptimizationStatus
from app.models.optimization import Optimization
from app.repositories.optimization import OptimizationRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
async def mcp_session(db_engine):
    """Patch _repo_session to use the test in-memory database.

    Yields a session that can be used to seed test data.
    """
    factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    @asynccontextmanager
    async def _fake_repo_session():
        async with factory() as session:
            yield OptimizationRepository(session), session

    with patch("app.mcp_server._repo_session", _fake_repo_session):
        async with factory() as session:
            yield session


async def _seed(session: AsyncSession, **overrides) -> Optimization:
    """Insert an optimization record for testing."""
    defaults = {
        "id": "mcp-001",
        "raw_prompt": "test prompt",
        "status": OptimizationStatus.COMPLETED,
        "task_type": "coding",
        "overall_score": 0.8,
        "optimized_prompt": "better prompt",
    }
    defaults.update(overrides)
    opt = Optimization(**defaults)
    session.add(opt)
    await session.commit()
    return opt


# ---------------------------------------------------------------------------
# TestPromptforgeOptimize
# ---------------------------------------------------------------------------

class TestPromptforgeOptimize:
    @pytest.mark.asyncio
    async def test_empty_prompt_returns_error(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        result = await promptforge_optimize(prompt="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_whitespace_prompt_returns_error(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        result = await promptforge_optimize(prompt="   ")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_prompt_too_long_returns_error(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        result = await promptforge_optimize(prompt="x" * 100_001)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_strategy_returns_error(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        result = await promptforge_optimize(prompt="test", strategy="bogus")
        assert "error" in result
        assert "bogus" in result["error"]

    @pytest.mark.asyncio
    async def test_happy_path_with_mocked_pipeline(self, mcp_session):
        """Successfully runs pipeline and returns result with scores."""
        from app.mcp_server import promptforge_optimize
        from app.services.pipeline import PipelineResult

        mock_result = PipelineResult(
            task_type="coding",
            complexity="medium",
            weaknesses=["vague"],
            strengths=["clear intent"],
            optimized_prompt="Better prompt text",
            framework_applied="persona-assignment",
            changes_made=["Added role context"],
            optimization_notes="Improved clarity",
            clarity_score=0.9,
            specificity_score=0.8,
            structure_score=0.7,
            faithfulness_score=0.85,
            overall_score=0.81,
            is_improvement=True,
            verdict="Improved",
            duration_ms=1500,
            model_used="test-model",
            strategy_reasoning="Best fit",
            strategy_confidence=0.9,
        )

        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ):
            result = await promptforge_optimize(
                prompt="Write a function",
                project="test-project",
                tags=["coding"],
                title="Test optimization",
            )

        assert "error" not in result
        assert result["status"] == "completed"
        assert result["id"]  # Should have a UUID
        assert result["optimized_prompt"] == "Better prompt text"

    @pytest.mark.asyncio
    async def test_happy_path_with_strategy_override(self, mcp_session):
        """Strategy override is passed through to run_pipeline."""
        from app.mcp_server import promptforge_optimize
        from app.services.pipeline import PipelineResult

        mock_result = PipelineResult(
            task_type="general",
            complexity="low",
            weaknesses=[],
            strengths=[],
            optimized_prompt="Better",
            framework_applied="chain-of-thought",
            changes_made=[],
            optimization_notes="",
            clarity_score=0.8,
            specificity_score=0.7,
            structure_score=0.6,
            faithfulness_score=0.8,
            overall_score=0.75,
            is_improvement=True,
            verdict="OK",
            duration_ms=500,
            model_used="m",
            strategy_reasoning="r",
            strategy_confidence=0.9,
        )

        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            result = await promptforge_optimize(prompt="test", strategy="chain-of-thought")

        assert "error" not in result
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("strategy_override") == "chain-of-thought"

    @pytest.mark.asyncio
    async def test_pipeline_error_returns_error_dict(self, mcp_session):
        """When pipeline raises, returns error dict with id and status."""
        from app.mcp_server import promptforge_optimize

        with patch(
            "app.mcp_server.run_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM failed"),
        ):
            result = await promptforge_optimize(prompt="test prompt")

        assert result["error"] == "LLM failed"
        assert result["status"] == "error"
        assert "id" in result


# ---------------------------------------------------------------------------
# TestPromptforgeGet
# ---------------------------------------------------------------------------

class TestPromptforgeGet:
    @pytest.mark.asyncio
    async def test_found(self, mcp_session):
        await _seed(mcp_session)
        from app.mcp_server import promptforge_get
        result = await promptforge_get("mcp-001")
        assert result["id"] == "mcp-001"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_not_found(self, mcp_session):
        from app.mcp_server import promptforge_get
        result = await promptforge_get("nonexistent")
        assert "error" in result


# ---------------------------------------------------------------------------
# TestPromptforgeList
# ---------------------------------------------------------------------------

class TestPromptforgeList:
    @pytest.mark.asyncio
    async def test_basic_list(self, mcp_session):
        await _seed(mcp_session, id="a")
        await _seed(mcp_session, id="b")
        from app.mcp_server import promptforge_list
        result = await promptforge_list()
        assert result["total"] == 2
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_limit_clamped_to_100(self, mcp_session):
        from app.mcp_server import promptforge_list
        # Should not crash even with limit > 100
        result = await promptforge_list(limit=200)
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_project(self, mcp_session):
        await _seed(mcp_session, id="a", project="proj-a")
        await _seed(mcp_session, id="b", project="proj-b")
        from app.mcp_server import promptforge_list
        result = await promptforge_list(project="proj-a")
        assert result["total"] == 1


# ---------------------------------------------------------------------------
# TestPromptforgeGetByProject
# ---------------------------------------------------------------------------

class TestPromptforgeGetByProject:
    @pytest.mark.asyncio
    async def test_returns_project_items(self, mcp_session):
        await _seed(mcp_session, id="a", project="alpha")
        await _seed(mcp_session, id="b", project="beta")
        from app.mcp_server import promptforge_get_by_project
        result = await promptforge_get_by_project("alpha")
        assert result["project"] == "alpha"
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# TestPromptforgeSearch
# ---------------------------------------------------------------------------

class TestPromptforgeSearch:
    @pytest.mark.asyncio
    async def test_valid_search(self, mcp_session):
        await _seed(mcp_session, id="a", raw_prompt="optimize SQL query")
        await _seed(mcp_session, id="b", raw_prompt="write a poem")
        from app.mcp_server import promptforge_search
        result = await promptforge_search("SQL")
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_short_query_returns_error(self, mcp_session):
        from app.mcp_server import promptforge_search
        result = await promptforge_search("x")
        assert "error" in result


# ---------------------------------------------------------------------------
# TestPromptforgeTag
# ---------------------------------------------------------------------------

class TestPromptforgeTag:
    @pytest.mark.asyncio
    async def test_add_and_remove_tags(self, mcp_session):
        await _seed(mcp_session, id="t1", tags=json.dumps(["existing"]))
        from app.mcp_server import promptforge_tag
        result = await promptforge_tag("t1", add_tags=["new"], remove_tags=["existing"])
        assert result["tags"] == ["new"]

    @pytest.mark.asyncio
    async def test_not_found(self, mcp_session):
        from app.mcp_server import promptforge_tag
        result = await promptforge_tag("nonexistent", add_tags=["x"])
        assert "error" in result


# ---------------------------------------------------------------------------
# TestPromptforgeStats
# ---------------------------------------------------------------------------

class TestPromptforgeStats:
    @pytest.mark.asyncio
    async def test_empty_stats(self, mcp_session):
        from app.mcp_server import promptforge_stats
        result = await promptforge_stats()
        assert result["total_optimizations"] == 0

    @pytest.mark.asyncio
    async def test_with_data(self, mcp_session):
        await _seed(mcp_session, id="a", overall_score=0.8)
        from app.mcp_server import promptforge_stats
        result = await promptforge_stats()
        assert result["total_optimizations"] == 1


# ---------------------------------------------------------------------------
# TestPromptforgeDelete
# ---------------------------------------------------------------------------

class TestPromptforgeDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self, mcp_session):
        await _seed(mcp_session)
        from app.mcp_server import promptforge_delete
        result = await promptforge_delete("mcp-001")
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mcp_session):
        from app.mcp_server import promptforge_delete
        result = await promptforge_delete("nonexistent")
        assert "error" in result
