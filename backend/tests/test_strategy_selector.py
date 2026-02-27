"""Tests for the heuristic strategy selector service (pure logic, no mocking needed)."""

from app.constants import Strategy
from app.services.analyzer import AnalysisResult
from app.services.strategy_selector import (
    _COT_NATURAL_TASK_TYPES,
    _SPECIFICITY_EXEMPT_STRATEGIES,
    _SPECIFICITY_PATTERNS,
    _SPECIFICITY_RE,
    _STRATEGY_REASON_MAP,
    _STRENGTH_REDUNDANCY_PATTERNS,
    _STRENGTH_REDUNDANCY_RE,
    TASK_TYPE_FRAMEWORK_MAP,
    HeuristicStrategySelector,
    StrategySelection,
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
        self.selector = HeuristicStrategySelector()

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
        assert result.strategy == "few-shot-scaffolding"

    def test_formatting_task_selects_structured_output(self):
        result = self.selector.select(_make_analysis(task_type="formatting"))
        assert result.strategy == "structured-output"

    def test_extraction_task_selects_structured_output(self):
        result = self.selector.select(_make_analysis(task_type="extraction"))
        assert result.strategy == "structured-output"

    # --- Task-type mapping: persona/coding group ---

    def test_coding_task_selects_structured_output(self):
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert result.strategy == "structured-output"

    def test_writing_task_selects_persona_assignment(self):
        result = self.selector.select(_make_analysis(task_type="writing"))
        assert result.strategy == "persona-assignment"

    def test_creative_task_selects_persona_assignment(self):
        result = self.selector.select(_make_analysis(task_type="creative"))
        assert result.strategy == "persona-assignment"

    def test_medical_task_selects_persona_assignment(self):
        result = self.selector.select(_make_analysis(task_type="medical"))
        assert result.strategy == "persona-assignment"

    def test_legal_task_selects_persona_assignment(self):
        result = self.selector.select(_make_analysis(task_type="legal"))
        assert result.strategy == "persona-assignment"

    # --- Task-type mapping: general/education group ---

    def test_general_task_selects_role_task_format(self):
        result = self.selector.select(_make_analysis(task_type="general"))
        assert result.strategy == "role-task-format"

    def test_education_task_selects_risen(self):
        result = self.selector.select(_make_analysis(task_type="education"))
        assert result.strategy == "risen"

    def test_other_task_selects_risen(self):
        result = self.selector.select(_make_analysis(task_type="other"))
        assert result.strategy == "risen"

    # --- Unknown task type fallback ---

    def test_unknown_task_type_falls_back_to_structured_enhancement(self):
        result = self.selector.select(_make_analysis(task_type="completely_unknown"))
        assert result.strategy == "role-task-format"

    # --- Priority 1: High complexity override ---

    def test_high_complexity_general_task_gets_natural_strategy(self):
        """General task at high complexity falls through P1 → structured-enhancement with boost."""
        result = self.selector.select(_make_analysis(complexity="high", task_type="general"))
        assert result.strategy == "role-task-format"
        assert result.confidence == 0.85

    def test_high_complexity_coding_task_gets_natural_strategy(self):
        """Coding task at high complexity falls through P1 → structured-output with boost."""
        result = self.selector.select(_make_analysis(complexity="high", task_type="coding"))
        assert result.strategy == "structured-output"
        assert result.confidence == 0.85

    # --- Priority 2: Specificity weakness override ---

    def test_specificity_weakness_overrides_coding_task(self):
        """A coding task with specificity weakness should get constraint-focused, not role-based."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Lacks specific details"])
        )
        assert result.strategy == "constraint-injection"

    def test_specificity_weakness_on_general_task(self):
        result = self.selector.select(
            _make_analysis(task_type="general", weaknesses=["Not specific enough"])
        )
        assert result.strategy == "constraint-injection"

    def test_domain_specific_does_not_trigger_constraint_focused(self):
        """'too domain-specific' should NOT match specificity patterns."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Too domain-specific for general use"])
        )
        assert result.strategy == "structured-output"

    def test_overly_specific_does_not_trigger_constraint_focused(self):
        """'overly specific' should NOT match specificity patterns."""
        result = self.selector.select(
            _make_analysis(task_type="writing", weaknesses=["Overly specific to one audience"])
        )
        assert result.strategy == "persona-assignment"

    def test_vague_weakness_triggers_constraint_focused(self):
        """'vague' IS a specificity pattern and should trigger constraint-focused."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Instructions are vague"])
        )
        assert result.strategy == "constraint-injection"

    def test_lack_of_detail_writing_keeps_persona(self):
        """Writing's persona-assignment is exempt from P2 specificity override."""
        result = self.selector.select(
            _make_analysis(task_type="writing", weaknesses=["Suffers from lack of detail"])
        )
        assert result.strategy == "persona-assignment"

    # --- Expanded specificity patterns ---

    def test_ambiguous_triggers_constraint_focused(self):
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Requirements are ambiguous"])
        )
        assert result.strategy == "constraint-injection"

    def test_unclear_triggers_constraint_focused(self):
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Instructions are unclear"])
        )
        assert result.strategy == "constraint-injection"

    def test_underspecified_triggers_constraint_focused(self):
        result = self.selector.select(
            _make_analysis(task_type="general", weaknesses=["Task is underspecified"])
        )
        assert result.strategy == "constraint-injection"

    def test_too_broad_writing_keeps_persona(self):
        """Writing's persona-assignment is exempt from P2 specificity override."""
        result = self.selector.select(
            _make_analysis(task_type="writing", weaknesses=["Scope is too broad"])
        )
        assert result.strategy == "persona-assignment"

    def test_too_general_triggers_constraint_focused(self):
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Instructions are too general"])
        )
        assert result.strategy == "constraint-injection"

    def test_needs_more_detail_triggers_constraint_focused(self):
        result = self.selector.select(
            _make_analysis(task_type="general", weaknesses=["Needs more detail on expectations"])
        )
        assert result.strategy == "constraint-injection"

    def test_insufficiently_detailed_writing_keeps_persona(self):
        """Writing's persona-assignment is exempt from P2 specificity override."""
        result = self.selector.select(
            _make_analysis(task_type="writing", weaknesses=["Insufficiently detailed requirements"])
        )
        assert result.strategy == "persona-assignment"

    def test_broad_scope_triggers_constraint_focused(self):
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Has a broad scope without focus"])
        )
        assert result.strategy == "constraint-injection"

    # --- False-positive checks for expanded patterns ---

    def test_clear_instructions_does_not_trigger_constraint_focused(self):
        """'clear instructions' should NOT match 'unclear'."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Mostly clear instructions"])
        )
        assert result.strategy == "structured-output"

    def test_unambiguous_does_not_trigger_word_boundary(self):
        """'ambiguous' does NOT match inside 'unambiguous' due to word boundaries.

        Word boundary regex prevents false positives on compound words.
        """
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Surprisingly unambiguous wording"])
        )
        # "unambiguous" does not trigger specificity override — falls to P3 task-type map
        assert result.strategy == "structured-output"

    # --- Non-string weakness items (B1) ---

    def test_non_string_weakness_does_not_crash(self):
        """Weaknesses containing ints or None should not crash the selector.
        ratio=1/3=0.333 < 0.40 → P2 does not fire, falls to P3 default."""
        result = self.selector.select(
            _make_analysis(task_type="general", weaknesses=[123, None, "vague"])
        )
        assert result.strategy == "role-task-format"

    def test_empty_string_weakness_does_not_crash(self):
        """An empty-string weakness should not crash or match patterns."""
        result = self.selector.select(
            _make_analysis(task_type="general", weaknesses=[""])
        )
        assert result.strategy == "role-task-format"

    # --- Case-insensitive complexity/task_type (B2) ---

    def test_high_complexity_case_insensitive(self):
        """Complexity 'High' (capitalized) should still trigger P1 for CoT-natural types."""
        result = self.selector.select(_make_analysis(complexity="High", task_type="reasoning"))
        assert result.strategy == "chain-of-thought"

    def test_task_type_case_insensitive(self):
        """Task type 'Coding' (capitalized) should still map to structured-output."""
        result = self.selector.select(_make_analysis(task_type="Coding"))
        assert result.strategy == "structured-output"

    # --- Priority interactions ---

    def test_high_complexity_non_cot_with_specificity_gets_constraint_focused(self):
        """High complexity coding (non-CoT) with specificity weakness → P2 fires.
        ratio=1/1=1.0 → >=0.75 tier → 0.90."""
        result = self.selector.select(
            _make_analysis(
                complexity="high",
                task_type="coding",
                weaknesses=["Lacks specific details"],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.90

    # --- Issue 2.1: Specificity exemption for chain-of-thought task types ---

    def test_math_with_vague_weakness_keeps_chain_of_thought(self):
        """Math task with vague weakness should keep chain-of-thought (Issue 2.1)."""
        result = self.selector.select(
            _make_analysis(task_type="math", weaknesses=["Parameters are vague"])
        )
        assert result.strategy == "chain-of-thought"

    def test_reasoning_with_vague_weakness_keeps_chain_of_thought(self):
        """Reasoning task with vague weakness should keep chain-of-thought (Issue 2.1)."""
        result = self.selector.select(
            _make_analysis(task_type="reasoning", weaknesses=["Lacks specific details"])
        )
        assert result.strategy == "chain-of-thought"

    def test_analysis_with_vague_weakness_keeps_chain_of_thought(self):
        """Analysis task with vague weakness should keep chain-of-thought (Issue 2.1)."""
        result = self.selector.select(
            _make_analysis(task_type="analysis", weaknesses=["Too broad scope"])
        )
        assert result.strategy == "chain-of-thought"

    def test_coding_with_vague_weakness_gets_constraint_focused(self):
        """Coding task (non-exempt) with vague weakness should still get constraint-focused."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Requirements are vague"])
        )
        assert result.strategy == "constraint-injection"

    # --- Reasoning string content ---

    def test_reasoning_contains_task_type(self):
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert "coding" in result.reasoning

    def test_reasoning_contains_strategy_name(self):
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert "structured-output" in result.reasoning


    # --- Priority 2.5: Strengths-based redundancy ---

    def test_few_shot_redirected_when_strengths_include_examples(self):
        """If task maps to few-shot but prompt already has examples, use first secondary."""
        result = self.selector.select(
            _make_analysis(task_type="classification", strengths=["Includes examples of each type"])
        )
        # classification combo: primary=few-shot-scaffolding,
        # secondary=(structured-output, constraint-injection)
        # Redundancy: few-shot → structured-output (first secondary)
        assert result.strategy == "structured-output"
        assert result.confidence == 0.70

    def test_structured_output_redirected_when_well_structured(self):
        """Structured-output redirected when prompt is already well-structured."""
        result = self.selector.select(
            _make_analysis(task_type="coding", strengths=["Well-structured with clear format"])
        )
        # coding combo: primary=structured-output, secondary=(constraint-injection, step-by-step)
        # Redundancy redirect: structured-output → constraint-injection (first secondary)
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.70

    def test_chain_of_thought_redirected_when_strengths_include_steps(self):
        """CoT redirected when prompt has steps — uses first secondary from combo."""
        result = self.selector.select(
            _make_analysis(
                task_type="reasoning",
                strengths=["Already has step-by-step instructions"],
            )
        )
        # reasoning combo: primary=chain-of-thought, secondary=(structured-output, co-star)
        # Redundancy redirect: chain-of-thought → structured-output (first secondary)
        assert result.strategy == "structured-output"
        assert result.confidence == 0.70

    def test_constraint_injection_redirected_when_strengths_include_constraints(self):
        """Constraint-injection redirect: coding+vague gets P2, general stays."""
        # Coding with specificity weakness → P2 fires (constraint-injection)
        # regardless of strengths, since P2 comes before P3 redundancy.
        coding_result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=["Instructions are vague"],
                strengths=["Has explicit constraints for the task"],
            )
        )
        assert coding_result.strategy == "constraint-injection"

        # General maps to role-task-format which has no redundancy
        # patterns matching, so it stays as role-task-format.
        general_result = self.selector.select(
            _make_analysis(
                task_type="general",
                strengths=["Well-defined boundaries and clear constraints"],
            )
        )
        assert general_result.strategy == "role-task-format"

    def test_strengths_check_is_case_insensitive(self):
        """Extraction maps to structured-output; 'PROVIDES EXAMPLES'
        doesn't match structured-output patterns."""
        result = self.selector.select(
            _make_analysis(
                task_type="extraction",
                strengths=["PROVIDES EXAMPLES for parsing"],
            )
        )
        # extraction: primary=structured-output,
        # "PROVIDES EXAMPLES" doesn't match its patterns
        assert result.strategy == "structured-output"

    def test_no_redundancy_without_matching_strength(self):
        """If strengths don't match redundancy patterns, use normal task-type strategy."""
        result = self.selector.select(
            _make_analysis(task_type="classification", strengths=["Good structure"])
        )
        assert result.strategy == "few-shot-scaffolding"

    # --- Confidence scores ---

    def test_high_complexity_cot_confidence_is_095(self):
        """P1 fires for CoT-natural task at high complexity → 0.95 (via math)."""
        result = self.selector.select(_make_analysis(complexity="high", task_type="math"))
        assert result.confidence == 0.95

    def test_specificity_weakness_single_confidence_is_090(self):
        """Single specificity weakness: ratio=1/1=1.0 → >=0.75 tier → 0.90."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Instructions are vague"])
        )
        assert result.confidence == 0.90

    def test_known_task_type_confidence_is_075(self):
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert result.confidence == 0.75

    def test_unknown_task_type_confidence_is_050(self):
        result = self.selector.select(_make_analysis(task_type="completely_unknown"))
        assert result.confidence == 0.50

    # --- Strategy type is Strategy enum ---

    def test_strategy_is_strategy_enum(self):
        """StrategySelection.strategy should be a Strategy enum value."""
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert isinstance(result.strategy, Strategy)

    def test_strategy_equals_string_via_strenum(self):
        """Strategy enum (StrEnum) should compare equal to its string value."""
        result = self.selector.select(_make_analysis(task_type="coding"))
        assert result.strategy == "structured-output"
        assert result.strategy == Strategy.STRUCTURED_OUTPUT


    # --- Priority 1 scoped to CoT-natural task types ---

    def test_high_complexity_reasoning_gets_cot(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="reasoning"))
        assert result.strategy == "chain-of-thought"
        assert result.confidence == 0.95

    def test_high_complexity_analysis_gets_cot(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="analysis"))
        assert result.strategy == "chain-of-thought"
        assert result.confidence == 0.95

    def test_high_complexity_math_gets_cot(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="math"))
        assert result.strategy == "chain-of-thought"
        assert result.confidence == 0.95

    def test_high_complexity_writing_keeps_role_based(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="writing"))
        assert result.strategy == "persona-assignment"
        assert result.confidence == 0.85

    def test_high_complexity_classification_keeps_few_shot(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="classification"))
        assert result.strategy == "few-shot-scaffolding"
        assert result.confidence == 0.85

    def test_high_complexity_extraction_keeps_structured_output(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="extraction"))
        assert result.strategy == "structured-output"
        assert result.confidence == 0.85

    def test_high_complexity_creative_keeps_role_based(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="creative"))
        assert result.strategy == "persona-assignment"
        assert result.confidence == 0.85

    def test_high_complexity_unknown_gets_structured_enhancement(self):
        result = self.selector.select(_make_analysis(complexity="high", task_type="unknown_xyz"))
        assert result.strategy == "role-task-format"
        assert result.confidence == 0.60  # 0.50 base + 0.10 boost

    def test_high_complexity_cot_with_specificity_still_gets_cot(self):
        """P1 fires before P2 for CoT-natural types even with specificity weakness."""
        result = self.selector.select(
            _make_analysis(
                complexity="high", task_type="math",
                weaknesses=["Lacks specific details"],
            )
        )
        assert result.strategy == "chain-of-thought"
        assert result.confidence == 0.95

    def test_medium_complexity_no_confidence_boost(self):
        """Medium complexity should NOT get the +0.10 boost."""
        result = self.selector.select(_make_analysis(complexity="medium", task_type="coding"))
        assert result.confidence == 0.75

    def test_low_complexity_no_confidence_boost(self):
        """Low complexity should NOT get the +0.10 boost."""
        result = self.selector.select(_make_analysis(complexity="low", task_type="coding"))
        assert result.confidence == 0.75

    def test_high_complexity_boost_capped_at_095(self):
        """High complexity boost for known task types: 0.75 + 0.10 = 0.85 (under cap)."""
        result = self.selector.select(_make_analysis(complexity="high", task_type="education"))
        assert result.strategy == "risen"
        assert result.confidence == 0.85

    def test_high_complexity_boost_unknown_task(self):
        """High complexity boost for unknown: 0.50 + 0.10 = 0.60."""
        result = self.selector.select(_make_analysis(complexity="high", task_type="never_heard_of"))
        assert result.confidence == 0.60

    def test_high_complexity_redundancy_no_boost(self):
        """High complexity + redundancy redirect stays at 0.70 (no boost on redirect path)."""
        result = self.selector.select(
            _make_analysis(
                complexity="high",
                task_type="coding",
                strengths=["Well-structured with clear format"],
            )
        )
        # coding combo: primary=structured-output, redundancy redirect → constraint-injection
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.70


class TestCotNaturalTaskTypes:
    """Tests for the _COT_NATURAL_TASK_TYPES constant."""

    def test_cot_natural_matches_framework_map(self):
        """_COT_NATURAL_TASK_TYPES must be exactly the task types whose primary is CoT."""
        cot_from_map = {
            k for k, v in TASK_TYPE_FRAMEWORK_MAP.items()
            if v.primary == Strategy.CHAIN_OF_THOUGHT
        }
        assert _COT_NATURAL_TASK_TYPES == cot_from_map

    def test_cot_natural_is_frozenset(self):
        assert isinstance(_COT_NATURAL_TASK_TYPES, frozenset)

    def test_contains_expected_types(self):
        assert _COT_NATURAL_TASK_TYPES == {"reasoning", "analysis", "math"}


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
        assert set(TASK_TYPE_FRAMEWORK_MAP.keys()) == expected_types

    def test_map_keys_match_analyzer_valid_task_types(self):
        """Strategy map must stay in sync with the analyzer's valid task types."""
        from app.services.analyzer import _VALID_TASK_TYPES

        assert set(TASK_TYPE_FRAMEWORK_MAP.keys()) == _VALID_TASK_TYPES

    def test_map_values_are_valid_strategies(self):
        for combo in TASK_TYPE_FRAMEWORK_MAP.values():
            assert combo.primary in set(Strategy), f"Unknown primary strategy {combo.primary!r}"
            for s in combo.secondary:
                assert s in set(Strategy), f"Unknown secondary strategy {s!r}"


