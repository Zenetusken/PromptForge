"""Prompt optimizer service - applies optimization strategies to improve prompts."""

import json
import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from apps.promptforge.constants import Strategy
from apps.promptforge.prompts.optimizer_prompts import OPTIMIZER_SYSTEM_PROMPT
from app.providers import LLMProvider, get_provider
from app.providers.types import CompletionRequest, TokenUsage
from apps.promptforge.services.analyzer import AnalysisResult, _ensure_string_list

if TYPE_CHECKING:
    from apps.promptforge.schemas.context import CodebaseContext

logger = logging.getLogger(__name__)


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

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider or get_provider()
        self.last_usage: TokenUsage | None = None

    async def optimize(
        self,
        raw_prompt: str,
        analysis: AnalysisResult,
        strategy: str = Strategy.ROLE_TASK_FORMAT,
        secondary_frameworks: list[str] | None = None,
        *,
        codebase_context: CodebaseContext | None = None,
    ) -> OptimizationResult:
        """Optimize a raw prompt based on its analysis and chosen strategy.

        Args:
            raw_prompt: The original prompt text.
            analysis: The analysis results from PromptAnalyzer.
            strategy: The primary optimization strategy to apply.
            secondary_frameworks: Optional 0-2 secondary frameworks to combine.
            codebase_context: Optional codebase context to ground the optimization.

        Returns:
            An OptimizationResult with the optimized prompt and metadata.
        """
        payload: dict = {
            "raw_prompt": raw_prompt,
            "analysis": asdict(analysis),
            "strategy": strategy,
        }
        if secondary_frameworks:
            payload["secondary_frameworks"] = secondary_frameworks
        if codebase_context:
            rendered = codebase_context.render()
            if rendered:
                payload["codebase_context"] = rendered
        user_message = json.dumps(payload)
        request = CompletionRequest(
            system_prompt=OPTIMIZER_SYSTEM_PROMPT,
            user_message=user_message,
        )
        response, completion = await self.llm.complete_json(request)
        self.last_usage = completion.usage
        optimized = response.get("optimized_prompt")
        if not optimized:
            logger.warning("LLM returned no optimized_prompt; falling back to raw prompt")
            optimized = raw_prompt
        return OptimizationResult(
            optimized_prompt=optimized,
            framework_applied=response.get("framework_applied", strategy),
            changes_made=_ensure_string_list(response.get("changes_made", [])),
            optimization_notes=response.get("optimization_notes", ""),
        )
