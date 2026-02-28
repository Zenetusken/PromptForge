"""Tests for the kernel ServiceRegistry."""

import pytest

from kernel.services.registry import ServiceRegistry


class TestServiceRegistry:
    """ServiceRegistry register/get/has/validate tests."""

    def test_register_and_get(self):
        reg = ServiceRegistry()
        reg.register("llm", "fake-provider")
        assert reg.get("llm") == "fake-provider"

    def test_get_missing_raises(self):
        reg = ServiceRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.get("missing")

    def test_has(self):
        reg = ServiceRegistry()
        assert reg.has("llm") is False
        reg.register("llm", "fake")
        assert reg.has("llm") is True

    def test_validate_requirements_all_satisfied(self):
        reg = ServiceRegistry()
        reg.register("llm", "fake")
        reg.register("db", "fake-db")
        assert reg.validate_requirements(["llm", "db"]) == []

    def test_validate_requirements_some_missing(self):
        reg = ServiceRegistry()
        reg.register("llm", "fake")
        missing = reg.validate_requirements(["llm", "storage", "cache"])
        assert missing == ["storage", "cache"]

    def test_validate_empty_requirements(self):
        reg = ServiceRegistry()
        assert reg.validate_requirements([]) == []

    def test_registered_names(self):
        reg = ServiceRegistry()
        reg.register("llm", "a")
        reg.register("db", "b")
        assert sorted(reg.registered_names) == ["db", "llm"]

    def test_overwrite_warning(self):
        reg = ServiceRegistry()
        reg.register("llm", "first")
        reg.register("llm", "second")
        assert reg.get("llm") == "second"


class TestKernelObject:
    """Tests for the Kernel dataclass."""

    def test_kernel_construction(self):
        from kernel.core import Kernel

        kernel = Kernel(
            app_registry=None,  # type: ignore
            db_session_factory=None,  # type: ignore
        )
        assert kernel.services is not None
        assert kernel.services.has("llm") is False

    def test_kernel_with_services(self):
        from kernel.core import Kernel

        kernel = Kernel(
            app_registry=None,  # type: ignore
            db_session_factory=None,  # type: ignore
        )
        kernel.services.register("llm", "test-provider")
        assert kernel.services.get("llm") == "test-provider"
