"""Prompt validator service - validates optimization quality and faithfulness."""

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from apps.promptforge.prompts.validator_prompt import VALIDATOR_SYSTEM_PROMPT
from app.providers import LLMProvider, get_provider
from app.providers.types import CompletionRequest, TokenUsage

if TYPE_CHECKING:
    from apps.promptforge.schemas.context import CodebaseContext

logger = logging.getLogger(__name__)

# Weights for server-side overall_score computation
CLARITY_WEIGHT = 0.20
SPECIFICITY_WEIGHT = 0.20
STRUCTURE_WEIGHT = 0.15
FAITHFULNESS_WEIGHT = 0.25
CONCISENESS_WEIGHT = 0.20


@dataclass
class ValidationResult:
    """Result from validating an optimized prompt."""

    clarity_score: float
    specificity_score: float
    structure_score: float
    faithfulness_score: float
    conciseness_score: float
    overall_score: float
    is_improvement: bool
    verdict: str
    detected_patterns: list[str] = field(default_factory=list)
    framework_adherence_score: float | None = None


def _fallback_verdict() -> str:
    """Return a fallback verdict string and log a warning."""
    logger.warning("LLM returned no verdict field; using fallback text")
    return "No verdict available."


class PromptValidator:
    """Validates optimized prompts against the original for quality assurance.

    Scores the optimization across multiple dimensions and determines
    whether it is a genuine improvement over the original.
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider or get_provider()
        self.last_usage: TokenUsage | None = None

    async def validate(
        self,
        raw_prompt: str,
        optimized_prompt: str,
        *,
        strategy: str | None = None,
        codebase_context: CodebaseContext | None = None,
    ) -> ValidationResult:
        """Validate the quality of an optimized prompt against the original.

        Args:
            raw_prompt: The original prompt text.
            optimized_prompt: The optimized prompt text to validate.
            strategy: The optimization strategy that was applied (for framework
                adherence scoring).
            codebase_context: Optional codebase context for scoring calibration.

        Returns:
            A ValidationResult with scores and improvement verdict.
        """
        payload: dict = {
            "raw_prompt": raw_prompt,
            "optimized_prompt": optimized_prompt,
        }
        if strategy:
            payload["strategy"] = strategy
        if codebase_context:
            rendered = codebase_context.render()
            if rendered:
                payload["codebase_context"] = rendered
        user_message = json.dumps(payload)
        request = CompletionRequest(
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            user_message=user_message,
        )
        response, completion = await self.llm.complete_json(request)
        self.last_usage = completion.usage

        def _clamp_score(key: str) -> float:
            try:
                val = float(response.get(key, 0.5))
            except (TypeError, ValueError):
                logger.warning("Non-numeric value for %r from LLM, defaulting to 0.5", key)
                val = 0.5
            return max(0.0, min(1.0, val))

        clarity = _clamp_score("clarity_score")
        specificity = _clamp_score("specificity_score")
        structure = _clamp_score("structure_score")
        faithfulness = _clamp_score("faithfulness_score")
        conciseness = _clamp_score("conciseness_score")

        # Weighted average computed server-side (never trust LLM arithmetic)
        overall = (
            clarity * CLARITY_WEIGHT
            + specificity * SPECIFICITY_WEIGHT
            + structure * STRUCTURE_WEIGHT
            + faithfulness * FAITHFULNESS_WEIGHT
            + conciseness * CONCISENESS_WEIGHT
        )

        # Parse detected_patterns from LLM response
        raw_patterns = response.get("detected_patterns")
        if isinstance(raw_patterns, list):
            detected_patterns = [str(p) for p in raw_patterns if p]
        else:
            detected_patterns = []

        # Cross-check is_improvement against computed overall_score.
        # The LLM judges subjectively, but extreme mismatches indicate
        # unreliable judgment — override to keep UI consistent with scores.
        llm_is_improvement = bool(response.get("is_improvement", False))
        overall_rounded = round(overall, 4)
        if overall_rounded < 0.4 and llm_is_improvement:
            logger.warning(
                "is_improvement cross-check: LLM says improvement but overall_score=%.4f < 0.4; "
                "overriding to False",
                overall_rounded,
            )
            is_improvement = False
        elif overall_rounded > 0.7 and not llm_is_improvement:
            logger.warning(
                "is_improvement cross-check: LLM says not improvement "
                "but overall_score=%.4f > 0.7; overriding to True",
                overall_rounded,
            )
            is_improvement = True
        else:
            is_improvement = llm_is_improvement

        # Extract framework_adherence_score (supplementary — NOT in weighted overall)
        raw_adherence = response.get("framework_adherence_score")
        if raw_adherence is not None:
            try:
                framework_adherence = max(0.0, min(1.0, float(raw_adherence)))
            except (TypeError, ValueError):
                framework_adherence = None
        else:
            framework_adherence = None

        return ValidationResult(
            clarity_score=clarity,
            specificity_score=specificity,
            structure_score=structure,
            faithfulness_score=faithfulness,
            conciseness_score=conciseness,
            overall_score=overall_rounded,
            is_improvement=is_improvement,
            verdict=response.get("verdict") or _fallback_verdict(),
            detected_patterns=detected_patterns,
            framework_adherence_score=framework_adherence,
        )
