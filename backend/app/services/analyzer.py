"""Prompt analyzer service - analyzes raw prompts to identify characteristics."""

from dataclasses import dataclass

from app.services.claude_client import ClaudeClient
from app.prompts.analyzer_prompt import ANALYZER_SYSTEM_PROMPT


@dataclass
class AnalysisResult:
    """Result from analyzing a raw prompt."""

    task_type: str
    complexity: str
    weaknesses: list[str]
    strengths: list[str]


class PromptAnalyzer:
    """Analyzes prompts to determine task type, complexity, strengths, and weaknesses.

    Uses Claude to perform deep analysis of prompt structure, intent, and quality.
    """

    def __init__(self, claude_client: ClaudeClient | None = None):
        self.claude_client = claude_client or ClaudeClient()

    async def analyze(self, raw_prompt: str) -> AnalysisResult:
        """Analyze a raw prompt and return structured analysis.

        Args:
            raw_prompt: The original prompt text to analyze.

        Returns:
            An AnalysisResult with task_type, complexity, weaknesses, and strengths.
        """
        # TODO: Replace with actual Claude API call using ANALYZER_SYSTEM_PROMPT
        # response = await self.claude_client.send_message_json(
        #     system_prompt=ANALYZER_SYSTEM_PROMPT,
        #     user_message=raw_prompt,
        # )
        # return AnalysisResult(**response)

        # Mock analysis for now
        return AnalysisResult(
            task_type="general",
            complexity="medium",
            weaknesses=["Lacks specificity", "No output format specified"],
            strengths=["Clear intent", "Good context"],
        )
