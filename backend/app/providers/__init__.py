"""LLM provider registry with auto-detection and explicit selection.

All module-level functions delegate to a ``ProviderRegistry`` singleton.
Existing imports (``get_provider``, ``list_all_providers``, etc.) continue
to work unchanged.
"""

import os

from app.providers.base import LLMProvider, invalidate_which_cache, which_claude_cached
from app.providers.registry import ProviderRegistry

__all__ = [
    "LLMProvider",
    "get_provider",
    "list_all_providers",
    "invalidate_detect_cache",
    "_registry",
]

# ---------------------------------------------------------------------------
# Singleton registry instance — populated once at import time.
# ---------------------------------------------------------------------------

_registry = ProviderRegistry()

_registry.register(
    "claude-cli",
    "app.providers.claude_cli",
    "ClaudeCLIProvider",
    gate=which_claude_cached,
)
_registry.register(
    "anthropic",
    "app.providers.anthropic_api",
    "AnthropicAPIProvider",
    gate=lambda: bool(os.getenv("ANTHROPIC_API_KEY")),
)
_registry.register(
    "openai",
    "app.providers.openai_provider",
    "OpenAIProvider",
    gate=lambda: bool(os.getenv("OPENAI_API_KEY")),
)
_registry.register(
    "gemini",
    "app.providers.gemini_provider",
    "GeminiProvider",
    gate=lambda: bool(os.getenv("GEMINI_API_KEY")),
)


# ---------------------------------------------------------------------------
# Public API — thin wrappers that delegate to the registry.
# ---------------------------------------------------------------------------


def get_provider(
    provider_name: str | None = None,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> LLMProvider:
    """Return an LLM provider instance.

    Resolution order:
    1. Explicit *provider_name* argument
    2. ``LLM_PROVIDER`` environment variable
    3. Auto-detect: Claude CLI -> ANTHROPIC_API_KEY -> OPENAI_API_KEY -> GEMINI_API_KEY

    Optional *api_key* and *model* override environment defaults when
    *provider_name* is given explicitly.
    """
    return _registry.get(provider_name, api_key=api_key, model=model)


def list_all_providers() -> list[dict]:
    """Return metadata for all registered providers."""
    return _registry.list_providers()


def invalidate_detect_cache() -> None:
    """Clear the auto-detect, instance, and shutil.which caches."""
    _registry.invalidate_caches()
    invalidate_which_cache()


def _load_provider(
    name: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> LLMProvider:
    """Lazily import and instantiate a provider by registry name."""
    return _registry._load_provider(name, api_key=api_key, model=model)
