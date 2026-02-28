"""Token Budget Manager — per-provider token tracking with configurable limits.

Layer 0 (HAL) in the PromptForge OS stack.
Tracks token usage per provider and enforces optional daily budgets.
"""

import time
from dataclasses import dataclass, field

from app.providers.types import TokenUsage


@dataclass
class BudgetStatus:
    """Current budget state for a single provider."""

    provider: str
    input_tokens_used: int = 0
    output_tokens_used: int = 0
    total_tokens_used: int = 0
    request_count: int = 0
    daily_limit: int | None = None  # None = unlimited
    remaining: int | None = None
    last_reset: float = 0.0
    last_usage_at: float = 0.0


@dataclass
class _ProviderBucket:
    """Internal tracking bucket for a provider."""

    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    daily_limit: int | None = None
    last_reset: float = field(default_factory=time.time)
    last_usage_at: float = 0.0


# Seconds in a day
_DAY_SECONDS = 86400


class TokenBudgetManager:
    """Per-provider token usage tracking with optional daily limits."""

    def __init__(self) -> None:
        self._buckets: dict[str, _ProviderBucket] = {}

    def record_usage(self, provider: str, usage: TokenUsage) -> None:
        """Record token usage for a provider."""
        bucket = self._get_or_create(provider)
        self._maybe_reset(bucket)
        bucket.input_tokens += usage.input_tokens or 0
        bucket.output_tokens += usage.output_tokens or 0
        bucket.request_count += 1
        bucket.last_usage_at = time.time()

    def get_budget(self, provider: str) -> BudgetStatus:
        """Get current budget status for a provider."""
        bucket = self._get_or_create(provider)
        self._maybe_reset(bucket)
        total = bucket.input_tokens + bucket.output_tokens
        remaining = None
        if bucket.daily_limit is not None:
            remaining = max(0, bucket.daily_limit - total)
        return BudgetStatus(
            provider=provider,
            input_tokens_used=bucket.input_tokens,
            output_tokens_used=bucket.output_tokens,
            total_tokens_used=total,
            request_count=bucket.request_count,
            daily_limit=bucket.daily_limit,
            remaining=remaining,
            last_reset=bucket.last_reset,
            last_usage_at=bucket.last_usage_at,
        )

    def set_daily_limit(self, provider: str, limit: int | None) -> None:
        """Set or clear a daily token limit for a provider."""
        bucket = self._get_or_create(provider)
        bucket.daily_limit = limit

    def check_available(self, provider: str, estimated_tokens: int = 0) -> bool:
        """Check if a provider has budget available for an estimated token count."""
        bucket = self._get_or_create(provider)
        self._maybe_reset(bucket)
        if bucket.daily_limit is None:
            return True
        total = bucket.input_tokens + bucket.output_tokens
        return (total + estimated_tokens) <= bucket.daily_limit

    def reset(self, provider: str | None = None) -> None:
        """Reset usage counters. If provider is None, reset all."""
        if provider:
            if provider in self._buckets:
                limit = self._buckets[provider].daily_limit
                self._buckets[provider] = _ProviderBucket(daily_limit=limit)
        else:
            for name in list(self._buckets):
                limit = self._buckets[name].daily_limit
                self._buckets[name] = _ProviderBucket(daily_limit=limit)

    def get_all_budgets(self) -> dict[str, BudgetStatus]:
        """Get budget status for all tracked providers."""
        return {name: self.get_budget(name) for name in self._buckets}

    def to_dict(self) -> dict:
        """Serialize budget state for API responses."""
        result = {}
        for name, status in self.get_all_budgets().items():
            result[name] = {
                "input_tokens_used": status.input_tokens_used,
                "output_tokens_used": status.output_tokens_used,
                "total_tokens_used": status.total_tokens_used,
                "request_count": status.request_count,
                "daily_limit": status.daily_limit,
                "remaining": status.remaining,
            }
        return result

    def _get_or_create(self, provider: str) -> _ProviderBucket:
        if provider not in self._buckets:
            self._buckets[provider] = _ProviderBucket()
        return self._buckets[provider]

    def _maybe_reset(self, bucket: _ProviderBucket) -> None:
        """Auto-reset if a day has passed since last reset."""
        now = time.time()
        if now - bucket.last_reset >= _DAY_SECONDS:
            limit = bucket.daily_limit
            bucket.input_tokens = 0
            bucket.output_tokens = 0
            bucket.request_count = 0
            bucket.last_reset = now
            bucket.daily_limit = limit


# Singleton instance
token_budget = TokenBudgetManager()
