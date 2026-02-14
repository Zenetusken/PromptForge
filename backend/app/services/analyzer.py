"""Prompt analyzer service - analyzes raw prompts to identify characteristics."""

from dataclasses import dataclass

from app.prompts.analyzer_prompt import ANALYZER_SYSTEM_PROMPT
from app.services.claude_client import ClaudeClient


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

    def __init__(self, claude_client: ClaudeClient | None = None) -> None:
        self.claude_client = claude_client or ClaudeClient()

    async def analyze(self, raw_prompt: str) -> AnalysisResult:
        """Analyze a raw prompt and return structured analysis.

        Args:
            raw_prompt: The original prompt text to analyze.

        Returns:
            An AnalysisResult with task_type, complexity, weaknesses, and strengths.
        """
        user_message = (
            f"Analyze the following prompt and return your analysis as JSON:\n\n"
            f"---\n{raw_prompt}\n---"
        )
        response = await self.claude_client.send_message_json(
            system_prompt=ANALYZER_SYSTEM_PROMPT,
            user_message=user_message,
        )
        return AnalysisResult(
            task_type=response.get("task_type", "general"),
            complexity=response.get("complexity", "medium"),
            weaknesses=response.get("weaknesses", []),
            strengths=response.get("strengths", []),
        )