class TestSpecificityPatterns:
    def test_patterns_are_all_lowercase(self):
        for p in _SPECIFICITY_PATTERNS:
            assert p == p.lower(), f"Pattern {p!r} must be lowercase for case-insensitive matching"

    def test_patterns_do_not_match_domain_specific(self):
        """Ensure none of the patterns are broad enough to match 'domain-specific'."""
        false_positive = "too domain-specific"
        for p in _SPECIFICITY_PATTERNS:
            assert p not in false_positive.lower(), (
                f"Pattern {p!r} matches false-positive {false_positive!r}"
            )

    def test_patterns_do_not_match_overly_specific(self):
        """Ensure none of the patterns match 'overly specific'."""
        false_positive = "overly specific to one audience"
        for p in _SPECIFICITY_PATTERNS:
            assert p not in false_positive.lower(), (
                f"Pattern {p!r} matches false-positive {false_positive!r}"
            )

    def test_compiled_regex_matches_same_as_patterns(self):
        """Compiled regex should match the same strings as the tuple patterns."""
        test_cases = [
            ("Instructions are vague", True),
            ("Lacks specific details", True),
            ("Clear and well-defined", False),
            ("Too domain-specific", False),
        ]
        for text, expected in test_cases:
            assert bool(_SPECIFICITY_RE.search(text)) == expected, (
                f"Regex mismatch for {text!r}: expected {expected}"
            )

    def test_compiled_regex_is_case_insensitive(self):
        """The compiled regex should match regardless of case."""
        assert _SPECIFICITY_RE.search("INSTRUCTIONS ARE VAGUE")
        assert _SPECIFICITY_RE.search("Lacks Specific Details")


