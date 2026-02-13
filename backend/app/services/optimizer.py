"""Prompt optimizer service - applies optimization strategies to improve prompts."""

from dataclasses import dataclass

from app.services.analyzer import AnalysisResult
from app.services.claude_client import ClaudeClient
from app.prompts.optimizer_prompts import OPTIMIZER_SYSTEM_PROMPT


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

    def __init__(self, claude_client: ClaudeClient | None = None):
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
        # TODO: Replace with actual Claude API call using OPTIMIZER_SYSTEM_PROMPT
        # user_message = json.dumps({
        #     "raw_prompt": raw_prompt,
        #     "analysis": asdict(analysis),
        #     "strategy": strategy,
        # })
        # response = await self.claude_client.send_message_json(
        #     system_prompt=OPTIMIZER_SYSTEM_PROMPT,
        #     user_message=user_message,
        # )
        # return OptimizationResult(**response)

        # Mock optimization for now
        optimized = (
            f"You are an expert assistant. Your task is as follows:\n\n"
            f"{raw_prompt}\n\n"
            f"Please provide a detailed, well-structured response. "
            f"Include specific examples where relevant. "
            f"Format your output using clear headings and bullet points."
        )

        return OptimizationResult(
            optimized_prompt=optimized,
            framework_applied=strategy,
            changes_made=[
                "Added role definition",
                "Specified output format",
                "Added structure requirements",
                "Enhanced specificity",
            ],
            optimization_notes=(
                "Applied structured enhancement framework to improve "
                "clarity and specificity."
            ),
        )
