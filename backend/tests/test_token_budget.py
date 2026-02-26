"""Tests for the Token Budget Manager."""

import time
from unittest.mock import patch

import pytest

from app.providers.types import TokenUsage
from app.services.token_budget import TokenBudgetManager


@pytest.fixture
def manager():
    return TokenBudgetManager()


class TestRecordUsage:
    def test_records_input_and_output_tokens(self, manager):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        manager.record_usage("claude", usage)

        budget = manager.get_budget("claude")
        assert budget.input_tokens_used == 100
        assert budget.output_tokens_used == 50
        assert budget.total_tokens_used == 150
        assert budget.request_count == 1

    def test_accumulates_across_calls(self, manager):
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=50))
        manager.record_usage("claude", TokenUsage(input_tokens=200, output_tokens=100))

        budget = manager.get_budget("claude")
        assert budget.input_tokens_used == 300
        assert budget.output_tokens_used == 150
        assert budget.request_count == 2

    def test_handles_none_token_values(self, manager):
        usage = TokenUsage(input_tokens=None, output_tokens=None)
        manager.record_usage("claude", usage)

        budget = manager.get_budget("claude")
        assert budget.total_tokens_used == 0

    def test_tracks_per_provider(self, manager):
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=50))
        manager.record_usage("openai", TokenUsage(input_tokens=200, output_tokens=100))

        assert manager.get_budget("claude").total_tokens_used == 150
        assert manager.get_budget("openai").total_tokens_used == 300


class TestDailyLimit:
    def test_unlimited_by_default(self, manager):
        budget = manager.get_budget("claude")
        assert budget.daily_limit is None
        assert budget.remaining is None

    def test_set_daily_limit(self, manager):
        manager.set_daily_limit("claude", 1000)
        budget = manager.get_budget("claude")
        assert budget.daily_limit == 1000
        assert budget.remaining == 1000

    def test_remaining_decreases_with_usage(self, manager):
        manager.set_daily_limit("claude", 1000)
        manager.record_usage("claude", TokenUsage(input_tokens=300, output_tokens=200))

        budget = manager.get_budget("claude")
        assert budget.remaining == 500

    def test_remaining_floors_at_zero(self, manager):
        manager.set_daily_limit("claude", 100)
        manager.record_usage("claude", TokenUsage(input_tokens=500, output_tokens=500))

        budget = manager.get_budget("claude")
        assert budget.remaining == 0

    def test_clear_daily_limit(self, manager):
        manager.set_daily_limit("claude", 1000)
        manager.set_daily_limit("claude", None)

        budget = manager.get_budget("claude")
        assert budget.daily_limit is None
        assert budget.remaining is None


class TestCheckAvailable:
    def test_unlimited_always_available(self, manager):
        assert manager.check_available("claude", 1_000_000) is True

    def test_available_within_budget(self, manager):
        manager.set_daily_limit("claude", 1000)
        manager.record_usage("claude", TokenUsage(input_tokens=400, output_tokens=0))
        assert manager.check_available("claude", 500) is True

    def test_unavailable_exceeds_budget(self, manager):
        manager.set_daily_limit("claude", 1000)
        manager.record_usage("claude", TokenUsage(input_tokens=900, output_tokens=0))
        assert manager.check_available("claude", 200) is False

    def test_available_with_zero_estimate(self, manager):
        manager.set_daily_limit("claude", 1000)
        manager.record_usage("claude", TokenUsage(input_tokens=999, output_tokens=0))
        assert manager.check_available("claude") is True


class TestReset:
    def test_reset_single_provider(self, manager):
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=50))
        manager.record_usage("openai", TokenUsage(input_tokens=200, output_tokens=100))

        manager.reset("claude")

        assert manager.get_budget("claude").total_tokens_used == 0
        assert manager.get_budget("openai").total_tokens_used == 300

    def test_reset_all_providers(self, manager):
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=50))
        manager.record_usage("openai", TokenUsage(input_tokens=200, output_tokens=100))

        manager.reset()

        assert manager.get_budget("claude").total_tokens_used == 0
        assert manager.get_budget("openai").total_tokens_used == 0

    def test_reset_preserves_daily_limit(self, manager):
        manager.set_daily_limit("claude", 5000)
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=50))
        manager.reset("claude")

        budget = manager.get_budget("claude")
        assert budget.daily_limit == 5000
        assert budget.total_tokens_used == 0


class TestAutoReset:
    def test_auto_resets_after_24h(self, manager):
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=50))
        assert manager.get_budget("claude").total_tokens_used == 150

        # Simulate 25 hours passing
        with patch("app.services.token_budget.time") as mock_time:
            mock_time.time.return_value = time.time() + 90_000
            budget = manager.get_budget("claude")
            assert budget.total_tokens_used == 0


class TestSerialization:
    def test_to_dict(self, manager):
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=50))
        manager.set_daily_limit("claude", 5000)

        result = manager.to_dict()
        assert "claude" in result
        assert result["claude"]["input_tokens_used"] == 100
        assert result["claude"]["output_tokens_used"] == 50
        assert result["claude"]["total_tokens_used"] == 150
        assert result["claude"]["daily_limit"] == 5000
        assert result["claude"]["remaining"] == 4850

    def test_get_all_budgets(self, manager):
        manager.record_usage("claude", TokenUsage(input_tokens=100, output_tokens=0))
        manager.record_usage("openai", TokenUsage(input_tokens=200, output_tokens=0))

        all_budgets = manager.get_all_budgets()
        assert len(all_budgets) == 2
        assert "claude" in all_budgets
        assert "openai" in all_budgets
