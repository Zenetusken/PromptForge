"""Singleton embedding service for local sentence-transformers inference.

Provides batch embedding and cosine similarity search for the repo index
service. The model is loaded lazily on first use and all blocking inference
is offloaded to a worker thread via ``anyio.to_thread.run_sync()``.

When ``sentence-transformers`` is not installed or the model fails to load,
``is_ready`` returns False and callers should fall back to keyword matching.

Usage::

    from app.services.embedding_service import get_embedding_service

    svc = get_embedding_service()
    if await svc.ensure_loaded():
        vecs = await svc.embed_texts(["hello", "world"])
        results = svc.cosine_search(query_vec, index_vecs, top_k=10)
"""

import logging
import time
from typing import Optional

import anyio
import numpy as np

logger = logging.getLogger(__name__)

# Default model: 384-dimensional vectors, ~80 MB, CPU-only
_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class EmbeddingService:
    """Singleton embedding service using sentence-transformers.

    Provides batch embedding and cosine similarity search for the
    repo index service. Model is loaded lazily on first use.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None  # SentenceTransformer, loaded lazily
        self._load_error: str | None = None

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True if model is loaded or loadable (no previous load error)."""
        return self._model is not None or self._load_error is None

    # ── Loading ──────────────────────────────────────────────────────────

    async def ensure_loaded(self) -> bool:
        """Load the model if not already loaded. Returns True on success.

        Uses ``anyio.to_thread.run_sync`` for the blocking model load.
        """
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False

        def _load() -> object:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Install with: pip install sentence-transformers"
                ) from exc
            return SentenceTransformer(self._model_name)

        t0 = time.perf_counter()
        try:
            self._model = await anyio.to_thread.run_sync(_load)
            elapsed = time.perf_counter() - t0
            logger.info(
                "Embedding model '%s' loaded in %.2fs",
                self._model_name,
                elapsed,
            )
            return True
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            self._load_error = str(exc)
            logger.error(
                "Failed to load embedding model '%s' after %.2fs: %s",
                self._model_name,
                elapsed,
                exc,
            )
            return False

    # ── Embedding ────────────────────────────────────────────────────────

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Batch embed texts. Returns (N, 384) array.

        Uses ``anyio.to_thread.run_sync`` for the blocking encode call.
        Returns an empty array if the model is not ready.
        """
        if not await self.ensure_loaded():
            return np.empty((0, 0), dtype=np.float32)

        model = self._model

        def _encode() -> np.ndarray:
            return model.encode(
                texts,
                show_progress_bar=False,
                normalize_embeddings=True,
            )

        return await anyio.to_thread.run_sync(_encode)

    async def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text. Returns (384,) array."""
        result = await self.embed_texts([text])
        if result.size == 0:
            return np.empty(0, dtype=np.float32)
        return result[0]

    # ── Search ───────────────────────────────────────────────────────────

    @staticmethod
    def cosine_search(
        query_vec: np.ndarray,
        index_vecs: np.ndarray,
        top_k: int = 20,
    ) -> list[tuple[int, float]]:
        """Find top-k most similar vectors by cosine similarity.

        Returns list of ``(index, score)`` tuples sorted by descending score.
        Assumes all vectors are already L2-normalized (as produced by
        ``embed_texts`` with ``normalize_embeddings=True``), so cosine
        similarity reduces to a simple dot product.

        Pure numpy implementation, no external dependencies.
        """
        if index_vecs.size == 0 or query_vec.size == 0:
            return []

        # Dot product with normalized vectors == cosine similarity
        scores = index_vecs @ query_vec  # (N,)

        # Indices of top-k highest scores (ascending), then reverse
        k = min(top_k, len(scores))
        top_indices = np.argsort(scores)[-k:][::-1]

        return [(int(idx), float(scores[idx])) for idx in top_indices]


# ── Module-level singleton ───────────────────────────────────────────────────

_instance: Optional[EmbeddingService] = None


def get_embedding_service(
    model_name: str = _DEFAULT_MODEL,
) -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _instance
    if _instance is None:
        _instance = EmbeddingService(model_name)
    return _instance