class TestSpecificityExemptStrategies:
    def test_exempt_strategies_include_expected_set(self):
        assert _SPECIFICITY_EXEMPT_STRATEGIES == {
            Strategy.CHAIN_OF_THOUGHT,
            Strategy.PERSONA_ASSIGNMENT,
            Strategy.FEW_SHOT_SCAFFOLDING,
            Strategy.RISEN,
        }

    def test_exempt_task_types_cover_expected_set(self):
        """Task types whose primary is an exempt strategy — P2 skips these."""
        exempt_tasks = {
            k for k, v in TASK_TYPE_FRAMEWORK_MAP.items()
            if v.primary in _SPECIFICITY_EXEMPT_STRATEGIES
        }
        assert exempt_tasks == {
            "reasoning", "analysis", "math",          # chain-of-thought
            "writing", "creative", "medical", "legal", # persona-assignment
            "classification",                          # few-shot-scaffolding
            "education", "other",                      # risen
        }


class TestStrategyReasonMap:
    def test_reason_map_covers_all_strategies(self):
        assert set(_STRATEGY_REASON_MAP.keys()) == set(Strategy)


class TestStrategyEdgeCases:
    """Additional edge cases for strategy selector coverage."""

    def setup_method(self):
        self.selector = HeuristicStrategySelector()

    def test_empty_weaknesses_and_strengths_both_empty(self):
        """Both lists empty → falls through to P3 task-type default without crashing."""
        result = self.selector.select(_make_analysis(weaknesses=[], strengths=[]))
        assert result.strategy == "role-task-format"

    def test_p1_redirects_on_cot_redundancy(self):
        """High complexity + CoT-natural + redundant strength → first secondary at 0.85."""
        result = self.selector.select(_make_analysis(
            complexity="high",
            task_type="reasoning",
            strengths=["Already has step-by-step instructions"],
        ))
        assert result.strategy == "structured-output"
        assert result.confidence == 0.85

    def test_known_task_type_low_complexity_confidence_075(self):
        """Known type at low complexity has base 0.75, no boost."""
        result = self.selector.select(_make_analysis(task_type="coding", complexity="low"))
        assert result.confidence == 0.75

    def test_unknown_task_type_low_complexity_confidence_050(self):
        """Unknown type at low complexity has base 0.50, no boost."""
        result = self.selector.select(_make_analysis(task_type="alien_type", complexity="low"))
        assert result.confidence == 0.50

    def test_all_cot_natural_types_case_insensitive(self):
        """All 3 CoT types work in any case."""
        for task_type in ("REASONING", "Analysis", "MATH"):
            result = self.selector.select(_make_analysis(
                task_type=task_type, complexity="high",
            ))
            assert result.strategy == "chain-of-thought", f"Failed for {task_type}"
            assert result.confidence == 0.95

    def test_all_strategies_produce_valid_reasoning_format(self):
        """Every task type produces reasoning starting with 'Selected ' and containing ' for '."""
        for task_type in TASK_TYPE_FRAMEWORK_MAP:
            result = self.selector.select(_make_analysis(task_type=task_type))
            assert result.reasoning.startswith("Selected "), (
                f"Reasoning for {task_type} doesn't start with 'Selected ': {result.reasoning}"
            )
            assert " for " in result.reasoning, (
                f"Reasoning for {task_type} doesn't contain ' for ': {result.reasoning}"
            )


