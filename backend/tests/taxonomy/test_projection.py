"""Tests for UMAP 3D projection and Procrustes alignment."""

import numpy as np
import pytest

from app.services.taxonomy.projection import (
    UMAPProjector,
    procrustes_align,
)


@pytest.fixture
def projector():
    return UMAPProjector(random_state=42)


class TestUMAPProjector:
    def test_fit_returns_3d(self, projector):
        """UMAP should produce 3-component output."""
        embeddings = [np.random.randn(384).astype(np.float32) for _ in range(20)]
        positions = projector.fit(embeddings)
        assert positions.shape == (20, 3)

    def test_transform_incremental(self, projector):
        """Incremental transform should be fast and consistent."""
        base = [np.random.randn(384).astype(np.float32) for _ in range(20)]
        projector.fit(base)

        new = [np.random.randn(384).astype(np.float32) for _ in range(3)]
        positions = projector.transform(new)
        assert positions.shape == (3, 3)

    def test_fit_too_few_points(self, projector):
        """Should handle < 5 points gracefully (UMAP needs minimum)."""
        embeddings = [np.random.randn(384).astype(np.float32) for _ in range(3)]
        positions = projector.fit(embeddings)
        # Fallback to PCA or random placement for small sets
        assert positions.shape == (3, 3)


class TestProcrustesAlign:
    def test_preserves_relative_positions(self):
        """Procrustes should find rotation that minimizes displacement."""
        old_pos = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
        # Rotate 90 degrees around z-axis
        new_pos = np.array([[0, 0, 0], [0, 1, 0], [-1, 0, 0]], dtype=np.float64)
        aligned = procrustes_align(new_pos, old_pos)
        # After alignment, should be close to old_pos
        np.testing.assert_allclose(aligned, old_pos, atol=0.1)

    def test_identity_unchanged(self):
        """Same positions should stay the same."""
        pos = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=np.float64)
        aligned = procrustes_align(pos, pos)
        np.testing.assert_allclose(aligned, pos, atol=1e-6)

    def test_handles_single_point(self):
        """Single point should return translated to match."""
        old = np.array([[1, 2, 3]], dtype=np.float64)
        new = np.array([[4, 5, 6]], dtype=np.float64)
        aligned = procrustes_align(new, old)
        np.testing.assert_allclose(aligned, old, atol=1e-6)
