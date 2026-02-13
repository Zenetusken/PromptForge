"""Strategy selector service - chooses the best optimization strategy for a prompt."""

from dataclasses import dataclass

from app.services.analyzer import AnalysisResult


@dataclass
class StrategySelection:
    """The selected optimization strategy and reasoning."""

    strategy: str
    reasoning: str


# Available optimization strategies
STRATEGIES = {
    "structured-enhancement": (
        "Adds structure, role definitions, and output format specifications. "
        "Best for general-purpose prompts that lack organization."
    ),
    "chain-of-thought": (
        "Adds step-by-step reasoning instructions. "
        "Best for complex analytical or problem-solving prompts."
    ),
    "few-shot": (
        "Adds example input/output pairs. "
        "Best for classification, formatting, or pattern-following tasks."
    ),
    "role-based": (
        "Assigns a specific expert role and persona. "
        "Best for domain-specific or professional tasks."
    ),
    "constraint-focused": (
        "Adds explicit constraints and boundaries. "
        "Best for prompts that need precise output control."
    ),
}


class StrategySelector:
    """Selects the most appropriate optimization strategy based on prompt analysis.

    Uses task type, complexity, and identified weaknesses to choose
    the best optimization approach.
    """

    def select(self, analysis: AnalysisResult) -> StrategySelection:
        """Select the best optimization strategy given an analysis result.

        Args:
            analysis: The analysis result from PromptAnalyzer.

        Returns:
            A StrategySelection with the chosen strategy name and reasoning.
        """
        # Strategy selection logic based on analysis
        if analysis.complexity == "high" or analysis.task_type in (
            "reasoning",
            "analysis",
            "math",
        ):
            return StrategySelection(
                strategy="chain-of-thought",
                reasoning=(
                    f"Selected chain-of-thought for {analysis.complexity} complexity "
                    f"{analysis.task_type} task to enable step-by-step reasoning."
                ),
            )

        if analysis.task_type in ("classification", "formatting", "extraction"):
            return StrategySelection(
                strategy="few-shot",
                reasoning=(
                    f"Selected few-shot for {analysis.task_type} task "
                    f"to provide concrete examples."
                ),
            )

        if analysis.task_type in ("coding", "writing", "medical", "legal"):
            return StrategySelection(
                strategy="role-based",
                reasoning=(
                    f"Selected role-based for domain-specific "
                    f"{analysis.task_type} task."
                ),
            )

        has_specificity_weakness = any(
            "specific" in w.lower() for w in analysis.weaknesses
        )
        if has_specificity_weakness:
            return StrategySelection(
                strategy="constraint-focused",
                reasoning=(
                    "Selected constraint-focused to address identified "
                    "specificity weaknesses."
                ),
            )

        # Default strategy
        return StrategySelection(
            strategy="structured-enhancement",
            reasoning=(
                "Selected structured-enhancement as the default strategy "
                "for general improvement."
            ),
        )