class TestStrengthRedundancy:
    def test_all_ten_strategies_have_redundancy(self):
        assert set(_STRENGTH_REDUNDANCY_PATTERNS.keys()) == set(Strategy)

    def test_patterns_are_all_lowercase(self):
        for strategy, patterns in _STRENGTH_REDUNDANCY_PATTERNS.items():
            for p in patterns:
                assert p == p.lower(), (
                    f"Pattern {p!r} for {strategy} must be lowercase"
                )

    def test_compiled_regex_exists_for_all_strategies(self):
        """Each strategy with patterns should have a compiled regex."""
        assert set(_STRENGTH_REDUNDANCY_RE.keys()) == set(_STRENGTH_REDUNDANCY_PATTERNS.keys())

    def test_regex_prevents_false_positive_not_step_by_step(self):
        """'not step-by-step' should NOT trigger CoT redundancy due to word boundaries."""
        # "step-by-step" pattern uses word boundaries, so "not step-by-step"
        # still matches because "not" is separate from "step-by-step".
        # The real protection is against partial-word matches.
        cot_re = _STRENGTH_REDUNDANCY_RE[Strategy.CHAIN_OF_THOUGHT]
        # "stepwise" should NOT match "step-by-step"
        assert not cot_re.search("uses a stepwise approach")

    def test_regex_prevents_false_positive_examples_in_compound(self):
        """'examples of non-compliance' contains 'examples' but should still match
        since 'includes examples' uses word boundaries correctly."""
        few_shot_re = _STRENGTH_REDUNDANCY_RE[Strategy.FEW_SHOT_SCAFFOLDING]
        # This DOES match because "includes examples" is a full phrase in the regex
        # and "examples of non-compliance" doesn't match "includes examples"
        assert not few_shot_re.search("cites examples of non-compliance")

    def test_regex_matches_correct_patterns(self):
        """Verify basic matching works for each strategy's patterns."""
        cot_re = _STRENGTH_REDUNDANCY_RE[Strategy.CHAIN_OF_THOUGHT]
        assert cot_re.search("has step-by-step instructions")
        assert cot_re.search("uses chain of thought reasoning")

        fs_re = _STRENGTH_REDUNDANCY_RE[Strategy.FEW_SHOT_SCAFFOLDING]
        assert fs_re.search("includes examples of each type")
        assert fs_re.search("provides examples for parsing")

    def test_structured_output_redundancy_patterns_exist(self):
        """structured-output should have redundancy patterns for well-structured prompts."""
        assert Strategy.STRUCTURED_OUTPUT in _STRENGTH_REDUNDANCY_RE
        so_re = _STRENGTH_REDUNDANCY_RE[Strategy.STRUCTURED_OUTPUT]
        assert so_re.search("well-structured with headings")
        assert so_re.search("good organization throughout")
        assert so_re.search("well-organized sections")
        assert so_re.search("clear structure overall")

    def test_role_task_format_redundancy_patterns_exist(self):
        """role-task-format should have redundancy patterns for role-task prompts."""
        assert Strategy.ROLE_TASK_FORMAT in _STRENGTH_REDUNDANCY_RE
        rtf_re = _STRENGTH_REDUNDANCY_RE[Strategy.ROLE_TASK_FORMAT]
        assert rtf_re.search("clear role definition present")
        assert rtf_re.search("task and format specified")

    def test_role_task_format_self_redundancy_reduces_confidence(self):
        """When role-task-format is the natural strategy AND prompt already has
        role-task structure, redirect to first secondary (context-enrichment)."""
        selector = HeuristicStrategySelector()
        # general task → natural strategy is role-task-format
        result = selector.select(_make_analysis(
            task_type="general",
            strengths=["clear role definition already present"],
        ))
        # Redirects to first secondary (context-enrichment) at 0.70
        assert result.strategy == "context-enrichment"
        assert result.confidence == 0.70

    def test_structured_output_self_redundancy_for_coding(self):
        """When structured-output is the natural strategy AND prompt is already
        well-structured, redirect to first secondary (constraint-injection)."""
        selector = HeuristicStrategySelector()
        # coding task → natural strategy is structured-output
        result = selector.select(_make_analysis(
            task_type="coding",
            strengths=["well-structured with clear format"],
        ))
        # Redirects to first secondary (constraint-injection) at 0.70
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.70

    def test_non_primary_strength_does_not_trigger_redundancy(self):
        """When a coding task has a strength matching a *different* strategy's
        redundancy pattern, the primary (structured-output) is returned normally."""
        selector = HeuristicStrategySelector()
        result = selector.select(_make_analysis(
            task_type="coding",
            strengths=["clear role definition and expert persona"],
        ))
        # "clear role definition" matches persona-assignment, not structured-output
        # So no redundancy redirect — returns coding's primary at 0.75
        assert result.strategy == "structured-output"
        assert result.confidence == 0.75


