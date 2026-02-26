"""Tests for MCP server tool functions — all 17 tools exercised via direct calls."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import OptimizationStatus
from app.models.optimization import Optimization
from app.models.project import Project, Prompt
from app.repositories.optimization import OptimizationRepository


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid UUID for seeding records that will be looked up by UUID-validated tools
_UUID_1 = "00000000-0000-4000-8000-000000000001"
_UUID_2 = "00000000-0000-4000-8000-000000000002"
_UUID_3 = "00000000-0000-4000-8000-000000000003"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_context():
    """Create a mock MCP Context with report_progress."""
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    ctx.log = AsyncMock()
    return ctx


@pytest.fixture()
async def mcp_session(db_engine):
    """Patch _repo_session and async_session_factory to use the test in-memory database.

    Yields a session that can be used to seed test data.
    """
    factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    @asynccontextmanager
    async def _fake_repo_session():
        async with factory() as session:
            yield OptimizationRepository(session), session

    with (
        patch("app.mcp_server._repo_session", _fake_repo_session),
        patch("app.mcp_server.async_session_factory", factory),
    ):
        # Clear shared stats cache so tests start with a clean slate
        from app.services.stats_cache import invalidate_stats_cache
        invalidate_stats_cache()
        async with factory() as session:
            yield session


async def _seed(session: AsyncSession, **overrides) -> Optimization:
    """Insert an optimization record for testing."""
    defaults = {
        "id": _UUID_1,
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


async def _seed_project(session: AsyncSession, **overrides) -> Project:
    """Insert a project record for testing."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    defaults = {
        "id": _UUID_1,
        "name": "test-project",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    project = Project(**defaults)
    session.add(project)
    await session.commit()
    return project


