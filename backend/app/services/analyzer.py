"""Prompt analyzer service - analyzes raw prompts to identify characteristics."""

import logging
from dataclasses import dataclass

from app.prompts.analyzer_prompt import ANALYZER_SYSTEM_PROMPT
from app.providers import LLMProvider, get_provider
from app.providers.types import CompletionRequest, TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result from analyzing a raw prompt."""

    task_type: str
    complexity: str
    weaknesses: list[str]
    strengths: list[str]


_MAX_LIST_ITEMS = 20


def _ensure_string_list(value: list | None) -> list[str]:
    """Coerce a list of arbitrary items to a list of non-empty strings.

    Handles None, non-string items, and empty strings from LLM responses.
    Truncates to _MAX_LIST_ITEMS to prevent oversized payloads.
    """
    if not value:
        return []
    items = [str(item) for item in value if item is not None and str(item).strip()]
    if len(items) > _MAX_LIST_ITEMS:
        logger.warning(
            "_ensure_string_list: LLM returned %d items, truncating to %d",
            len(items), _MAX_LIST_ITEMS,
        )
        items = items[:_MAX_LIST_ITEMS]
    return items


_VALID_TASK_TYPES: frozenset[str] = frozenset({
    "reasoning", "analysis", "math",
    "classification", "formatting", "extraction",
    "coding", "writing", "creative", "medical", "legal",
    "general", "education", "other",
})

_VALID_COMPLEXITIES: frozenset[str] = frozenset({"low", "medium", "high"})

_DEFAULT_TASK_TYPE = "general"
_DEFAULT_COMPLEXITY = "medium"


class PromptAnalyzer:
    """Analyzes prompts to determine task type, complexity, strengths, and weaknesses.

    Uses an LLM provider to perform deep analysis of prompt structure, intent, and quality.
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider or get_provider()
        self.last_usage: TokenUsage | None = None

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
        request = CompletionRequest(
            system_prompt=ANALYZER_SYSTEM_PROMPT,
            user_message=user_message,
        )
        response, completion = await self.llm.complete_json(request)
        self.last_usage = completion.usage

        task_type = str(response.get("task_type", _DEFAULT_TASK_TYPE)).lower().strip()
        if task_type not in _VALID_TASK_TYPES:
            logger.warning(
                "Unknown task_type %r from LLM, defaulting to %r",
                task_type, _DEFAULT_TASK_TYPE,
            )
            task_type = _DEFAULT_TASK_TYPE

        complexity = str(response.get("complexity", _DEFAULT_COMPLEXITY)).lower().strip()
        if complexity not in _VALID_COMPLEXITIES:
            logger.warning(
                "Unknown complexity %r from LLM, defaulting to %r",
                complexity, _DEFAULT_COMPLEXITY,
            )
            complexity = _DEFAULT_COMPLEXITY

        return AnalysisResult(
            task_type=task_type,
            complexity=complexity,
            weaknesses=_ensure_string_list(response.get("weaknesses", [])),
            strengths=_ensure_string_list(response.get("strengths", [])),
        )