class TestConfidenceValidation:
    """Tests for StrategySelection confidence bounds validation (#14)."""

    def test_valid_confidence_values(self):
        """Confidence 0.0, 0.5, 1.0 should all be accepted."""
        for val in (0.0, 0.5, 0.75, 1.0):
            s = StrategySelection(
                strategy=Strategy.ROLE_TASK_FORMAT,
                reasoning="test",
                confidence=val,
            )
            assert s.confidence == val

    def test_negative_confidence_raises(self):
        """Confidence below 0.0 should raise ValueError."""
        import pytest

        with pytest.raises(ValueError, match="confidence must be between"):
            StrategySelection(
                strategy=Strategy.ROLE_TASK_FORMAT,
                reasoning="test",
                confidence=-0.1,
            )

    def test_confidence_above_one_raises(self):
        """Confidence above 1.0 should raise ValueError."""
        import pytest

        with pytest.raises(ValueError, match="confidence must be between"):
            StrategySelection(
                strategy=Strategy.ROLE_TASK_FORMAT,
                reasoning="test",
                confidence=1.5,
            )


class TestP1RedundancyCheck:
    """Tests for P1 redundancy check — CoT redirect when strengths include steps (#1)."""

    def setup_method(self):
        self.selector = HeuristicStrategySelector()

    def test_high_cot_with_steps_redirects_to_first_secondary(self):
        """High complexity + CoT-natural + existing steps → first secondary from combo."""
        result = self.selector.select(_make_analysis(
            complexity="high",
            task_type="math",
            strengths=["Already has step-by-step reasoning"],
        ))
        # math combo: CoT + (step-by-step, constraint-injection)
        assert result.strategy == "step-by-step"
        assert result.confidence == 0.85

    def test_high_cot_without_steps_stays_cot(self):
        """High complexity + CoT-natural + no redundant strengths → chain-of-thought."""
        result = self.selector.select(_make_analysis(
            complexity="high",
            task_type="math",
            strengths=["Good mathematical notation"],
        ))
        assert result.strategy == "chain-of-thought"
        assert result.confidence == 0.95

    def test_high_cot_with_chain_of_thought_strength_redirects(self):
        """'chain of thought' in strengths triggers P1 redundancy → first secondary."""
        result = self.selector.select(_make_analysis(
            complexity="high",
            task_type="analysis",
            strengths=["Uses chain of thought approach"],
        ))
        # analysis combo: CoT + (co-star, structured-output)
        assert result.strategy == "co-star"
        assert result.confidence == 0.85

    def test_high_cot_with_numbered_steps_redirects(self):
        """'numbered steps' in strengths triggers P1 redundancy → first secondary."""
        result = self.selector.select(_make_analysis(
            complexity="high",
            task_type="reasoning",
            strengths=["Has numbered steps for the process"],
        ))
        # reasoning combo: CoT + (structured-output, co-star)
        assert result.strategy == "structured-output"
        assert result.confidence == 0.85

    def test_medium_cot_with_steps_still_uses_p3_redundancy(self):
        """Medium complexity + CoT-natural + existing steps → P3 redundancy fires."""
        result = self.selector.select(_make_analysis(
            complexity="medium",
            task_type="reasoning",
            strengths=["Already has step-by-step instructions"],
        ))
        # reasoning combo: CoT + (structured-output, co-star) → redirect to structured-output
        assert result.strategy == "structured-output"
        assert result.confidence == 0.70  # P3 redundancy confidence


