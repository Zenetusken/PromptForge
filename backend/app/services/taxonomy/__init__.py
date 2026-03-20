"""Evolutionary Taxonomy Engine — self-organizing hierarchical clustering.

Public API:
    TaxonomyEngine — unified orchestrator
    TaxonomyMapping — domain mapping result
    PatternMatch — pattern matching result
    QWeights — quality metric weights
"""

from app.services.taxonomy.engine import (
    PatternMatch,
    TaxonomyEngine,
    TaxonomyMapping,
)
from app.services.taxonomy.quality import QWeights

__all__ = [
    "PatternMatch",
    "QWeights",
    "TaxonomyEngine",
    "TaxonomyMapping",
]
