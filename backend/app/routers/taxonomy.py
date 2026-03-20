"""Taxonomy tree API endpoints — tree, node detail, stats, recluster.

Spec Section 6.6.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.embedding_service import EmbeddingService
from app.services.taxonomy import TaxonomyEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])


def _get_engine(request: Request) -> TaxonomyEngine:
    """Retrieve the singleton TaxonomyEngine from app.state.
    Falls back to a minimal read-only instance if not initialized.
    """
    engine = getattr(request.app.state, "taxonomy_engine", None)
    if engine:
        return engine
    return TaxonomyEngine(embedding_service=EmbeddingService())


@router.get("/tree")
async def get_tree(
    request: Request,
    min_persistence: float = 0.0,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full taxonomy tree for 3D visualization."""
    engine = _get_engine(request)
    nodes = await engine.get_tree(db, min_persistence=min_persistence)
    return {"nodes": nodes}


@router.get("/node/{node_id}")
async def get_node(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Single taxonomy node with children, breadcrumb, and metrics."""
    engine = _get_engine(request)
    node = await engine.get_node(node_id, db)
    if node is None:
        raise HTTPException(status_code=404, detail="Taxonomy node not found")
    return node


@router.get("/stats")
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """System quality metrics and snapshot history."""
    engine = _get_engine(request)
    return await engine.get_stats(db)


@router.post("/recluster")
async def trigger_recluster(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manual cold-path trigger — full HDBSCAN + UMAP recomputation."""
    engine = _get_engine(request)
    try:
        result = await engine.run_cold_path(db)
        if result is None:
            return {"status": "skipped", "reason": "lock held"}
        return {
            "status": "completed",
            "snapshot_id": result.snapshot_id,
            "q_system": result.q_system,
            "nodes_created": result.nodes_created,
            "nodes_updated": result.nodes_updated,
            "umap_fitted": result.umap_fitted,
        }
    except Exception as exc:
        logger.error("Manual recluster failed: %s", exc, exc_info=True)
        raise HTTPException(500, "Recluster failed") from exc