async def _seed_prompt(session: AsyncSession, project_id: str, **overrides) -> Prompt:
    """Insert a prompt record for testing."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    defaults = {
        "id": _UUID_3,
        "content": "test prompt content",
        "version": 1,
        "project_id": project_id,
        "order_index": 0,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    prompt = Prompt(**defaults)
    session.add(prompt)
    await session.commit()
    return prompt


# ---------------------------------------------------------------------------
# TestValidateUuid
# ---------------------------------------------------------------------------

class TestValidateUuid:
    def test_valid_uuid(self):
        from app.mcp_server import _validate_uuid
        # Should not raise
        _validate_uuid("550e8400-e29b-41d4-a716-446655440000")

    def test_invalid_uuid_raises(self):
        from app.mcp_server import _validate_uuid
        with pytest.raises(ToolError, match="Invalid"):
            _validate_uuid("not-a-uuid")

    def test_short_string_raises(self):
        from app.mcp_server import _validate_uuid
        with pytest.raises(ToolError, match="Invalid"):
            _validate_uuid("abc")

    def test_custom_field_name(self):
        from app.mcp_server import _validate_uuid
        with pytest.raises(ToolError, match="optimization_id"):
            _validate_uuid("bad", "optimization_id")


# ---------------------------------------------------------------------------
# TestValidateTags
# ---------------------------------------------------------------------------

class TestValidateTags:
    def test_valid_tags(self):
        from app.mcp_server import _validate_tags
        _validate_tags(["short", "also-short"])

    def test_tag_too_long_raises(self):
        from app.mcp_server import _validate_tags
        with pytest.raises(ToolError, match="50 characters"):
            _validate_tags(["x" * 51])


# ---------------------------------------------------------------------------
# TestPromptforgeOptimize
# ---------------------------------------------------------------------------

class TestPromptforgeOptimize:
    @pytest.mark.asyncio
    async def test_empty_prompt_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="empty"):
            await promptforge_optimize(prompt="", ctx=ctx)

    @pytest.mark.asyncio
    async def test_whitespace_prompt_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="empty"):
            await promptforge_optimize(prompt="   ", ctx=ctx)

    @pytest.mark.asyncio
    async def test_prompt_too_long_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="100,000"):
            await promptforge_optimize(prompt="x" * 100_001, ctx=ctx)

    @pytest.mark.asyncio
    async def test_invalid_strategy_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="bogus"):
            await promptforge_optimize(prompt="test", strategy="bogus", ctx=ctx)

    @pytest.mark.asyncio
    async def test_tag_too_long_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="50 characters"):
            await promptforge_optimize(prompt="test", tags=["x" * 51], ctx=ctx)

    @pytest.mark.asyncio
    async def test_project_name_too_long_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="100 characters"):
            await promptforge_optimize(prompt="test", project="x" * 101, ctx=ctx)

    @pytest.mark.asyncio
    async def test_invalid_version_format_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="v<number>"):
            await promptforge_optimize(prompt="test", version="bad", ctx=ctx)

    @pytest.mark.asyncio
    async def test_invalid_prompt_id_format_raises(self, mcp_session):
        from app.mcp_server import promptforge_optimize
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="Invalid prompt_id"):
            await promptforge_optimize(prompt="test", prompt_id="not-uuid", ctx=ctx)

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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ):
            result = await promptforge_optimize(
                prompt="Write a function",
                ctx=ctx,
                project="test-project",
                tags=["coding"],
                title="Test optimization",
            )

        assert "error" not in result
        assert result["status"] == "completed"
        assert result["id"]  # Should have a UUID
        assert result["optimized_prompt"] == "Better prompt text"
        # Verify progress was reported
        assert ctx.report_progress.call_count >= 2

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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            result = await promptforge_optimize(prompt="test", strategy="chain-of-thought", ctx=ctx)

        assert "error" not in result
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("strategy_override") == "chain-of-thought"

    @pytest.mark.asyncio
    async def test_pipeline_error_raises_tool_error(self, mcp_session):
        """When pipeline raises a generic error, ToolError is raised with generic message."""
        from app.mcp_server import promptforge_optimize

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM failed"),
        ):
            with pytest.raises(ToolError, match="pipeline failed"):
                await promptforge_optimize(prompt="test prompt", ctx=ctx)

    @pytest.mark.asyncio
    async def test_provider_error_raises_tool_error_with_message(self, mcp_session):
        """When pipeline raises a ProviderError, its message is preserved."""
        from app.mcp_server import promptforge_optimize
        from app.providers.errors import ProviderError

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline",
            new_callable=AsyncMock,
            side_effect=ProviderError("Rate limit exceeded", provider="anthropic"),
        ):
            with pytest.raises(ToolError, match="Rate limit exceeded"):
                await promptforge_optimize(prompt="test prompt", ctx=ctx)

    @pytest.mark.asyncio
    async def test_codebase_context_passed_to_pipeline(self, mcp_session):
        """codebase_context dict should be converted and passed to run_pipeline."""
        from app.mcp_server import promptforge_optimize
        from app.services.pipeline import PipelineResult

        mock_result = PipelineResult(
            task_type="coding",
            complexity="medium",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            result = await promptforge_optimize(
                prompt="Write a function",
                ctx=ctx,
                codebase_context={
                    "language": "Python 3.14",
                    "framework": "FastAPI",
                    "conventions": ["PEP 8"],
                },
            )

        assert "error" not in result
        _, kwargs = mock_run.call_args
        resolved_ctx = kwargs.get("codebase_context")
        assert resolved_ctx is not None
        assert resolved_ctx.language == "Python 3.14"
        assert resolved_ctx.framework == "FastAPI"
        assert resolved_ctx.conventions == ["PEP 8"]

    @pytest.mark.asyncio
    async def test_codebase_context_none_when_omitted(self, mcp_session):
        """When codebase_context is not provided, run_pipeline receives None."""
        from app.mcp_server import promptforge_optimize
        from app.services.pipeline import PipelineResult

        mock_result = PipelineResult(
            task_type="general",
            complexity="low",
            weaknesses=[],
            strengths=[],
            optimized_prompt="Better",
            framework_applied="role-task-format",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            await promptforge_optimize(prompt="test", ctx=ctx)

        _, kwargs = mock_run.call_args
        assert kwargs.get("codebase_context") is None


# ---------------------------------------------------------------------------
# TestPromptforgeRetry
# ---------------------------------------------------------------------------

class TestPromptforgeRetry:
    @pytest.mark.asyncio
    async def test_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_retry
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="not found"):
            await promptforge_retry(optimization_id=_UUID_1, ctx=ctx)

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self, mcp_session):
        from app.mcp_server import promptforge_retry
        ctx = _make_mock_context()
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_retry(optimization_id="bad-id", ctx=ctx)

    @pytest.mark.asyncio
    async def test_retry_reuses_params(self, mcp_session):
        """Retry fetches original and re-runs with same parameters."""
        from app.mcp_server import promptforge_retry
        from app.services.pipeline import PipelineResult

        await _seed(
            mcp_session,
            id=_UUID_1,
            raw_prompt="original prompt",
            project="my-project",
            tags=json.dumps(["tag1"]),
            title="my title",
            strategy="chain-of-thought",
        )

        mock_result = PipelineResult(
            task_type="coding",
            complexity="low",
            weaknesses=[],
            strengths=[],
            optimized_prompt="Retried",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            result = await promptforge_retry(optimization_id=_UUID_1, ctx=ctx)

        assert result["optimized_prompt"] == "Retried"
        assert result["status"] == "completed"
        # Verify pipeline was called with the original strategy
        _, kwargs = mock_run.call_args
        assert kwargs.get("strategy_override") == "chain-of-thought"

    @pytest.mark.asyncio
    async def test_retry_with_strategy_override(self, mcp_session):
        """Retry with strategy override uses the new strategy instead of original."""
        from app.mcp_server import promptforge_retry
        from app.services.pipeline import PipelineResult

        await _seed(
            mcp_session,
            id=_UUID_1,
            raw_prompt="original prompt",
            strategy="chain-of-thought",
        )

        mock_result = PipelineResult(
            task_type="coding",
            complexity="low",
            weaknesses=[],
            strengths=[],
            optimized_prompt="Retried with override",
            framework_applied="few-shot-scaffolding",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            result = await promptforge_retry(
                optimization_id=_UUID_1,
                ctx=ctx,
                strategy="few-shot-scaffolding",
            )

        assert result["optimized_prompt"] == "Retried with override"
        _, kwargs = mock_run.call_args
        assert kwargs.get("strategy_override") == "few-shot-scaffolding"

    @pytest.mark.asyncio
    async def test_retry_with_secondary_frameworks_override(self, mcp_session):
        """Retry with secondary_frameworks override replaces originals."""
        from app.mcp_server import promptforge_retry
        from app.services.pipeline import PipelineResult

        await _seed(
            mcp_session,
            id=_UUID_1,
            raw_prompt="test",
            strategy="chain-of-thought",
            secondary_frameworks=json.dumps(["co-star"]),
        )

        mock_result = PipelineResult(
            task_type="general",
            complexity="low",
            weaknesses=[],
            strengths=[],
            optimized_prompt="OK",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            result = await promptforge_retry(
                optimization_id=_UUID_1,
                ctx=ctx,
                secondary_frameworks=["risen", "step-by-step"],
            )

        assert "error" not in result
        _, kwargs = mock_run.call_args
        assert kwargs.get("secondary_frameworks_override") == ["risen", "step-by-step"]

    @pytest.mark.asyncio
    async def test_retry_no_override_uses_original(self, mcp_session):
        """Retry without overrides uses the original strategy."""
        from app.mcp_server import promptforge_retry
        from app.services.pipeline import PipelineResult

        await _seed(
            mcp_session,
            id=_UUID_1,
            raw_prompt="test",
            strategy="persona-assignment",
        )

        mock_result = PipelineResult(
            task_type="general",
            complexity="low",
            weaknesses=[],
            strengths=[],
            optimized_prompt="OK",
            framework_applied="persona-assignment",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            result = await promptforge_retry(optimization_id=_UUID_1, ctx=ctx)

        assert "error" not in result
        _, kwargs = mock_run.call_args
        assert kwargs.get("strategy_override") == "persona-assignment"


# ---------------------------------------------------------------------------
# TestPromptforgeGet
# ---------------------------------------------------------------------------

class TestPromptforgeGet:
    @pytest.mark.asyncio
    async def test_found(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_get
        result = await promptforge_get(_UUID_1)
        assert result["id"] == _UUID_1
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_get
        with pytest.raises(ToolError, match="not found"):
            await promptforge_get(_UUID_2)

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self, mcp_session):
        from app.mcp_server import promptforge_get
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_get("nonexistent")


# ---------------------------------------------------------------------------
# TestPromptforgeList
# ---------------------------------------------------------------------------

class TestPromptforgeList:
    @pytest.mark.asyncio
    async def test_basic_list(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        await _seed(mcp_session, id=_UUID_2)
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
        await _seed(mcp_session, id=_UUID_1, project="proj-a")
        await _seed(mcp_session, id=_UUID_2, project="proj-b")
        from app.mcp_server import promptforge_list
        result = await promptforge_list(project="proj-a")
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_min_score_clamped(self, mcp_session):
        """min_score is clamped to [1.0, 10.0]."""
        from app.mcp_server import promptforge_list
        # Negative min_score should be clamped to 1.0
        result = await promptforge_list(min_score=-5.0)
        assert result is not None  # Should not crash
        # Over 10 should be clamped to 10.0
        result = await promptforge_list(min_score=999.0)
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# TestPromptforgeGetByProject
# ---------------------------------------------------------------------------

class TestPromptforgeGetByProject:
    @pytest.mark.asyncio
    async def test_returns_project_items(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1, project="alpha")
        await _seed(mcp_session, id=_UUID_2, project="beta")
        from app.mcp_server import promptforge_get_by_project
        result = await promptforge_get_by_project("alpha")
        assert result["project"] == "alpha"
        assert result["count"] == 1
        assert "total" in result
        assert "has_more" in result

    @pytest.mark.asyncio
    async def test_pagination_fields(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1, project="pg")
        await _seed(mcp_session, id=_UUID_2, project="pg")
        from app.mcp_server import promptforge_get_by_project
        result = await promptforge_get_by_project("pg", limit=1)
        assert result["count"] == 1
        assert result["total"] == 2
        assert result["has_more"] is True
        assert result["next_offset"] == 1


# ---------------------------------------------------------------------------
# TestPromptforgeSearch
# ---------------------------------------------------------------------------

class TestPromptforgeSearch:
    @pytest.mark.asyncio
    async def test_valid_search(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1, raw_prompt="optimize SQL query")
        await _seed(mcp_session, id=_UUID_2, raw_prompt="write a poem")
        from app.mcp_server import promptforge_search
        result = await promptforge_search("SQL")
        assert result["total"] == 1
        assert "count" in result
        assert "has_more" in result

    @pytest.mark.asyncio
    async def test_short_query_raises(self, mcp_session):
        from app.mcp_server import promptforge_search
        with pytest.raises(ToolError, match="at least 2"):
            await promptforge_search("x")

    @pytest.mark.asyncio
    async def test_pagination_fields(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1, raw_prompt="test search foo")
        await _seed(mcp_session, id=_UUID_2, raw_prompt="test search bar")
        from app.mcp_server import promptforge_search
        result = await promptforge_search("test", limit=1)
        assert result["count"] == 1
        assert result["total"] == 2
        assert result["has_more"] is True
        assert result["offset"] == 0


# ---------------------------------------------------------------------------
# TestPromptforgeTag
# ---------------------------------------------------------------------------

class TestPromptforgeTag:
    @pytest.mark.asyncio
    async def test_add_and_remove_tags(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1, tags=json.dumps(["existing"]))
        from app.mcp_server import promptforge_tag
        result = await promptforge_tag(_UUID_1, add_tags=["new"], remove_tags=["existing"])
        assert result["tags"] == ["new"]

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_tag
        with pytest.raises(ToolError, match="not found"):
            await promptforge_tag(_UUID_2, add_tags=["x"])

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self, mcp_session):
        from app.mcp_server import promptforge_tag
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_tag("nonexistent", add_tags=["x"])

    @pytest.mark.asyncio
    async def test_tag_too_long_raises(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_tag
        with pytest.raises(ToolError, match="50 characters"):
            await promptforge_tag(_UUID_1, add_tags=["x" * 51])

    @pytest.mark.asyncio
    async def test_project_name_too_long_raises(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_tag
        with pytest.raises(ToolError, match="100 characters"):
            await promptforge_tag(_UUID_1, project="x" * 101)

    @pytest.mark.asyncio
    async def test_title_too_long_raises(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_tag
        with pytest.raises(ToolError, match="200 characters"):
            await promptforge_tag(_UUID_1, title="x" * 201)

    @pytest.mark.asyncio
    async def test_archived_project_raises(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        await _seed_project(mcp_session, id=_UUID_2, name="archived-proj", status="archived")
        from app.mcp_server import promptforge_tag
        with pytest.raises(ToolError, match="archived"):
            await promptforge_tag(_UUID_1, project="archived-proj")

    @pytest.mark.asyncio
    async def test_set_project_returns_project_id(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_tag
        result = await promptforge_tag(_UUID_1, project="new-proj")
        assert "project_id" in result
        assert result["project_id"] is not None


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
        await _seed(mcp_session, id=_UUID_1, overall_score=0.8)
        from app.mcp_server import promptforge_stats
        result = await promptforge_stats()
        assert result["total_optimizations"] == 1


# ---------------------------------------------------------------------------
# TestPromptforgeDelete
# ---------------------------------------------------------------------------

class TestPromptforgeDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_delete
        result = await promptforge_delete(_UUID_1)
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_delete
        with pytest.raises(ToolError, match="not found"):
            await promptforge_delete(_UUID_2)

    @pytest.mark.asyncio
    async def test_delete_invalid_uuid_raises(self, mcp_session):
        from app.mcp_server import promptforge_delete
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_delete("nonexistent")


# ---------------------------------------------------------------------------
# TestPromptforgeBulkDelete
# ---------------------------------------------------------------------------

class TestPromptforgeBulkDelete:
    @pytest.mark.asyncio
    async def test_bulk_delete_existing(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        await _seed(mcp_session, id=_UUID_2)
        from app.mcp_server import promptforge_bulk_delete
        result = await promptforge_bulk_delete([_UUID_1, _UUID_2])
        assert result["deleted_count"] == 2
        assert set(result["deleted_ids"]) == {_UUID_1, _UUID_2}
        assert result["not_found_ids"] == []

    @pytest.mark.asyncio
    async def test_bulk_delete_mixed(self, mcp_session):
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_bulk_delete
        result = await promptforge_bulk_delete([_UUID_1, _UUID_2])
        assert result["deleted_count"] == 1
        assert result["deleted_ids"] == [_UUID_1]
        assert result["not_found_ids"] == [_UUID_2]

    @pytest.mark.asyncio
    async def test_bulk_delete_all_missing(self, mcp_session):
        from app.mcp_server import promptforge_bulk_delete
        result = await promptforge_bulk_delete([_UUID_1, _UUID_2])
        assert result["deleted_count"] == 0
        assert result["deleted_ids"] == []
        assert set(result["not_found_ids"]) == {_UUID_1, _UUID_2}

    @pytest.mark.asyncio
    async def test_bulk_delete_empty_raises(self, mcp_session):
        from app.mcp_server import promptforge_bulk_delete
        with pytest.raises(ToolError, match="empty"):
            await promptforge_bulk_delete([])

    @pytest.mark.asyncio
    async def test_bulk_delete_over_limit_raises(self, mcp_session):
        from app.mcp_server import promptforge_bulk_delete
        ids = [f"00000000-0000-4000-8000-{i:012d}" for i in range(101)]
        with pytest.raises(ToolError, match="100"):
            await promptforge_bulk_delete(ids)

    @pytest.mark.asyncio
    async def test_bulk_delete_actually_removes(self, mcp_session):
        """Verify deleted records are no longer retrievable."""
        await _seed(mcp_session, id=_UUID_1)
        from app.mcp_server import promptforge_bulk_delete, promptforge_get
        await promptforge_bulk_delete([_UUID_1])
        with pytest.raises(ToolError, match="not found"):
            await promptforge_get(_UUID_1)


# ---------------------------------------------------------------------------
# TestPromptforgeListProjects
# ---------------------------------------------------------------------------

class TestPromptforgeListProjects:
    @pytest.mark.asyncio
    async def test_empty(self, mcp_session):
        from app.mcp_server import promptforge_list_projects
        result = await promptforge_list_projects()
        assert result["total"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_with_projects(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="proj-alpha")
        await _seed_project(mcp_session, id=_UUID_2, name="proj-beta")
        from app.mcp_server import promptforge_list_projects
        result = await promptforge_list_projects()
        assert result["total"] == 2
        assert result["count"] == 2
        names = {item["name"] for item in result["items"]}
        assert names == {"proj-alpha", "proj-beta"}

    @pytest.mark.asyncio
    async def test_filter_by_status(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="active-p", status="active")
        await _seed_project(mcp_session, id=_UUID_2, name="archived-p", status="archived")
        from app.mcp_server import promptforge_list_projects
        result = await promptforge_list_projects(status="active")
        assert result["total"] == 1
        assert result["items"][0]["name"] == "active-p"

    @pytest.mark.asyncio
    async def test_pagination(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="p1")
        await _seed_project(mcp_session, id=_UUID_2, name="p2")
        from app.mcp_server import promptforge_list_projects
        result = await promptforge_list_projects(limit=1)
        assert result["count"] == 1
        assert result["total"] == 2
        assert result["has_more"] is True

    @pytest.mark.asyncio
    async def test_prompt_count_included(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="with-prompts")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2)
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_3)
        from app.mcp_server import promptforge_list_projects
        result = await promptforge_list_projects()
        assert result["items"][0]["prompt_count"] == 2


# ---------------------------------------------------------------------------
# TestPromptforgeGetProject
# ---------------------------------------------------------------------------

class TestPromptforgeGetProject:
    @pytest.mark.asyncio
    async def test_found_with_prompts(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="my-project")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2, content="prompt A")
        from app.mcp_server import promptforge_get_project
        result = await promptforge_get_project(_UUID_1)
        assert result["id"] == _UUID_1
        assert result["name"] == "my-project"
        assert len(result["prompts"]) == 1
        assert result["prompts"][0]["content"] == "prompt A"

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_get_project
        with pytest.raises(ToolError, match="not found"):
            await promptforge_get_project(_UUID_2)

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self, mcp_session):
        from app.mcp_server import promptforge_get_project
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_get_project("bad-id")


# ---------------------------------------------------------------------------
# TestPromptforgeStrategies
# ---------------------------------------------------------------------------

class TestPromptforgeStrategies:
    @pytest.mark.asyncio
    async def test_returns_all_strategies(self, mcp_session):
        from app.mcp_server import promptforge_strategies
        result = await promptforge_strategies()
        assert result["count"] == 10
        names = {s["name"] for s in result["strategies"]}
        assert "chain-of-thought" in names
        assert "co-star" in names
        assert "risen" in names
        assert "persona-assignment" in names

    @pytest.mark.asyncio
    async def test_each_strategy_has_description_and_reasoning(self, mcp_session):
        from app.mcp_server import promptforge_strategies
        result = await promptforge_strategies()
        for s in result["strategies"]:
            assert s["name"], "strategy must have a name"
            assert s["description"], f"strategy {s['name']} must have a description"
            assert s["reasoning"], f"strategy {s['name']} must have reasoning"

    @pytest.mark.asyncio
    async def test_legacy_aliases_included(self, mcp_session):
        from app.mcp_server import promptforge_strategies
        result = await promptforge_strategies()
        aliases = result["legacy_aliases"]
        assert isinstance(aliases, dict)
        assert "few-shot" in aliases
        assert aliases["few-shot"] == "few-shot-scaffolding"


# ---------------------------------------------------------------------------
# TestPromptforgeCreateProject
# ---------------------------------------------------------------------------

class TestPromptforgeCreateProject:
    @pytest.mark.asyncio
    async def test_create_new_project(self, mcp_session):
        from app.mcp_server import promptforge_create_project
        result = await promptforge_create_project(name="new-project")
        assert result["name"] == "new-project"
        assert result["status"] == "active"
        assert result["id"]

    @pytest.mark.asyncio
    async def test_create_with_description(self, mcp_session):
        from app.mcp_server import promptforge_create_project
        result = await promptforge_create_project(
            name="described-proj", description="A test project",
        )
        assert result["description"] == "A test project"

    @pytest.mark.asyncio
    async def test_empty_name_raises(self, mcp_session):
        from app.mcp_server import promptforge_create_project
        with pytest.raises(ToolError, match="empty"):
            await promptforge_create_project(name="")

    @pytest.mark.asyncio
    async def test_whitespace_name_raises(self, mcp_session):
        from app.mcp_server import promptforge_create_project
        with pytest.raises(ToolError, match="empty"):
            await promptforge_create_project(name="   ")

    @pytest.mark.asyncio
    async def test_name_too_long_raises(self, mcp_session):
        from app.mcp_server import promptforge_create_project
        with pytest.raises(ToolError, match="100 characters"):
            await promptforge_create_project(name="x" * 101)

    @pytest.mark.asyncio
    async def test_description_too_long_raises(self, mcp_session):
        from app.mcp_server import promptforge_create_project
        with pytest.raises(ToolError, match="2000 characters"):
            await promptforge_create_project(name="ok", description="x" * 2001)

    @pytest.mark.asyncio
    async def test_duplicate_name_raises(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="existing")
        from app.mcp_server import promptforge_create_project
        with pytest.raises(ToolError, match="already exists"):
            await promptforge_create_project(name="existing")

    @pytest.mark.asyncio
    async def test_reactivates_deleted_project(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="deleted-proj", status="deleted")
        from app.mcp_server import promptforge_create_project
        result = await promptforge_create_project(name="deleted-proj")
        assert result["status"] == "active"
        assert result["id"] == _UUID_1


# ---------------------------------------------------------------------------
# TestPromptforgeAddPrompt
# ---------------------------------------------------------------------------

class TestPromptforgeAddPrompt:
    @pytest.mark.asyncio
    async def test_add_prompt_to_project(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="proj")
        from app.mcp_server import promptforge_add_prompt
        result = await promptforge_add_prompt(
            project_id=_UUID_1, content="My new prompt",
        )
        assert result["content"] == "My new prompt"
        assert result["project_id"] == _UUID_1
        assert result["version"] == 1
        assert result["order_index"] == 0

    @pytest.mark.asyncio
    async def test_invalid_project_id_raises(self, mcp_session):
        from app.mcp_server import promptforge_add_prompt
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_add_prompt(project_id="bad", content="test")

    @pytest.mark.asyncio
    async def test_project_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_add_prompt
        with pytest.raises(ToolError, match="not found"):
            await promptforge_add_prompt(project_id=_UUID_2, content="test")

    @pytest.mark.asyncio
    async def test_empty_content_raises(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="proj")
        from app.mcp_server import promptforge_add_prompt
        with pytest.raises(ToolError, match="empty"):
            await promptforge_add_prompt(project_id=_UUID_1, content="")

    @pytest.mark.asyncio
    async def test_content_too_long_raises(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="proj")
        from app.mcp_server import promptforge_add_prompt
        with pytest.raises(ToolError, match="100,000"):
            await promptforge_add_prompt(project_id=_UUID_1, content="x" * 100_001)

    @pytest.mark.asyncio
    async def test_archived_project_raises(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="arch", status="archived")
        from app.mcp_server import promptforge_add_prompt
        with pytest.raises(ToolError, match="archived"):
            await promptforge_add_prompt(project_id=_UUID_1, content="test")

    @pytest.mark.asyncio
    async def test_deleted_project_raises(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="del", status="deleted")
        from app.mcp_server import promptforge_add_prompt
        with pytest.raises(ToolError, match="not found"):
            await promptforge_add_prompt(project_id=_UUID_1, content="test")


# ---------------------------------------------------------------------------
# TestPromptforgeUpdatePrompt
# ---------------------------------------------------------------------------

class TestPromptforgeUpdatePrompt:
    @pytest.mark.asyncio
    async def test_update_prompt_content(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="proj")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2, content="old")
        from app.mcp_server import promptforge_update_prompt
        result = await promptforge_update_prompt(prompt_id=_UUID_2, content="new content")
        assert result["content"] == "new content"
        assert result["version"] == 2  # bumped from 1

    @pytest.mark.asyncio
    async def test_invalid_prompt_id_raises(self, mcp_session):
        from app.mcp_server import promptforge_update_prompt
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_update_prompt(prompt_id="bad", content="test")

    @pytest.mark.asyncio
    async def test_prompt_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_update_prompt
        with pytest.raises(ToolError, match="not found"):
            await promptforge_update_prompt(prompt_id=_UUID_2, content="test")

    @pytest.mark.asyncio
    async def test_empty_content_raises(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="proj")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2)
        from app.mcp_server import promptforge_update_prompt
        with pytest.raises(ToolError, match="empty"):
            await promptforge_update_prompt(prompt_id=_UUID_2, content="")

    @pytest.mark.asyncio
    async def test_content_too_long_raises(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="proj")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2)
        from app.mcp_server import promptforge_update_prompt
        with pytest.raises(ToolError, match="100,000"):
            await promptforge_update_prompt(prompt_id=_UUID_2, content="x" * 100_001)

    @pytest.mark.asyncio
    async def test_invalid_optimization_id_raises(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="proj")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2)
        from app.mcp_server import promptforge_update_prompt
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_update_prompt(
                prompt_id=_UUID_2, content="new", optimization_id="bad",
            )

    @pytest.mark.asyncio
    async def test_archived_project_raises(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="arch", status="archived")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2)
        from app.mcp_server import promptforge_update_prompt
        with pytest.raises(ToolError, match="archived"):
            await promptforge_update_prompt(prompt_id=_UUID_2, content="new")

    @pytest.mark.asyncio
    async def test_deleted_project_raises(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="del", status="deleted")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2)
        from app.mcp_server import promptforge_update_prompt
        with pytest.raises(ToolError, match="not found"):
            await promptforge_update_prompt(prompt_id=_UUID_2, content="new")

    @pytest.mark.asyncio
    async def test_update_with_optimization_id(self, mcp_session):
        project = await _seed_project(mcp_session, id=_UUID_1, name="proj")
        await _seed_prompt(mcp_session, project_id=project.id, id=_UUID_2, content="old")
        from app.mcp_server import promptforge_update_prompt
        result = await promptforge_update_prompt(
            prompt_id=_UUID_2, content="new", optimization_id=_UUID_3,
        )
        assert result["content"] == "new"
        assert result["version"] == 2


# ---------------------------------------------------------------------------
# TestPromptforgeSetProjectContext
# ---------------------------------------------------------------------------

_SAMPLE_CONTEXT = {
    "language": "Python 3.14",
    "framework": "FastAPI",
    "test_framework": "pytest",
    "conventions": ["PEP 8", "async-first"],
}


class TestPromptforgeSetProjectContext:
    @pytest.mark.asyncio
    async def test_set_context_on_active_project(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="ctx-proj")
        from app.mcp_server import promptforge_set_project_context
        result = await promptforge_set_project_context(
            project_id=_UUID_1, context_profile=_SAMPLE_CONTEXT,
        )
        assert result["id"] == _UUID_1
        assert result["has_context"] is True
        assert result["context_profile"]["language"] == "Python 3.14"
        assert result["context_profile"]["framework"] == "FastAPI"
        assert result["context_profile"]["conventions"] == ["PEP 8", "async-first"]

    @pytest.mark.asyncio
    async def test_clear_context_with_none(self, mcp_session):
        await _seed_project(
            mcp_session, id=_UUID_1, name="ctx-proj",
            context_profile=json.dumps(_SAMPLE_CONTEXT),
        )
        from app.mcp_server import promptforge_set_project_context
        result = await promptforge_set_project_context(
            project_id=_UUID_1, context_profile=None,
        )
        assert result["has_context"] is False
        assert "context_profile" not in result or result.get("context_profile") is None

    @pytest.mark.asyncio
    async def test_overwrite_existing_context(self, mcp_session):
        await _seed_project(
            mcp_session, id=_UUID_1, name="ctx-proj",
            context_profile=json.dumps({"language": "Go"}),
        )
        from app.mcp_server import promptforge_set_project_context
        result = await promptforge_set_project_context(
            project_id=_UUID_1, context_profile={"language": "Rust", "framework": "Actix"},
        )
        assert result["context_profile"]["language"] == "Rust"
        assert result["context_profile"]["framework"] == "Actix"

    @pytest.mark.asyncio
    async def test_archived_project_raises(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="arch", status="archived")
        from app.mcp_server import promptforge_set_project_context
        with pytest.raises(ToolError, match="archived"):
            await promptforge_set_project_context(
                project_id=_UUID_1, context_profile=_SAMPLE_CONTEXT,
            )

    @pytest.mark.asyncio
    async def test_deleted_project_raises(self, mcp_session):
        await _seed_project(mcp_session, id=_UUID_1, name="del", status="deleted")
        from app.mcp_server import promptforge_set_project_context
        with pytest.raises(ToolError, match="not found"):
            await promptforge_set_project_context(
                project_id=_UUID_1, context_profile=_SAMPLE_CONTEXT,
            )

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mcp_session):
        from app.mcp_server import promptforge_set_project_context
        with pytest.raises(ToolError, match="not found"):
            await promptforge_set_project_context(
                project_id=_UUID_2, context_profile=_SAMPLE_CONTEXT,
            )

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self, mcp_session):
        from app.mcp_server import promptforge_set_project_context
        with pytest.raises(ToolError, match="Invalid"):
            await promptforge_set_project_context(
                project_id="bad-id", context_profile=_SAMPLE_CONTEXT,
            )

    @pytest.mark.asyncio
    async def test_empty_context_fields_are_filtered(self, mcp_session):
        """Context with all-empty fields is treated as no context."""
        await _seed_project(mcp_session, id=_UUID_1, name="ctx-proj")
        from app.mcp_server import promptforge_set_project_context
        result = await promptforge_set_project_context(
            project_id=_UUID_1,
            context_profile={"language": "", "framework": "", "conventions": []},
        )
        assert result["has_context"] is False

    @pytest.mark.asyncio
    async def test_idempotent_set(self, mcp_session):
        """Setting the same context twice produces the same result."""
        await _seed_project(mcp_session, id=_UUID_1, name="ctx-proj")
        from app.mcp_server import promptforge_set_project_context
        r1 = await promptforge_set_project_context(
            project_id=_UUID_1, context_profile=_SAMPLE_CONTEXT,
        )
        r2 = await promptforge_set_project_context(
            project_id=_UUID_1, context_profile=_SAMPLE_CONTEXT,
        )
        assert r1["context_profile"] == r2["context_profile"]
        assert r1["has_context"] == r2["has_context"]


# ---------------------------------------------------------------------------
# TestContextIntegration — context fields on other project/optimize tools
# ---------------------------------------------------------------------------

class TestContextIntegration:
    @pytest.mark.asyncio
    async def test_list_projects_has_context_field(self, mcp_session):
        """list_projects returns has_context boolean for each project."""
        await _seed_project(
            mcp_session, id=_UUID_1, name="with-ctx",
            context_profile=json.dumps({"language": "Python"}),
        )
        await _seed_project(mcp_session, id=_UUID_2, name="without-ctx")
        from app.mcp_server import promptforge_list_projects
        result = await promptforge_list_projects()
        items_by_name = {item["name"]: item for item in result["items"]}
        assert items_by_name["with-ctx"]["has_context"] is True
        assert items_by_name["without-ctx"]["has_context"] is False

    @pytest.mark.asyncio
    async def test_get_project_returns_context_profile(self, mcp_session):
        """get_project includes full context_profile dict when present."""
        await _seed_project(
            mcp_session, id=_UUID_1, name="ctx-proj",
            context_profile=json.dumps({"language": "TypeScript", "framework": "SvelteKit"}),
        )
        from app.mcp_server import promptforge_get_project
        result = await promptforge_get_project(_UUID_1)
        assert result["has_context"] is True
        assert result["context_profile"]["language"] == "TypeScript"
        assert result["context_profile"]["framework"] == "SvelteKit"

    @pytest.mark.asyncio
    async def test_get_project_no_context_profile(self, mcp_session):
        """get_project omits context_profile when project has no context."""
        await _seed_project(mcp_session, id=_UUID_1, name="plain-proj")
        from app.mcp_server import promptforge_get_project
        result = await promptforge_get_project(_UUID_1)
        assert result["has_context"] is False
        assert "context_profile" not in result

    @pytest.mark.asyncio
    async def test_create_project_with_context(self, mcp_session):
        """create_project accepts context_profile and returns it."""
        from app.mcp_server import promptforge_create_project
        result = await promptforge_create_project(
            name="new-ctx-proj",
            context_profile={"language": "Go", "framework": "Chi"},
        )
        assert result["has_context"] is True
        assert result["context_profile"]["language"] == "Go"
        assert result["context_profile"]["framework"] == "Chi"

    @pytest.mark.asyncio
    async def test_create_project_without_context(self, mcp_session):
        """create_project without context_profile has has_context=False."""
        from app.mcp_server import promptforge_create_project
        result = await promptforge_create_project(name="plain-proj")
        assert result["has_context"] is False

    @pytest.mark.asyncio
    async def test_optimize_resolves_project_context(self, mcp_session):
        """optimize with project name resolves context from project profile."""
        from app.mcp_server import promptforge_optimize
        from app.services.pipeline import PipelineResult

        # Seed project with context
        await _seed_project(
            mcp_session, id=_UUID_1, name="ctx-project",
            context_profile=json.dumps({
                "language": "Python 3.14",
                "framework": "FastAPI",
                "test_framework": "pytest",
            }),
        )

        mock_result = PipelineResult(
            task_type="coding",
            complexity="medium",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            await promptforge_optimize(prompt="Write a function", ctx=ctx, project="ctx-project")

        _, kwargs = mock_run.call_args
        resolved_ctx = kwargs.get("codebase_context")
        assert resolved_ctx is not None
        assert resolved_ctx.language == "Python 3.14"
        assert resolved_ctx.framework == "FastAPI"
        assert resolved_ctx.test_framework == "pytest"

    @pytest.mark.asyncio
    async def test_optimize_merges_explicit_over_project_context(self, mcp_session):
        """Explicit codebase_context fields override project profile fields."""
        from app.mcp_server import promptforge_optimize
        from app.services.pipeline import PipelineResult

        await _seed_project(
            mcp_session, id=_UUID_1, name="merge-proj",
            context_profile=json.dumps({
                "language": "Python",
                "framework": "FastAPI",
                "test_framework": "pytest",
            }),
        )

        mock_result = PipelineResult(
            task_type="coding",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            await promptforge_optimize(
                prompt="Write tests",
                ctx=ctx,
                project="merge-proj",
                codebase_context={"framework": "Django", "conventions": ["PEP 8"]},
            )

        _, kwargs = mock_run.call_args
        resolved_ctx = kwargs.get("codebase_context")
        assert resolved_ctx is not None
        # Explicit override wins
        assert resolved_ctx.framework == "Django"
        assert resolved_ctx.conventions == ["PEP 8"]
        # Project profile fields retained where not overridden
        assert resolved_ctx.language == "Python"
        assert resolved_ctx.test_framework == "pytest"

    @pytest.mark.asyncio
    async def test_optimize_no_project_no_context(self, mcp_session):
        """optimize without project or codebase_context passes None to pipeline."""
        from app.mcp_server import promptforge_optimize
        from app.services.pipeline import PipelineResult

        mock_result = PipelineResult(
            task_type="general",
            complexity="low",
            weaknesses=[],
            strengths=[],
            optimized_prompt="Better",
            framework_applied="role-task-format",
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

        ctx = _make_mock_context()
        with patch(
            "app.mcp_server.run_pipeline", new_callable=AsyncMock, return_value=mock_result,
        ) as mock_run:
            await promptforge_optimize(prompt="test", ctx=ctx)

        _, kwargs = mock_run.call_args
        assert kwargs.get("codebase_context") is None
