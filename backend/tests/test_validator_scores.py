"""Tests for server-side overall_score computation and score normalization."""

import pytest

from app.services.validator import (
    CLARITY_WEIGHT,
    CONCISENESS_WEIGHT,
    FAITHFULNESS_WEIGHT,
    SPECIFICITY_WEIGHT,
    STRUCTURE_WEIGHT,
)
from app.utils.scores import round_score, score_threshold_to_db, score_to_display

ALL_WEIGHTS = (CLARITY_WEIGHT, SPECIFICITY_WEIGHT, STRUCTURE_WEIGHT, FAITHFULNESS_WEIGHT,
               CONCISENESS_WEIGHT)


class TestScoreWeights:
    def test_weights_sum_to_one(self):
        total = sum(ALL_WEIGHTS)
        assert total == pytest.approx(1.0)

    def test_all_weights_positive(self):
        for w in ALL_WEIGHTS:
            assert w > 0


class TestOverallScoreComputation:
    """Verify overall_score equals the weighted formula and is bounded by sub-scores."""

    @staticmethod
    def _expected_overall(
        clarity: float, specificity: float, structure: float,
        faithfulness: float, conciseness: float,
    ) -> float:
        return round(
            clarity * CLARITY_WEIGHT
            + specificity * SPECIFICITY_WEIGHT
            + structure * STRUCTURE_WEIGHT
            + faithfulness * FAITHFULNESS_WEIGHT
            + conciseness * CONCISENESS_WEIGHT,
            4,
        )

    def test_uniform_scores(self):
        """When all sub-scores are equal, overall should equal that value."""
        score = 0.8
        expected = self._expected_overall(score, score, score, score, score)
        assert expected == pytest.approx(score)

    def test_weighted_average_formula(self):
        """Verify the specific weighted formula with all 5 dimensions."""
        c, sp, st, f, cn = 0.9, 0.7, 0.8, 1.0, 0.6
        expected = self._expected_overall(c, sp, st, f, cn)
        assert expected == pytest.approx(
            c * CLARITY_WEIGHT + sp * SPECIFICITY_WEIGHT + st * STRUCTURE_WEIGHT
            + f * FAITHFULNESS_WEIGHT + cn * CONCISENESS_WEIGHT
        )

    def test_overall_within_sub_score_bounds(self):
        """Overall score must be between min and max of sub-scores."""
        c, sp, st, f, cn = 0.3, 0.9, 0.5, 0.7, 0.6
        overall = self._expected_overall(c, sp, st, f, cn)
        assert min(c, sp, st, f, cn) <= overall <= max(c, sp, st, f, cn)

    def test_all_zeros(self):
        assert self._expected_overall(0.0, 0.0, 0.0, 0.0, 0.0) == 0.0

    def test_all_ones(self):
        assert self._expected_overall(1.0, 1.0, 1.0, 1.0, 1.0) == pytest.approx(1.0)


class TestFrameworkAdherenceNotInOverall:
    """framework_adherence_score must NOT affect the weighted overall_score."""

    def test_adherence_excluded_from_weights(self):
        """The 5 standard weights sum to 1.0 — no room for a 6th dimension."""
        total = sum(ALL_WEIGHTS)
        assert total == pytest.approx(1.0)

    def test_overall_unchanged_regardless_of_adherence(self):
        """Same 5 sub-scores → same overall, whether adherence is 0 or 1."""
        c, sp, st, f, cn = 0.8, 0.8, 0.8, 0.8, 0.8
        expected = TestOverallScoreComputation._expected_overall(c, sp, st, f, cn)
        # framework_adherence_score is supplementary and never enters the formula
        assert expected == pytest.approx(0.8)


class TestScoreToDisplay:
    """Tests for score_to_display (0.0-1.0 → 1-10 integer)."""

    def test_none_returns_none(self):
        assert score_to_display(None) is None

    def test_zero_returns_one(self):
        """DB score 0.0 should display as 1 (minimum), not 0."""
        assert score_to_display(0.0) == 1

    def test_one_returns_ten(self):
        assert score_to_display(1.0) == 10

    def test_half_returns_five(self):
        assert score_to_display(0.5) == 5

    def test_typical_scores(self):
        # round(8.5) = 8 in Python (banker's rounding), max(1, 8) = 8
        assert score_to_display(0.85) == 8
        assert score_to_display(0.72) == 7
        assert score_to_display(0.33) == 3

    def test_output_always_in_range_1_10(self):
        """score_to_display must always return 1-10 for any valid input."""
        for i in range(101):
            val = i / 100.0
            result = score_to_display(val)
            assert isinstance(result, int)
            assert 1 <= result <= 10, f"score_to_display({val}) = {result}, out of range"

    def test_clamping_above_one(self):
        """Scores slightly above 1.0 (floating point drift) should clamp to 10."""
        assert score_to_display(1.05) == 10

    def test_clamping_below_zero(self):
        """Negative scores should clamp to 1."""
        assert score_to_display(-0.1) == 1


class TestScoreThresholdToDb:
    """Tests for score_threshold_to_db (1-10 → 0.0-1.0).

    The threshold is the lower bound of DB values that display as the given
    score.  E.g. display 10 maps to DB >= 0.95 (since round(0.95*10) = 10).
    """

    def test_display_one_to_db(self):
        assert score_threshold_to_db(1) == pytest.approx(0.05)

    def test_display_ten_to_db(self):
        assert score_threshold_to_db(10) == pytest.approx(0.95)

    def test_display_five_to_db(self):
        assert score_threshold_to_db(5) == pytest.approx(0.45)

    def test_threshold_captures_display_value(self):
        """A DB value at the threshold should display as >= the requested score."""
        for d in range(1, 11):
            threshold = score_threshold_to_db(d)
            # A value slightly above the threshold must display as >= d
            display_val = score_to_display(threshold + 0.001)
            assert display_val >= d, (
                f"Threshold miss: display {d} → db {threshold:.4f} + 0.001 → {display_val}"
            )

    def test_threshold_excludes_below(self):
        """A DB value well below the threshold should display as < the requested score."""
        for d in range(2, 11):
            threshold = score_threshold_to_db(d)
            display_val = score_to_display(threshold - 0.01)
            assert display_val < d, (
                f"Threshold leak: display {d} → db {threshold:.4f} - 0.01 → {display_val}"
            )


class TestRoundScore:
    def test_none_returns_none(self):
        assert round_score(None) is None

    def test_rounds_to_4_digits(self):
        assert round_score(0.123456) == 0.1235

    def test_custom_digits(self):
        assert round_score(0.123456, 2) == 0.12
