"""Tests for Pydantic v2 validation schemas — OptimizeRequest validators."""

import pytest
from pydantic import ValidationError

from app.constants import Strategy
from app.schemas.optimization import OptimizeRequest

# ---------------------------------------------------------------------------
# TestPromptValidation
# ---------------------------------------------------------------------------

class TestPromptValidation:
    def test_valid_prompt(self):
        req = OptimizeRequest(prompt="Write a poem")
        assert req.prompt == "Write a poem"

    def test_blank_prompt_rejected(self):
        with pytest.raises(ValidationError, match="empty or whitespace"):
            OptimizeRequest(prompt="   ")

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(prompt="")

    def test_newlines_only_rejected(self):
        with pytest.raises(ValidationError, match="empty or whitespace"):
            OptimizeRequest(prompt="\n\n\t  ")


# ---------------------------------------------------------------------------
# TestStrategyValidation
# ---------------------------------------------------------------------------

class TestStrategyValidation:
    def test_valid_strategy(self):
        req = OptimizeRequest(prompt="test", strategy="chain-of-thought")
        assert req.strategy == "chain-of-thought"

    def test_none_strategy_allowed(self):
        req = OptimizeRequest(prompt="test", strategy=None)
        assert req.strategy is None

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValidationError, match="Unknown strategy"):
            OptimizeRequest(prompt="test", strategy="invalid-strategy")

    @pytest.mark.parametrize("strategy", [s.value for s in Strategy])
    def test_all_known_strategies_accepted(self, strategy):
        req = OptimizeRequest(prompt="test", strategy=strategy)
        assert req.strategy == strategy


# ---------------------------------------------------------------------------
# TestTagValidation
# ---------------------------------------------------------------------------

class TestTagValidation:
    def test_valid_tags(self):
        req = OptimizeRequest(prompt="test", tags=["tag1", "tag2"])
        assert req.tags == ["tag1", "tag2"]

    def test_none_tags_allowed(self):
        req = OptimizeRequest(prompt="test", tags=None)
        assert req.tags is None

    def test_tag_too_long_raises(self):
        with pytest.raises(ValidationError, match="50 characters"):
            OptimizeRequest(prompt="test", tags=["x" * 51])

    def test_tag_exactly_50_allowed(self):
        req = OptimizeRequest(prompt="test", tags=["x" * 50])
        assert len(req.tags[0]) == 50

    def test_empty_tags_list_allowed(self):
        req = OptimizeRequest(prompt="test", tags=[])
        assert req.tags == []
