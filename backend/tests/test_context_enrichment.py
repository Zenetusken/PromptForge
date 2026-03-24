"""Tests for ContextEnrichmentService."""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.context_enrichment import ContextEnrichmentService, EnrichedContext


@pytest_asyncio.fixture
async def db():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


class TestEnrichPassthrough:
    @pytest.mark.asyncio
    async def test_passthrough_runs_heuristic_analysis(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint for user login",
            tier="passthrough", db=db,
        )
        assert isinstance(result, EnrichedContext)
        assert result.analysis is not None
        assert result.analysis.task_type == "coding"
        assert result.context_sources["heuristic_analysis"] is True

    @pytest.mark.asyncio
    async def test_passthrough_gets_adaptation(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint for user login",
            tier="passthrough", db=db,
        )
        # Adaptation state is resolved (may be None if no data, but key exists)
        assert "adaptation" in result.context_sources


class TestEnrichInternal:
    @pytest.mark.asyncio
    async def test_internal_skips_heuristic_analysis(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint for user login",
            tier="internal", db=db,
        )
        assert result.analysis is None
        assert result.context_sources["heuristic_analysis"] is False

    @pytest.mark.asyncio
    async def test_internal_skips_curated_index(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint for user login",
            tier="internal", db=db,
            repo_full_name="owner/repo",
        )
        # Internal tier doesn't use curated index (pipeline does explore)
        assert result.codebase_context is None


class TestEnrichWorkspaceGuidance:
    @pytest.mark.asyncio
    async def test_workspace_path_resolves_guidance(self, db, tmp_path):
        # Create a workspace with CLAUDE.md
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("# Project Guidance\nUse async everywhere.")

        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint for user login",
            tier="passthrough", db=db,
            workspace_path=str(workspace),
        )
        assert result.workspace_guidance is not None
        assert "async everywhere" in result.workspace_guidance

    @pytest.mark.asyncio
    async def test_no_workspace_path_returns_none_guidance(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint for user login",
            tier="internal", db=db,
        )
        assert result.workspace_guidance is None
        assert result.context_sources["workspace_guidance"] is False


class TestEnrichGracefulDegradation:
    @pytest.mark.asyncio
    async def test_all_none_still_returns_valid_context(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Tell me about the weather",
            tier="passthrough", db=db,
        )
        assert isinstance(result, EnrichedContext)
        assert result.raw_prompt == "Tell me about the weather"

    @pytest.mark.asyncio
    async def test_context_sources_audit_all_keys_present(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint",
            tier="passthrough", db=db,
        )
        expected_keys = {
            "workspace_guidance", "codebase_context", "adaptation",
            "applied_patterns", "heuristic_analysis",
        }
        assert expected_keys == set(result.context_sources.keys())

    @pytest.mark.asyncio
    async def test_enriched_context_is_frozen(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a sorting algorithm",
            tier="passthrough", db=db,
        )
        assert isinstance(result, EnrichedContext)
        with pytest.raises((AttributeError, TypeError)):
            result.raw_prompt = "something else"  # type: ignore[misc]


class TestEnrichSampling:
    @pytest.mark.asyncio
    async def test_sampling_tier_skips_heuristic(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint",
            tier="sampling", db=db,
        )
        assert result.analysis is None
        assert result.context_sources["heuristic_analysis"] is False

    @pytest.mark.asyncio
    async def test_sampling_tier_skips_codebase_context(self, db, tmp_path):
        service = _build_service(tmp_path)
        result = await service.enrich(
            raw_prompt="Implement a REST API endpoint",
            tier="sampling", db=db,
            repo_full_name="owner/repo",
        )
        assert result.codebase_context is None
        assert result.context_sources["codebase_context"] is False


def _build_service(tmp_path: Path) -> ContextEnrichmentService:
    from app.services.heuristic_analyzer import HeuristicAnalyzer
    from app.services.workspace_intelligence import WorkspaceIntelligence
    mock_es = AsyncMock()
    mock_gc = AsyncMock()
    return ContextEnrichmentService(
        prompts_dir=tmp_path,
        data_dir=tmp_path,
        workspace_intel=WorkspaceIntelligence(),
        embedding_service=mock_es,
        heuristic_analyzer=HeuristicAnalyzer(),
        github_client=mock_gc,
    )
