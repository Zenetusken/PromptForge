"""Prompt validator service - validates optimization quality and faithfulness."""

import json
from dataclasses import dataclass

from app.prompts.validator_prompt import VALIDATOR_SYSTEM_PROMPT
from app.services.claude_client import ClaudeClient


@dataclass
class ValidationResult:
    """Result from validating an optimized prompt."""

    clarity_score: float
    specificity_score: float
    structure_score: float
    faithfulness_score: float
    overall_score: float
    is_improvement: bool
    verdict: str


class PromptValidator:
    """Validates optimized prompts against the original for quality assurance.

    Scores the optimization across multiple dimensions and determines
    whether it is a genuine improvement over the original.
    """

    def __init__(self, claude_client: ClaudeClient | None = None) -> None:
        self.claude_client = claude_client or ClaudeClient()

    async def validate(
        self,
        raw_prompt: str,
        optimized_prompt: str,
    ) -> ValidationResult:
        """Validate the quality of an optimized prompt against the original.

        Args:
            raw_prompt: The original prompt text.
            optimized_prompt: The optimized prompt text to validate.

        Returns:
            A ValidationResult with scores and improvement verdict.
        """
        user_message = json.dumps({
            "raw_prompt": raw_prompt,
            "optimized_prompt": optimized_prompt,
        })
        response = await self.claude_client.send_message_json(
            system_prompt=VALIDATOR_SYSTEM_PROMPT,
            user_message=user_message,
        )
        def _clamp_score(key: str) -> float:
            try:
                val = float(response.get(key, 0.5))
            except (TypeError, ValueError):
                val = 0.5
            return max(0.0, min(1.0, val))

        return ValidationResult(
            clarity_score=_clamp_score("clarity_score"),
            specificity_score=_clamp_score("specificity_score"),
            structure_score=_clamp_score("structure_score"),
            faithfulness_score=_clamp_score("faithfulness_score"),
            overall_score=_clamp_score("overall_score"),
            is_improvement=bool(response.get("is_improvement", False)),
            verdict=response.get("verdict", "No verdict available."),
        )