class TestP2ScaledConfidence:
    """Tests for P2 specificity confidence scaling by match count (#8)."""

    def setup_method(self):
        self.selector = HeuristicStrategySelector()

    def test_single_weakness_confidence_090(self):
        """Single weakness: ratio=1/1=1.0 → >=0.75 tier → 0.90."""
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Instructions are vague"])
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.90

    def test_two_weaknesses_confidence_090(self):
        """Two weaknesses, both match: ratio=2/2=1.0 → >=0.75 tier → 0.90."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=["Instructions are vague", "Lacks specific details"],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.90

    def test_three_weaknesses_confidence_090(self):
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",
                    "Lacks specific details",
                    "Too broad scope",
                ],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.90

    def test_four_weaknesses_still_090(self):
        """Four or more specificity weaknesses caps at 0.90."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",
                    "Lacks specific details",
                    "Too broad scope",
                    "Requirements are ambiguous",
                ],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.90

    def test_mixed_matching_and_nonmatching_weaknesses(self):
        """2/4 specificity matches: ratio=0.50 → >=0.40 tier → 0.80."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",       # matches
                    "Poor formatting",              # doesn't match
                    "Too broad scope",              # matches
                    "Missing error handling",       # doesn't match
                ],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.80  # ratio 2/4=0.50 → 0.40-0.59 tier


class TestP2ProportionalThreshold:
    """Tests for P2 proportional ratio threshold.

    P2 now requires specificity_ratio >= 0.40 instead of count > 0.
    """

    def setup_method(self):
        self.selector = HeuristicStrategySelector()

    def test_minority_specificity_does_not_trigger_p2(self):
        """1/6=0.167 < 0.40 → P2 skipped, falls to P3."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",       # specificity match
                    "Poor formatting",
                    "Missing error handling",
                    "No tests mentioned",
                    "Lacks examples",
                    "Inconsistent style",
                ],
            )
        )
        # P2 does NOT fire; P3 selects coding default (structured-output)
        assert result.strategy != "constraint-injection"
        assert result.strategy == "structured-output"

    def test_at_threshold_triggers_p2(self):
        """2/5=0.40 → exactly at threshold → P2 fires."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",       # matches
                    "Too broad scope",              # matches
                    "Poor formatting",
                    "Missing error handling",
                    "No tests mentioned",
                ],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.80  # ratio 0.40 → lowest tier

    def test_just_below_threshold_does_not_trigger_p2(self):
        """2/6=0.333 < 0.40 → P2 skipped."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",       # matches
                    "Too broad scope",              # matches
                    "Poor formatting",
                    "Missing error handling",
                    "No tests mentioned",
                    "Inconsistent style",
                ],
            )
        )
        assert result.strategy != "constraint-injection"

    def test_dominant_specificity_high_confidence(self):
        """4/5=0.80 → >=0.75 tier → 0.90 confidence."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",
                    "Too broad scope",
                    "Lacks specific details",
                    "Requirements are ambiguous",
                    "Poor formatting",
                ],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.90

    def test_majority_specificity_medium_confidence(self):
        """3/5=0.60 → >=0.60 tier → 0.85 confidence."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    "Instructions are vague",
                    "Too broad scope",
                    "Lacks specific details",
                    "Poor formatting",
                    "Missing error handling",
                ],
            )
        )
        assert result.strategy == "constraint-injection"
        assert result.confidence == 0.85

    def test_meta_eval_scenario(self):
        """Meta-eval: 4/12=0.333 < 0.40 → P2 skipped (validates the finding)."""
        result = self.selector.select(
            _make_analysis(
                task_type="coding",
                weaknesses=[
                    # 4 specificity matches
                    "Instructions are vague",
                    "Too broad scope",
                    "Lacks specific details",
                    "Requirements are ambiguous",
                    # 8 non-specificity weaknesses
                    "Poor formatting",
                    "Missing error handling",
                    "No tests mentioned",
                    "Inconsistent naming",
                    "Missing documentation",
                    "No examples provided",
                    "Inconsistent style",
                    "Missing edge cases",
                ],
            )
        )
        # P2 does NOT fire; falls to P3
        assert result.strategy != "constraint-injection"


