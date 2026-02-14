"""Strategy selector service - chooses the best optimization strategy for a prompt."""

from dataclasses import dataclass

from app.services.analyzer import AnalysisResult


@dataclass
class StrategySelection:
    """The selected optimization strategy and reasoning."""

    strategy: str
    reasoning: str


# Maps each analyzer task_type to its default strategy.
# Unknown task types fall through to structured-enhancement.
TASK_TYPE_STRATEGY_MAP: dict[str, str] = {
    "reasoning": "chain-of-thought",
    "analysis": "chain-of-thought",
    "math": "chain-of-thought",
    "classification": "few-shot",
    "formatting": "few-shot",
    "extraction": "few-shot",
    "coding": "role-based",
    "writing": "role-based",
    "creative": "role-based",
    "medical": "role-based",
    "legal": "role-based",
    "general": "structured-enhancement",
    "education": "structured-enhancement",
    "other": "structured-enhancement",
}

_DEFAULT_STRATEGY = "structured-enhancement"

# Maps each strategy to its human-readable reasoning suffix.
_STRATEGY_REASON_MAP: dict[str, str] = {
    "chain-of-thought": "enables step-by-step reasoning.",
    "few-shot": "provides concrete examples for pattern-based tasks.",
    "role-based": "leverages domain-specific expert persona.",
    "structured-enhancement": "applies general structural improvements.",
}


def _build_reasoning(strategy: str, task_type: str, reason: str) -> str:
    """Build a consistent reasoning string."""
    return f"Selected {strategy} for {task_type} task: {reason}"


class StrategySelector:
    """Selects the most appropriate optimization strategy based on prompt analysis.

    Uses task type, complexity, and identified weaknesses to choose
    the best optimization approach.

    Priority order:
      1. High complexity → chain-of-thought (always)
      2. Specificity weakness → constraint-focused (before task-type lookup)
      3. Task-type map → lookup with structured-enhancement fallback
    """

    def select(self, analysis: AnalysisResult) -> StrategySelection:
        """Select the best optimization strategy given an analysis result.

        Args:
            analysis: The analysis result from PromptAnalyzer.

        Returns:
            A StrategySelection with the chosen strategy name and reasoning.
        """
        # Priority 1: High complexity always gets chain-of-thought
        if analysis.complexity == "high":
            return StrategySelection(
                strategy="chain-of-thought",
                reasoning=_build_reasoning(
                    "chain-of-thought",
                    analysis.task_type,
                    "high complexity requires step-by-step reasoning.",
                ),
            )

        # Priority 2: Specificity weakness → constraint-focused
        # (checked BEFORE task-type lookup so e.g. a coding task with
        # vague wording correctly gets constraint-focused, not role-based)
        has_specificity_weakness = any(
            "specific" in w.lower() for w in analysis.weaknesses
        )
        if has_specificity_weakness:
            return StrategySelection(
                strategy="constraint-focused",
                reasoning=_build_reasoning(
                    "constraint-focused",
                    analysis.task_type,
                    "addressing identified specificity weaknesses.",
                ),
            )

        # Priority 3: Task-type map with fallback
        strategy = TASK_TYPE_STRATEGY_MAP.get(analysis.task_type, _DEFAULT_STRATEGY)
        reason = _STRATEGY_REASON_MAP.get(strategy, "applies general structural improvements.")

        return StrategySelection(
            strategy=strategy,
            reasoning=_build_reasoning(strategy, analysis.task_type, reason),
        )
