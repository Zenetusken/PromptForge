"""Tests for the strategy selector service (pure logic, no mocking needed)."""

from app.services.analyzer import AnalysisResult
from app.services.strategy_selector import StrategySelector


def _make_analysis(
    task_type: str = "general",
    complexity: str = "medium",
    weaknesses: list[str] | None = None,
    strengths: list[str] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        task_type=task_type,
        complexity=complexity,
        weaknesses=weaknesses or [],
        strengths=strengths or [],
    )


class TestStrategySelector:
    def setup_method(self):
        self.selector = StrategySelector()

    def test_high_complexity_selects_chain_of_thought(self):
        analysis = _make_analysis(complexity="high", task_type="general")
        result = self.selector.select(analysis)
        assert result.strategy == "chain-of-thought"

    def test_reasoning_task_selects_chain_of_thought(self):
        analysis = _make_analysis(task_type="reasoning")
        result = self.selector.select(analysis)
        assert result.strategy == "chain-of-thought"

    def test_classification_task_selects_few_shot(self):
        analysis = _make_analysis(task_type="classification")
        result = self.selector.select(analysis)
        assert result.strategy == "few-shot"

    def test_coding_task_selects_role_based(self):
        analysis = _make_analysis(task_type="coding")
        result = self.selector.select(analysis)
        assert result.strategy == "role-based"

    def test_specificity_weakness_selects_constraint_focused(self):
        analysis = _make_analysis(weaknesses=["Lacks specific details"])
        result = self.selector.select(analysis)
        assert result.strategy == "constraint-focused"

    def test_default_selects_structured_enhancement(self):
        analysis = _make_analysis()
        result = self.selector.select(analysis)
        assert result.strategy == "structured-enhancement"