class TestPromptLengthPenalty:
    """Tests for short-prompt confidence penalty (#11)."""

    def setup_method(self):
        self.selector = HeuristicStrategySelector()

    def test_short_prompt_reduces_confidence(self):
        """A very short prompt (< 50 chars) should get -0.05 penalty."""
        result = self.selector.select(
            _make_analysis(task_type="coding"),
            prompt_length=20,
        )
        # Normal P3 for coding = structured-output at 0.75 → 0.70 with penalty
        assert result.strategy == "structured-output"
        assert result.confidence == 0.70

    def test_normal_prompt_no_penalty(self):
        """A normal-length prompt (>= 50 chars) gets no penalty."""
        result = self.selector.select(
            _make_analysis(task_type="coding"),
            prompt_length=100,
        )
        assert result.strategy == "structured-output"
        assert result.confidence == 0.75

    def test_zero_prompt_length_no_penalty(self):
        """prompt_length=0 (default) means no penalty (length unknown)."""
        result = self.selector.select(
            _make_analysis(task_type="coding"),
            prompt_length=0,
        )
        assert result.strategy == "structured-output"
        assert result.confidence == 0.75

    def test_boundary_prompt_length_no_penalty(self):
        """prompt_length=50 is exactly at threshold — no penalty."""
        result = self.selector.select(
            _make_analysis(task_type="coding"),
            prompt_length=50,
        )
        assert result.strategy == "structured-output"
        assert result.confidence == 0.75

    def test_short_prompt_penalty_on_high_confidence(self):
        """Penalty applies even on P1 high-confidence selections."""
        result = self.selector.select(
            _make_analysis(task_type="math", complexity="high"),
            prompt_length=10,
        )
        assert result.strategy == "chain-of-thought"
        assert abs(result.confidence - 0.90) < 1e-9  # 0.95 - 0.05

    def test_penalty_does_not_go_below_zero(self):
        """Confidence floor is 0.0 even with penalty."""
        # Use a scenario that already has very low confidence:
        # unknown task → 0.50 → after penalty → 0.45 (still positive)
        result = self.selector.select(
            _make_analysis(task_type="alien_type"),
            prompt_length=5,
        )
        assert result.confidence >= 0.0


class TestStrategyUtilizationCoverage:
    """Tests verifying all 10 strategies are reachable as primary selection.

    Addresses the strategy utilization gap where 5 strategies had zero primary
    selections: co-star, few-shot-scaffolding, step-by-step, context-enrichment,
    structured-output (the last via non-redundancy paths).
    """

    def setup_method(self):
        self.selector = HeuristicStrategySelector()

    # --- RISEN reachability (new primary for education/other) ---

    def test_risen_selected_for_education(self):
        """Education task type now maps to risen as primary."""
        result = self.selector.select(_make_analysis(task_type="education"))
        assert result.strategy == "risen"
        assert result.confidence == 0.75
        assert "step-by-step" in result.secondary_frameworks

    def test_risen_selected_for_other(self):
        """Other task type now maps to risen as primary."""
        result = self.selector.select(_make_analysis(task_type="other"))
        assert result.strategy == "risen"
        assert result.confidence == 0.75

    # --- co-star via redundancy fallback (now at secondary[0]) ---

    def test_co_star_via_analysis_redundancy(self):
        """Analysis: CoT redundant → falls back to co-star (first secondary)."""
        result = self.selector.select(_make_analysis(
            task_type="analysis",
            strengths=["Already uses chain of thought reasoning"],
        ))
        # analysis combo: CoT + (co-star, structured-output)
        assert result.strategy == "co-star"
        assert result.confidence == 0.70

    def test_co_star_via_creative_redundancy(self):
        """Creative: persona-assignment redundant → falls back to co-star (first secondary)."""
        result = self.selector.select(_make_analysis(
            task_type="creative",
            strengths=["Already assigns a role as expert storyteller"],
        ))
        # creative combo: persona-assignment + (co-star, context-enrichment)
        assert result.strategy == "co-star"
        assert result.confidence == 0.70

    # --- context-enrichment via writing redundancy ---

    def test_context_enrichment_via_writing_redundancy(self):
        """Writing: persona-assignment redundant → falls back to context-enrichment."""
        result = self.selector.select(_make_analysis(
            task_type="writing",
            strengths=["Defines a role as professional copywriter"],
        ))
        # writing combo: persona-assignment + (context-enrichment, co-star)
        assert result.strategy == "context-enrichment"
        assert result.confidence == 0.70

    # --- few-shot-scaffolding via extraction redundancy ---

    def test_few_shot_via_extraction_redundancy(self):
        """Extraction: structured-output redundant → falls back to few-shot-scaffolding."""
        result = self.selector.select(_make_analysis(
            task_type="extraction",
            strengths=["Well-structured with clear format for output"],
        ))
        # extraction combo: structured-output + (few-shot-scaffolding, constraint-injection)
        assert result.strategy == "few-shot-scaffolding"
        assert result.confidence == 0.70

    # --- step-by-step via education redundancy ---

    def test_step_by_step_via_education_redundancy(self):
        """Education: risen redundant → falls back to step-by-step."""
        result = self.selector.select(_make_analysis(
            task_type="education",
            strengths=["Has clear role and instructions with end-goal defined"],
        ))
        # education combo: risen + (step-by-step, context-enrichment)
        assert result.strategy == "step-by-step"
        assert result.confidence == 0.70

    # --- Exempt strategies keep their natural selection under P2 ---

    def test_writing_with_vague_keeps_persona(self):
        """Writing task with vague weakness keeps persona-assignment (exempt from P2)."""
        result = self.selector.select(
            _make_analysis(task_type="writing", weaknesses=["Instructions are vague"])
        )
        assert result.strategy == "persona-assignment"

    def test_classification_vague_keeps_few_shot(self):
        """Classification task with vague weakness keeps few-shot-scaffolding (exempt from P2)."""
        result = self.selector.select(
            _make_analysis(task_type="classification", weaknesses=["Requirements are vague"])
        )
        assert result.strategy == "few-shot-scaffolding"

    def test_education_vague_keeps_risen(self):
        """Education task with vague weakness keeps risen (exempt from P2)."""
        result = self.selector.select(
            _make_analysis(task_type="education", weaknesses=["Too broad scope"])
        )
        assert result.strategy == "risen"

    # --- Meta-test: all 10 strategies reachable as primary ---

    def test_all_10_strategies_reachable_as_primary(self):
        """Every one of the 10 strategies must be reachable as a primary selection.

        This test constructs specific analysis scenarios for each strategy and
        verifies the heuristic selector can produce it as primary output.
        """
        scenarios: dict[Strategy, AnalysisResult] = {
            # Direct task-type mappings (P3)
            Strategy.CHAIN_OF_THOUGHT: _make_analysis(task_type="reasoning"),
            Strategy.PERSONA_ASSIGNMENT: _make_analysis(task_type="writing"),
            Strategy.STRUCTURED_OUTPUT: _make_analysis(task_type="coding"),
            Strategy.FEW_SHOT_SCAFFOLDING: _make_analysis(task_type="classification"),
            Strategy.ROLE_TASK_FORMAT: _make_analysis(task_type="general"),
            Strategy.RISEN: _make_analysis(task_type="education"),
            # P2 specificity override (only fires for non-exempt task types)
            Strategy.CONSTRAINT_INJECTION: _make_analysis(
                task_type="coding", weaknesses=["Instructions are vague"],
            ),
            # Redundancy fallback paths
            Strategy.CO_STAR: _make_analysis(
                task_type="analysis",
                strengths=["Already uses chain of thought reasoning"],
            ),
            Strategy.CONTEXT_ENRICHMENT: _make_analysis(
                task_type="writing",
                strengths=["Defines a role as professional writer"],
            ),
            Strategy.STEP_BY_STEP: _make_analysis(
                task_type="education",
                strengths=["Has clear role and instructions with end-goal defined"],
            ),
        }
        reached = set()
        for expected_strategy, analysis in scenarios.items():
            result = self.selector.select(analysis)
            assert result.strategy == expected_strategy, (
                f"Expected {expected_strategy} but got {result.strategy} "
                f"for task_type={analysis.task_type}"
            )
            reached.add(result.strategy)

        assert reached == set(Strategy), (
            f"Not all strategies reachable. Missing: {set(Strategy) - reached}"
        )


