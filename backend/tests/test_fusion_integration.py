"""Integration tests for composite embedding fusion."""
from __future__ import annotations

import numpy as np

from app.services.taxonomy.fusion import (
    CompositeQuery,
    PhaseWeights,
    adapt_weights,
    decay_toward_defaults,
)

DIM = 384

def test_full_fusion_pipeline():
    rng = np.random.RandomState(42)
    query = CompositeQuery(
        topic=rng.randn(DIM).astype(np.float32),
        transformation=rng.randn(DIM).astype(np.float32),
        output=rng.randn(DIM).astype(np.float32),
        pattern=rng.randn(DIM).astype(np.float32),
    )
    for phase in ["analysis", "optimization", "pattern_injection", "scoring"]:
        weights = PhaseWeights.for_phase(phase)
        fused = query.fuse(weights)
        assert fused.shape == (DIM,)
        assert abs(np.linalg.norm(fused) - 1.0) < 0.01

def test_adaptation_converges():
    current = PhaseWeights.for_phase("optimization")
    successful = PhaseWeights(w_topic=0.1, w_transform=0.6, w_output=0.2, w_pattern=0.1)
    for _ in range(50):
        current = adapt_weights(current, successful, alpha=0.1)
    assert abs(current.w_transform - successful.w_transform) < 0.1

def test_decay_prevents_lock_in():
    extreme = PhaseWeights(w_topic=0.9, w_transform=0.05, w_output=0.025, w_pattern=0.025)
    defaults = PhaseWeights.for_phase("optimization")
    decayed = extreme
    for _ in range(100):
        decayed = decay_toward_defaults(decayed, "optimization", rate=0.05)
    assert abs(decayed.w_topic - defaults.w_topic) < 0.15
