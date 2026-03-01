"""Tests for deny-by-default capability enforcement and require_capability factory."""

import pytest
from fastapi import HTTPException

from kernel.registry.manifest import AppManifest, CapabilitiesDef
from kernel.security.access import (
    AppContext,
    LEGACY_PERMISSIVE_CAPABILITIES,
    check_capability,
    require_capability,
)


class TestRequireCapability:
    """Tests for the require_capability dependency factory."""

    def test_factory_returns_callable(self):
        dep = require_capability("storage:read")
        assert callable(dep)

    def test_registered_app_with_capability_passes(self):
        """A registered app with the required capability should pass."""
        from kernel.registry.app_registry import AppRecord, AppStatus, get_app_registry
        from kernel.registry.hooks import AppBase

        class _TestApp(AppBase):
            @property
            def app_id(self):
                return "cap-test-ok"

        manifest = AppManifest(
            id="cap-test-ok",
            python_module="apps.test",
            entry_point="TestApp",
            capabilities=CapabilitiesDef(required=["storage:read"]),
        )
        registry = get_app_registry()
        registry._apps["cap-test-ok"] = AppRecord(
            manifest=manifest, instance=_TestApp(), status=AppStatus.ENABLED,
        )

        try:
            dep = require_capability("storage:read")
            ctx = dep(app_id="cap-test-ok")
            assert ctx.app_id == "cap-test-ok"
            assert "storage:read" in ctx.capabilities
        finally:
            registry._apps.pop("cap-test-ok", None)

    def test_registered_app_without_capability_denied(self):
        """A registered app missing the capability gets 403."""
        from kernel.registry.app_registry import AppRecord, AppStatus, get_app_registry
        from kernel.registry.hooks import AppBase

        class _TestApp(AppBase):
            @property
            def app_id(self):
                return "cap-test-deny"

        manifest = AppManifest(
            id="cap-test-deny",
            python_module="apps.test",
            entry_point="TestApp",
            capabilities=CapabilitiesDef(required=["settings:read"]),
        )
        registry = get_app_registry()
        registry._apps["cap-test-deny"] = AppRecord(
            manifest=manifest, instance=_TestApp(), status=AppStatus.ENABLED,
        )

        try:
            dep = require_capability("storage:write")
            with pytest.raises(HTTPException) as exc_info:
                dep(app_id="cap-test-deny")
            assert exc_info.value.status_code == 403
            assert "storage:write" in str(exc_info.value.detail)
        finally:
            registry._apps.pop("cap-test-deny", None)

    def test_unknown_app_denied(self):
        """Unknown apps with empty capabilities should be denied."""
        dep = require_capability("storage:read")
        with pytest.raises(HTTPException) as exc_info:
            dep(app_id="totally-unknown-app-xyz")
        assert exc_info.value.status_code == 403


class TestLegacyPermissiveCapabilities:
    """Tests for the legacy alias."""

    def test_alias_matches_legacy(self):
        from kernel.security.access import PERMISSIVE_CAPABILITIES
        assert PERMISSIVE_CAPABILITIES == LEGACY_PERMISSIVE_CAPABILITIES

    def test_legacy_set_has_expected_capabilities(self):
        expected = {"settings:read", "settings:write", "storage:read", "storage:write",
                    "vfs:read", "vfs:write", "audit:read", "llm:invoke"}
        assert LEGACY_PERMISSIVE_CAPABILITIES == expected


class TestKernelContextPermissive:
    """Tests that kernel-level contexts remain permissive."""

    def test_kernel_context_has_capabilities(self):
        from kernel.security.dependencies import get_kernel_context
        ctx = get_kernel_context()
        assert ctx.app_id == "kernel"
        assert "audit:read" in ctx.capabilities
        assert "storage:read" in ctx.capabilities


class TestEndpointCapabilityEnforcement:
    """Integration tests hitting kernel endpoints as unknown vs registered apps."""

    @pytest.mark.asyncio
    async def test_unknown_app_gets_403_on_settings(self, client):
        resp = await client.get("/api/kernel/settings/totally-unknown-app-xyz")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unknown_app_gets_403_on_storage(self, client):
        resp = await client.get("/api/kernel/storage/totally-unknown-app-xyz/collections")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unknown_app_gets_403_on_vfs(self, client):
        resp = await client.get("/api/kernel/vfs/totally-unknown-app-xyz/children")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_registered_app_passes_settings(self, client):
        # promptforge is registered and has settings:read
        resp = await client.get("/api/kernel/settings/promptforge")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_cross_app_audit_still_works(self, client):
        # Cross-app endpoints use kernel context, should still work
        resp = await client.get("/api/kernel/audit/all")
        assert resp.status_code == 200