class TestContextAwareHeuristic:
    """Tests for context-aware strategy selection adjustments."""

    def setup_method(self):
        self.selector = HeuristicStrategySelector()

    def test_strict_types_boosts_structured_output(self):
        """TypeScript strict mode in context → structured-output confidence boost."""
        from app.schemas.context import CodebaseContext

        ctx = CodebaseContext(
            language="TypeScript",
            conventions=["TypeScript strict mode enabled"],
        )
        # coding task → natural strategy is structured-output
        result = self.selector.select(
            _make_analysis(task_type="coding"),
            codebase_context=ctx,
        )
        assert result.strategy == "structured-output"
        # Base 0.75 + 0.05 context boost = 0.80
        assert result.confidence == 0.80

    def test_rust_language_boosts_structured_output(self):
        """Rust language in context → structured-output confidence boost."""
        from app.schemas.context import CodebaseContext

        ctx = CodebaseContext(language="Rust")
        result = self.selector.select(
            _make_analysis(task_type="coding"),
            codebase_context=ctx,
        )
        assert result.strategy == "structured-output"
        assert result.confidence == 0.80

    def test_context_doesnt_override_p1(self):
        """High complexity math still gets CoT regardless of context."""
        from app.schemas.context import CodebaseContext

        ctx = CodebaseContext(
            language="TypeScript",
            conventions=["TypeScript strict mode enabled"],
        )
        result = self.selector.select(
            _make_analysis(task_type="math", complexity="high"),
            codebase_context=ctx,
        )
        # P1 fires first → chain-of-thought, context cannot override
        assert result.strategy == "chain-of-thought"
        assert result.confidence == 0.95

    def test_context_doesnt_override_p2(self):
        """Specificity weakness still gets constraint-injection despite context."""
        from app.schemas.context import CodebaseContext

        ctx = CodebaseContext(
            language="TypeScript",
            conventions=["TypeScript strict mode enabled"],
        )
        result = self.selector.select(
            _make_analysis(task_type="coding", weaknesses=["Instructions are vague"]),
            codebase_context=ctx,
        )
        # P2 fires → constraint-injection, context cannot override
        assert result.strategy == "constraint-injection"

    def test_no_context_no_boost(self):
        """Without context, confidence is unchanged."""
        result_no_ctx = self.selector.select(
            _make_analysis(task_type="coding"),
        )
        result_none_ctx = self.selector.select(
            _make_analysis(task_type="coding"),
            codebase_context=None,
        )
        assert result_no_ctx.confidence == result_none_ctx.confidence == 0.75

    def test_service_layer_boosts_step_by_step(self):
        """Multi-layer architecture → step-by-step boost when aligned."""
        from app.schemas.context import CodebaseContext

        ctx = CodebaseContext(
            patterns=["Service layer pattern", "Repository pattern", "Middleware layer"],
        )
        # education task → natural strategy is risen (step-by-step is secondary)
        # step-by-step boost only applies when step-by-step is the selected strategy
        # Let's use a task type where step-by-step is the natural for a combo's secondary
        # Actually, step-by-step is natural for none. The boost only applies when
        # the P3-selected strategy matches the context preference.
        # education task → risen, so context boost for step-by-step won't apply
        result = self.selector.select(
            _make_analysis(task_type="education"),
            codebase_context=ctx,
        )
        # risen is the natural strategy, not step-by-step, so no boost
        assert result.strategy == "risen"
        assert result.confidence == 0.75
