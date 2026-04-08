"""Tests for Phase 2A project-scoped cluster assignment."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.services.taxonomy.engine import TaxonomyEngine


class TestEngineProjectCaches:
    """TaxonomyEngine has _cluster_project_cache and _legacy_project_id."""

    def test_caches_initialised(self):
        mock_embedding = MagicMock()
        mock_provider = MagicMock()
        engine = TaxonomyEngine(
            embedding_service=mock_embedding, provider=mock_provider
        )
        assert hasattr(engine, "_cluster_project_cache")
        assert hasattr(engine, "_legacy_project_id")
        assert engine._cluster_project_cache == {}
        assert engine._legacy_project_id is None

    def test_process_optimization_accepts_repo_full_name(self):
        """Signature accepts repo_full_name keyword argument."""
        import inspect

        sig = inspect.signature(TaxonomyEngine.process_optimization)
        params = list(sig.parameters.keys())
        assert "repo_full_name" in params
        # Default should be None
        assert sig.parameters["repo_full_name"].default is None
