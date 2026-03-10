"""Tests for the embedding service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.services.embedding_service import EmbeddingService, get_embedding_service


class TestEmbeddingServiceInit:
    """Test initialization and singleton behavior."""

    def test_singleton_returns_same_instance(self):
        """get_embedding_service returns the same instance."""
        # Reset global singleton for clean test
        import app.services.embedding_service as mod
        mod._instance = None
        svc1 = get_embedding_service()
        svc2 = get_embedding_service()
        assert svc1 is svc2
        mod._instance = None  # cleanup

    def test_is_ready_before_load(self):
        """is_ready returns True before any load attempt (model might be loadable)."""
        svc = EmbeddingService("test-model")
        assert svc.is_ready is True

    def test_is_ready_false_after_load_error(self):
        """is_ready returns False after a failed load."""
        svc = EmbeddingService("test-model")
        svc._load_error = "some error"
        assert svc.is_ready is False

    def test_is_ready_true_when_model_loaded(self):
        """is_ready returns True when model is loaded."""
        svc = EmbeddingService("test-model")
        svc._model = MagicMock()  # fake loaded model
        assert svc.is_ready is True


class TestEmbeddingServiceEnsureLoaded:
    """Test lazy model loading."""

    @pytest.mark.asyncio
    async def test_ensure_loaded_success(self):
        """ensure_loaded returns True on successful model load."""
        svc = EmbeddingService("test-model")
        mock_model = MagicMock()

        with patch("anyio.to_thread.run_sync", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_model
            result = await svc.ensure_loaded()

        assert result is True
        assert svc._model is mock_model

    @pytest.mark.asyncio
    async def test_ensure_loaded_already_loaded(self):
        """ensure_loaded returns True immediately if model already loaded."""
        svc = EmbeddingService("test-model")
        svc._model = MagicMock()

        result = await svc.ensure_loaded()
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_loaded_previous_error(self):
        """ensure_loaded returns False if a previous load error exists."""
        svc = EmbeddingService("test-model")
        svc._load_error = "previous error"

        result = await svc.ensure_loaded()
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_loaded_failure(self):
        """ensure_loaded records error on failure."""
        svc = EmbeddingService("test-model")

        with patch("anyio.to_thread.run_sync", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ImportError("no module")
            result = await svc.ensure_loaded()

        assert result is False
        assert svc._load_error is not None


class TestEmbedTexts:
    """Test text embedding."""

    @pytest.mark.asyncio
    async def test_embed_texts_returns_correct_shape(self):
        """embed_texts returns (N, dim) array."""
        svc = EmbeddingService("test-model")
        fake_vecs = np.random.randn(3, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vecs
        svc._model = mock_model

        with patch("anyio.to_thread.run_sync", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = lambda fn: fn()
            result = await svc.embed_texts(["a", "b", "c"])

        assert result.shape == (3, 384)
        mock_model.encode.assert_called_once_with(
            ["a", "b", "c"],
            show_progress_bar=False,
            normalize_embeddings=True,
        )

    @pytest.mark.asyncio
    async def test_embed_texts_empty_when_not_ready(self):
        """embed_texts returns empty array when model unavailable."""
        svc = EmbeddingService("test-model")
        svc._load_error = "not available"

        result = await svc.embed_texts(["test"])
        assert result.size == 0

    @pytest.mark.asyncio
    async def test_embed_single(self):
        """embed_single returns (dim,) array."""
        svc = EmbeddingService("test-model")
        fake_vec = np.random.randn(1, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vec
        svc._model = mock_model

        with patch("anyio.to_thread.run_sync", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = lambda fn: fn()
            result = await svc.embed_single("hello")

        assert result.shape == (384,)


class TestCosineSearch:
    """Test cosine similarity search."""

    def test_cosine_search_basic(self):
        """cosine_search returns ranked results."""
        # Create normalized vectors
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        index = np.array([
            [1.0, 0.0, 0.0],  # exact match → score 1.0
            [0.0, 1.0, 0.0],  # orthogonal → score 0.0
            [0.7, 0.7, 0.0],  # partial match
        ], dtype=np.float32)

        results = EmbeddingService.cosine_search(query, index, top_k=3)

        assert len(results) == 3
        # First result should be the exact match (index 0)
        assert results[0][0] == 0
        assert results[0][1] == pytest.approx(1.0, abs=0.01)
        # Last should be the orthogonal (index 1)
        assert results[-1][0] == 1

    def test_cosine_search_top_k(self):
        """cosine_search respects top_k limit."""
        query = np.array([1.0, 0.0], dtype=np.float32)
        index = np.random.randn(100, 2).astype(np.float32)

        results = EmbeddingService.cosine_search(query, index, top_k=5)
        assert len(results) == 5

    def test_cosine_search_empty_input(self):
        """cosine_search returns empty list for empty input."""
        query = np.empty(0, dtype=np.float32)
        index = np.empty((0, 0), dtype=np.float32)

        results = EmbeddingService.cosine_search(query, index, top_k=5)
        assert results == []

    def test_cosine_search_descending_order(self):
        """cosine_search results are sorted by descending score."""
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        index = np.array([
            [0.1, 0.9, 0.0],
            [0.5, 0.5, 0.0],
            [0.9, 0.1, 0.0],
        ], dtype=np.float32)

        results = EmbeddingService.cosine_search(query, index, top_k=3)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)
