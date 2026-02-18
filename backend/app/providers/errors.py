"""Typed error hierarchy for LLM provider failures.

Every error carries the originating *provider* name and an optional
*original* exception so callers can inspect or re-raise as needed.
``ProviderUnavailableError`` also inherits ``RuntimeError`` for backward
compatibility with existing ``except RuntimeError`` handlers.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all provider-related errors."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.original = original


class AuthenticationError(ProviderError):
    """Invalid or missing API key."""


class ProviderPermissionError(ProviderError):
    """API key lacks required permissions."""


class RateLimitError(ProviderError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        original: Exception | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, provider=provider, original=original)
        self.retry_after = retry_after


class ModelNotFoundError(ProviderError):
    """Requested model does not exist or is not accessible."""


class ProviderUnavailableError(ProviderError, RuntimeError):
    """Provider is not ready (CLI missing, service down, etc.).

    Inherits ``RuntimeError`` so existing ``except RuntimeError`` handlers
    continue to catch it without modification.
    """


class ProviderConnectionError(ProviderError):
    """Network or timeout error communicating with the provider."""
