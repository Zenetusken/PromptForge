"""ProviderRegistry — centralised provider registration, caching, and resolution."""

from __future__ import annotations

import dataclasses
import importlib
import logging
import os
import time
from collections.abc import Callable

from app.providers.base import LLMProvider
from app.providers.errors import ProviderUnavailableError
from app.providers.models import MODEL_CATALOG, REQUIRES_API_KEY

logger = logging.getLogger(__name__)

_ENV_KEYS = ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")
_DETECT_TTL = 60.0


def _serialize_models(provider_name: str) -> list[dict]:
    """Serialize model catalog entries for a provider.

    Converts frozenset capabilities to a sorted list for stable JSON output.
    """
    result = []
    for m in MODEL_CATALOG.get(provider_name, []):
        d = dataclasses.asdict(m)
        d["capabilities"] = sorted(d["capabilities"])
        result.append(d)
    return result


class ProviderRegistry:
    """Registry of LLM providers with auto-detection and instance caching.

    Replaces the former module-level dicts and functions in ``__init__.py``
    with an encapsulated, testable object.
    """

    def __init__(self) -> None:
        # Maps provider name -> (module_path, class_name)
        self._providers: dict[str, tuple[str, str]] = {}
        # Auto-detect order: (gate_check, provider_name)
        self._detect_order: list[tuple[Callable[[], bool], str]] = []
        # Auto-detect result cache
        self._detect_cache: tuple[str | None, float, str] | None = None
        # Default (no override) instance cache
        self._instance_cache: dict[str, LLMProvider] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        module_path: str,
        class_name: str,
        *,
        gate: Callable[[], bool] | None = None,
    ) -> None:
        """Register a provider.

        Parameters
        ----------
        name:
            Short identifier (e.g. ``"anthropic"``).
        module_path:
            Fully-qualified module (e.g. ``"app.providers.anthropic_api"``).
        class_name:
            Class to instantiate (e.g. ``"AnthropicAPIProvider"``).
        gate:
            Optional fast-check callable used during auto-detection to skip
            providers whose prerequisite (CLI on PATH, env var) is absent.
        """
        self._providers[name] = (module_path, class_name)
        if gate is not None:
            self._detect_order.append((gate, name))

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def get(
        self,
        provider_name: str | None = None,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> LLMProvider:
        """Return an LLM provider instance.

        Resolution order:
        1. Explicit *provider_name* argument
        2. ``LLM_PROVIDER`` environment variable
        3. Auto-detect via gate checks + ``is_available()``
        """
        name = provider_name or os.getenv("LLM_PROVIDER", "").strip()
        if name:
            provider = self._load_provider(name, api_key=api_key, model=model)
            if not provider.is_available():
                raise ProviderUnavailableError(
                    f"LLM provider {name!r} was selected but is not available. "
                    f"Check that the required API key is set or CLI tool is installed.",
                    provider=name,
                )
            logger.info("Using explicitly selected LLM provider: %s", provider.provider_name)
            return provider

        detected = self._auto_detect_name()
        if detected is not None:
            provider = self._load_provider(detected, api_key=api_key, model=model)
            logger.info("Auto-detected LLM provider: %s", provider.provider_name)
            return provider

        raise ProviderUnavailableError(
            "No LLM provider available. Options:\n"
            "  1. Install the Claude CLI "
            "(npm install -g @anthropic-ai/claude-code) for MAX subscription\n"
            "  2. Set ANTHROPIC_API_KEY for Anthropic API access\n"
            "  3. Set OPENAI_API_KEY for OpenAI access\n"
            "  4. Set GEMINI_API_KEY for Google Gemini access\n"
            "  5. Set LLM_PROVIDER to explicitly choose a provider",
        )

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_providers(self) -> list[dict]:
        """Return metadata for all registered providers."""
        default_name: str | None = None
        env_name = os.getenv("LLM_PROVIDER", "").strip()
        if env_name:
            default_name = env_name if env_name in self._providers else None
        else:
            default_name = self._auto_detect_name()

        result = []
        for name in self._providers:
            models = _serialize_models(name)
            try:
                provider = self._get_default_instance(name)
                result.append({
                    "name": name,
                    "display_name": provider.provider_name,
                    "model": provider.model_name,
                    "available": provider.is_available(),
                    "is_default": name == default_name,
                    "requires_api_key": REQUIRES_API_KEY.get(name, True),
                    "models": models,
                })
            except Exception:
                logger.debug("Could not load provider %s", name, exc_info=True)
                result.append({
                    "name": name,
                    "display_name": name,
                    "model": "",
                    "available": False,
                    "is_default": name == default_name,
                    "requires_api_key": REQUIRES_API_KEY.get(name, True),
                    "models": models,
                })
        return result

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate_caches(self) -> None:
        """Clear the auto-detect and instance caches."""
        self._detect_cache = None
        self._instance_cache.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_provider(
        self,
        name: str,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> LLMProvider:
        """Lazily import and instantiate a provider by registry name."""
        if name not in self._providers:
            available = ", ".join(sorted(self._providers))
            raise ValueError(f"Unknown LLM provider {name!r}. Available: {available}")

        module_path, class_name = self._providers[name]
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(
                f"Provider {name!r} requires additional dependencies. "
                f"Install with: pip install promptforge-backend[{name}]"
            ) from exc

        cls = getattr(module, class_name)

        field_names = {f.name for f in dataclasses.fields(cls)}
        kwargs: dict[str, str] = {}
        if api_key and "api_key" in field_names:
            kwargs["api_key"] = api_key
        if model and "model" in field_names:
            kwargs["model"] = model

        return cls(**kwargs)

    def _auto_detect_name(self) -> str | None:
        """Return the name of the first available provider, using the cache."""
        now = time.monotonic()
        snap = self._env_snapshot()

        if self._detect_cache is not None:
            cached_name, cached_time, cached_snap = self._detect_cache
            if now - cached_time < _DETECT_TTL and cached_snap == snap:
                return cached_name

        detected: str | None = None
        for gate, name in self._detect_order:
            if not gate():
                continue
            try:
                provider = self._get_default_instance(name)
                if provider.is_available():
                    detected = name
                    break
            except ImportError:
                pass

        self._detect_cache = (detected, now, snap)
        return detected

    def _get_default_instance(self, name: str) -> LLMProvider:
        """Return a cached default-config provider instance."""
        if name not in self._instance_cache:
            self._instance_cache[name] = self._load_provider(name)
        return self._instance_cache[name]

    def _env_snapshot(self) -> str:
        """Compact fingerprint of detection-relevant env vars."""
        return "|".join(os.getenv(k, "") for k in _ENV_KEYS)
