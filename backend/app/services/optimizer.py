"""Prompt optimizer service - applies optimization strategies to improve prompts."""

import json
from dataclasses import asdict, dataclass

from app.prompts.optimizer_prompts import OPTIMIZER_SYSTEM_PROMPT
from app.services.analyzer import AnalysisResult
from app.services.claude_client import ClaudeClient


@dataclass
class OptimizationResult:
    """Result from optimizing a prompt."""

    optimized_prompt: str
    framework_applied: str
    changes_made: list[str]
    optimization_notes: str


class PromptOptimizer:
    """Optimizes prompts based on analysis results and selected strategies.

    Takes the raw prompt and analysis data to produce an enhanced version
    with documented changes and reasoning.
    """

    def __init__(self, claude_client: ClaudeClient | None = None) -> None:
        self.claude_client = claude_client or ClaudeClient()

    async def optimize(
        self,
        raw_prompt: str,
        analysis: AnalysisResult,
        strategy: str = "structured-enhancement",
    ) -> OptimizationResult:
        """Optimize a raw prompt based on its analysis and chosen strategy.

        Args:
            raw_prompt: The original prompt text.
            analysis: The analysis results from PromptAnalyzer.
            strategy: The optimization strategy to apply.

        Returns:
            An OptimizationResult with the optimized prompt and metadata.
        """
        user_message = json.dumps({
            "raw_prompt": raw_prompt,
            "analysis": asdict(analysis),
            "strategy": strategy,
        })
        response = await self.claude_client.send_message_json(
            system_prompt=OPTIMIZER_SYSTEM_PROMPT,
            user_message=user_message,
        )
        return OptimizationResult(
            optimized_prompt=response.get("optimized_prompt", raw_prompt),
            framework_applied=response.get("framework_applied", strategy),
            changes_made=response.get("changes_made", []),
            optimization_notes=response.get("optimization_notes", ""),
        )
