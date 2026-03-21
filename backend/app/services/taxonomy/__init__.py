"""Evolutionary Taxonomy Engine — self-organizing hierarchical clustering.

Public API:
    TaxonomyEngine — unified orchestrator
    TaxonomyMapping — domain mapping result
    PatternMatch — pattern matching result
    QWeights — quality metric weights
    SparklineData — sparkline-ready Q_system history data
    compute_sparkline_data — transform raw Q values into sparkline data
"""

from app.services.taxonomy.engine import (
    PatternMatch,
    TaxonomyEngine,
    TaxonomyMapping,
)
from app.services.taxonomy.quality import QWeights
from app.services.taxonomy.sparkline import SparklineData, compute_sparkline_data

__all__ = [
    "PatternMatch",
    "QWeights",
    "SparklineData",
    "TaxonomyEngine",
    "TaxonomyMapping",
    "compute_sparkline_data",
]
