"""DomainResolver — cached domain label lookup.

Replaces the ``VALID_DOMAINS`` constant with a live query against
``PromptCluster`` nodes where ``state='domain'``.  Cached in memory
with event-bus invalidation.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromptCluster
from app.services.pipeline_constants import DOMAIN_CONFIDENCE_GATE
from app.utils.text_cleanup import parse_domain

logger = logging.getLogger(__name__)

# Module-level singleton — set by main.py lifespan, read by pipeline/tools
_instance: DomainResolver | None = None


def get_domain_resolver() -> DomainResolver:
    """Return the process-level DomainResolver or raise if not initialized."""
    if _instance is None:
        raise ValueError("DomainResolver not initialized")
    return _instance


def set_domain_resolver(resolver: DomainResolver | None) -> None:
    """Set the process-level DomainResolver (called by lifespan)."""
    global _instance
    _instance = resolver


class DomainResolver:
    """Resolve free-form domain strings to known domain node labels."""

    def __init__(self) -> None:
        self._domain_labels: set[str] = set()
        self._cache: dict[str, str] = {}

    @property
    def domain_labels(self) -> set[str]:
        return set(self._domain_labels)

    async def load(self, db: AsyncSession) -> None:
        result = await db.execute(
            select(PromptCluster.label).where(PromptCluster.state == "domain")
        )
        self._domain_labels = {row[0] for row in result}
        self._cache.clear()
        logger.info("DomainResolver loaded %d domain labels", len(self._domain_labels))

    async def resolve(
        self, db: AsyncSession, domain_raw: str | None, confidence: float,
    ) -> str:
        """Resolve a free-form domain string to a known domain label.

        This method NEVER raises — any exception returns "general".
        """
        try:
            if not domain_raw or not domain_raw.strip():
                return "general"
            if confidence < DOMAIN_CONFIDENCE_GATE:
                logger.debug(
                    "Domain confidence gate: %.2f < %.2f, defaulting to 'general'",
                    confidence, DOMAIN_CONFIDENCE_GATE,
                )
                return "general"
            primary, _ = parse_domain(domain_raw)
            if primary in self._cache:
                return self._cache[primary]
            if primary in self._domain_labels:
                self._cache[primary] = primary
                return primary
            self._cache[primary] = "general"
            return "general"
        except Exception:
            logger.warning(
                "DomainResolver.resolve() failed for '%s', defaulting to 'general'",
                domain_raw, exc_info=True,
            )
            return "general"
