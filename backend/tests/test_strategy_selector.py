"""Tests for the strategy selector service (pure logic, no mocking needed)."""

from app.services.analyzer import AnalysisResult
from app.services.strategy_selector import (
    _STRATEGY_REASON_MAP,
    TASK_TYPE_STRATEGY_MAP,
    StrategySelector,
    _build_reasoning,
)


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

    # --- Task-type mapping: chain-of-thought group ---

    def test_reasoning_task_selects_chain_of_thought(self):
        result = self.selector.select(_make_analysis(task_type="reasoning"))
        assert result.strategy == "chain-of-thought"

    def test_analysis_task_selects_chain_of_thought(self):
        result = self.selector.select(_make_analysis(task_type="analysis"))
        assert result.strategy == "chain-of-thought"

    def test_math_task_selects_chain_of_thought(self):
        result = self.selector.select(_make_analysis(task_type="math"))
        assert result.strategy == "chain-of-thought"

    # --- Task-type mapping: few-shot group ---

    def test_classification_task_selects_few_shot(self):
        result = self.selector.select(_make_analysis(task_type="classification"))
        assert result.strategy == "few-shot"

    def test_formatting_task_selects_few_shot(self):
        result = self.selector.select(_make_analysis(task_type="formatting"))
        assert result.strategy == "few-shot"

    def test_extraction_task_selects_few_shot(self):
        result = self.selector.select(_make_analysis(task_type="extraction"))
        assert result.strategy == "few-shot"

    # --- Task-type mapping: role-based group ---

    def test_coding_task_selects_role_based(self):
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert result.strategy == "role-based"

    def test_writing_task_selects_role_based(self):
        result = self.selector.select(_make_analysis(task_type="writing"))
        assert result.strategy == "role-based"

    def test_creative_task_selects_role_based(self):
        result = self.selector.select(_make_analysis(task_type="creative"))
        assert result.strategy == "role-based"

    def test_medical_task_selects_role_based(self):
        result = self.selector.select(_make_analysis(task_type="medical"))
        assert result.strategy == "role-based"

    def test_legal_task_selects_role_based(self):
        result = self.selector.select(_make_analysis(task_type="legal"))
        assert result.strategy == "role-based"

    # --- Task-type mapping: structured-enhancement group ---

    def test_general_task_selects_structured_enhancement(self):
        result = self.selector.select(_make_analysis(task_type="general"))
        assert result.strategy == "structured-enhancement"

    def test_education_task_selects_structured_enhancement(self):
        result = self.selector.select(_make_analysis(task_type="education"))
        assert result.strategy == "structured-enhancement"

    def test_other_task_selects_structured_enhancement(self):
        result = self.selector.select(_make_analysis(task_type="other"))
        assert result.strategy == "structured-enhancement"

    # --- Unknown task type fallback ---

    def test_unknown_task_type_falls_back_to_structured_enhancement(self):
        result = self.selector.select(_make_analysis(task_type="completely_unknown"))
        assert result.strategy == "structured-enhancement"

    # --- Priority 1: High complexity override ---

    def test_high_complexity_overrides_general_task(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="general"))
        assert result.strategy == "chain-of-thought"

    def test_high_complexity_overrides_coding_task(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="coding"))
        assert result.strategy == "chain-of-thought"

    # --- Priority 2: Specificity weakness override ---

    def test_specificity_weakness_overrides_coding_task(self):
        """A coding task with specificity weakness should get constraint-focused, not role-based."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Lacks specific details"])
        )
        assert result.strategy == "constraint-focused"

    def test_specificity_weakness_on_general_task(self):
        result = self.selector.select(
            _make_analysis(task_type="general", weaknesses=["Not specific enough"])
        )
        assert result.strategy == "constraint-focused"

    # --- Priority interactions ---

    def test_high_complexity_beats_specificity_weakness(self):
        """Priority 1 (high complexity) should beat priority 2 (specificity weakness)."""
        result = self.selector.select(
            _make_analysis(
                complexity="high",
                task_type="coding",
                weaknesses=["Lacks specific details"],
            )
        )
        assert result.strategy == "chain-of-thought"

    # --- Reasoning string content ---

    def test_reasoning_contains_task_type(self):
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert "coding" in result.reasoning

    def test_reasoning_contains_strategy_name(self):
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert "role-based" in result.reasoning


class TestBuildReasoning:
    def test_format(self):
        result = _build_reasoning("chain-of-thought", "math", "needs step-by-step.")
        assert result == "Selected chain-of-thought for math task: needs step-by-step."


class TestTaskTypeStrategyMap:
    def test_all_14_task_types_covered(self):
        expected_types = {
            "reasoning", "analysis", "math",
            "classification", "formatting", "extraction",
            "coding", "writing", "creative", "medical", "legal",
            "general", "education", "other",
        }
        assert set(TASK_TYPE_STRATEGY_MAP.keys()) == expected_types

    def test_map_values_are_valid_strategies(self):
        valid_strategies = {
            "chain-of-thought", "few-shot", "role-based",
            "structured-enhancement", "constraint-focused",
        }
        for strategy in TASK_TYPE_STRATEGY_MAP.values():
            assert strategy in valid_strategies


class TestStrategyReasonMap:
    def test_reason_map_covers_all_strategies(self):
        valid_strategies = {
            "chain-of-thought", "few-shot", "role-based",
            "structured-enhancement", "constraint-focused",
        }
        assert set(_STRATEGY_REASON_MAP.keys()) == valid_strategies
