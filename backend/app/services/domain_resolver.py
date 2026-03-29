"""DomainResolver — cached domain label lookup with signal cross-validation.

Replaces the ``VALID_DOMAINS`` constant with a live query against
``PromptCluster`` nodes where ``state='domain'``.  Cached in memory
with event-bus invalidation.

Layer 1: blends keyword signal confidence with analyzer confidence
for gate decisions on unknown domains.

Layer 2: logs divergence when LLM domain and signal-based domain
disagree (observability, no override).

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
        self._signal_loader = None

    @property
    def domain_labels(self) -> set[str]:
        return set(self._domain_labels)

    async def load(self, db: AsyncSession) -> None:
        result = await db.execute(
            select(PromptCluster.label).where(PromptCluster.state == "domain")
        )
        self._domain_labels = {row[0] for row in result}
        self._cache.clear()
        # Attach signal loader for cross-validation
        from app.services.domain_signal_loader import get_signal_loader
        self._signal_loader = get_signal_loader()
        logger.info("DomainResolver loaded %d domain labels", len(self._domain_labels))

    async def resolve(
        self,
        domain_raw: str | None,
        confidence: float,
        raw_prompt: str | None = None,
    ) -> str:
        """Resolve a free-form domain string to a known domain label.

        Args:
            domain_raw: The LLM's domain output (e.g., "backend", "backend: auth").
            confidence: Analyzer's overall confidence score (0.0-1.0).
            raw_prompt: Original prompt text for signal cross-validation (optional).

        This method NEVER raises — any exception returns "general".
        """
        try:
            if not domain_raw or not domain_raw.strip():
                return "general"
            primary, _ = parse_domain(domain_raw)

            # Cache hit
            if primary in self._cache:
                return self._cache[primary]

            # Known domain label — accept regardless of confidence.
            if primary in self._domain_labels:
                # Layer 1: log signal divergence for observability
                if self._signal_loader and raw_prompt:
                    self._log_signal_divergence(primary, raw_prompt)
                self._cache[primary] = primary
                return primary

            # Unknown domain: blend signal confidence for gate decision
            blended = confidence
            if self._signal_loader and raw_prompt:
                blended = self._blend_confidence(confidence, raw_prompt)

            if blended < DOMAIN_CONFIDENCE_GATE:
                logger.debug(
                    "Domain confidence gate: unknown '%s' blended=%.2f < %.2f → 'general'",
                    primary, blended, DOMAIN_CONFIDENCE_GATE,
                )
                self._cache[primary] = "general"
                return "general"

            self._cache[primary] = "general"
            return "general"
        except Exception:
            logger.warning(
                "DomainResolver.resolve() failed for '%s', defaulting to 'general'",
                domain_raw, exc_info=True,
            )
            return "general"

    def _blend_confidence(self, analyzer_confidence: float, raw_prompt: str) -> float:
        """Blend analyzer confidence with keyword signal confidence."""
        words = set(raw_prompt.lower().split())
        scores = self._signal_loader.score(words)
        if not scores:
            return analyzer_confidence
        top_score = max(scores.values())
        signal_confidence = min(1.0, top_score / 3.0)  # normalize: 3.0+ signals = full confidence
        blended = 0.6 * analyzer_confidence + 0.4 * signal_confidence
        return blended

    def _log_signal_divergence(self, llm_domain: str, raw_prompt: str) -> None:
        """Log when LLM domain and signal-based domain disagree."""
        words = set(raw_prompt.lower().split())
        scores = self._signal_loader.score(words)
        if not scores:
            return
        top_signal = max(scores, key=scores.get)
        if top_signal != llm_domain:
            llm_score = scores.get(llm_domain, 0)
            top_score = scores[top_signal]
            if top_score > llm_score + 1.0:
                logger.info(
                    "Domain signal divergence: llm='%s'(%.1f) vs signals='%s'(%.1f)",
                    llm_domain, llm_score, top_signal, top_score,
                )
