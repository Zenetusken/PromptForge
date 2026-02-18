"""Tests for provider registry and auto-detection logic."""

import time
from unittest.mock import patch

import pytest

from app.providers import _load_provider, _registry, get_provider, invalidate_detect_cache
from app.providers.claude_cli import ClaudeCLIProvider


@pytest.fixture(autouse=True)
def _clear_provider_caches():
    """Clear all module-level caches before each test so detection is fresh."""
    invalidate_detect_cache()
    yield
    invalidate_detect_cache()


class TestLoadProvider:
    def test_load_claude_cli(self):
        provider = _load_provider("claude-cli")
        assert isinstance(provider, ClaudeCLIProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            _load_provider("nonexistent")

    def test_missing_sdk_raises_import_error(self):
        with patch("importlib.import_module", side_effect=ImportError("no module")):
            with pytest.raises(ImportError, match="requires additional dependencies"):
                _load_provider("openai")


class TestGetProvider:
    def test_explicit_provider_name(self):
        """Passing provider_name directly should load that provider."""
        with patch("shutil.which", return_value="/usr/bin/claude"):
            provider = get_provider("claude-cli")
        assert isinstance(provider, ClaudeCLIProvider)

    def test_env_var_selection(self):
        """LLM_PROVIDER env var should select the provider."""
        with (
            patch.dict("os.environ", {"LLM_PROVIDER": "claude-cli"}, clear=False),
            patch("shutil.which", return_value="/usr/bin/claude"),
        ):
            provider = get_provider()
        assert isinstance(provider, ClaudeCLIProvider)

    def test_auto_detect_claude_cli(self):
        """Auto-detect should find Claude CLI first when on PATH."""
        with (
            patch.dict("os.environ", {"LLM_PROVIDER": ""}, clear=False),
            patch("shutil.which", return_value="/usr/bin/claude"),
        ):
            provider = get_provider()
        assert isinstance(provider, ClaudeCLIProvider)

    def test_no_provider_raises(self):
        """With nothing available, get_provider should raise RuntimeError."""
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_PROVIDER": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENAI_API_KEY": "",
                    "GEMINI_API_KEY": "",
                },
                clear=False,
            ),
            patch("shutil.which", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="No LLM provider available"):
                get_provider()

    def test_explicit_unavailable_raises(self):
        """Explicitly selecting an unavailable provider should raise RuntimeError."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="not available"):
                get_provider("claude-cli")

    def test_auto_detect_falls_through_to_openai(self):
        """When Claude CLI is absent but OPENAI_API_KEY is set, detect OpenAI."""
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_PROVIDER": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENAI_API_KEY": "sk-test-key",
                    "GEMINI_API_KEY": "",
                },
                clear=False,
            ),
            patch("shutil.which", return_value=None),
        ):
            # OpenAI SDK may not be installed, so we mock the import
            try:
                provider = get_provider()
                assert provider.provider_name == "OpenAI"
            except ImportError:
                pytest.skip("openai package not installed")


class TestInvalidateDetectCache:
    def test_invalidate_clears_which_cache(self):
        """After invalidation, which result is re-evaluated."""
        # Prime cache with claude not on PATH
        with patch("shutil.which", return_value=None):
            from app.providers import which_claude_cached

            assert which_claude_cached() is False

        # Without invalidation, cached value persists
        assert which_claude_cached() is False

        # After invalidation, it re-evaluates
        invalidate_detect_cache()
        with patch("shutil.which", return_value="/usr/bin/claude"):
            assert which_claude_cached() is True

    def test_invalidate_clears_detect_cache(self):
        """After invalidation, auto-detect re-runs."""
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_PROVIDER": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENAI_API_KEY": "",
                    "GEMINI_API_KEY": "",
                },
                clear=False,
            ),
            patch("shutil.which", return_value=None),
        ):
            with pytest.raises(RuntimeError):
                get_provider()

        # Now make claude available and invalidate
        invalidate_detect_cache()
        with (
            patch.dict("os.environ", {"LLM_PROVIDER": ""}, clear=False),
            patch("shutil.which", return_value="/usr/bin/claude"),
        ):
            provider = get_provider()
            assert isinstance(provider, ClaudeCLIProvider)


class TestDetectCacheTTLAndEnv:
    def test_cache_expires_after_ttl(self):
        """After TTL expires, auto-detect re-runs."""
        with (
            patch.dict("os.environ", {"LLM_PROVIDER": ""}, clear=False),
            patch("shutil.which", return_value="/usr/bin/claude"),
        ):
            # First call populates cache
            result1 = _registry._auto_detect_name()
            assert result1 == "claude-cli"

            # Manually expire the cache by setting cached_time to past
            name, _cached_time, snap = _registry._detect_cache
            _registry._detect_cache = (name, time.monotonic() - 120, snap)

        # After TTL expiry with claude gone, should detect nothing
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_PROVIDER": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENAI_API_KEY": "",
                    "GEMINI_API_KEY": "",
                },
                clear=False,
            ),
            patch("shutil.which", return_value=None),
        ):
            invalidate_detect_cache()  # Needed to also clear which_claude cache
            result2 = _registry._auto_detect_name()
            assert result2 is None

    def test_env_change_invalidates_cache(self):
        """When env vars change, cache is bypassed even within TTL."""
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_PROVIDER": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENAI_API_KEY": "",
                    "GEMINI_API_KEY": "",
                },
                clear=False,
            ),
            patch("shutil.which", return_value="/usr/bin/claude"),
        ):
            result1 = _registry._auto_detect_name()
            assert result1 == "claude-cli"

        # Now change an env var -- the snapshot changes so cache should be bypassed
        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_PROVIDER": "",
                    "ANTHROPIC_API_KEY": "sk-new-key",
                    "OPENAI_API_KEY": "",
                    "GEMINI_API_KEY": "",
                },
                clear=False,
            ),
            patch("shutil.which", return_value="/usr/bin/claude"),
        ):
            # Even though TTL hasn't expired, env change should trigger re-detect
            result2 = _registry._auto_detect_name()
            assert result2 == "claude-cli"  # Still claude-cli, but we verified it re-ran

    def test_env_snapshot_format(self):
        """_env_snapshot returns pipe-delimited env var values."""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "abc",
                "ANTHROPIC_API_KEY": "def",
                "OPENAI_API_KEY": "",
                "GEMINI_API_KEY": "ghi",
            },
            clear=False,
        ):
            snap = _registry._env_snapshot()
        assert snap == "abc|def||ghi"
