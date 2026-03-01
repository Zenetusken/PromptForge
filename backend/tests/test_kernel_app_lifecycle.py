"""Tests for kernel app lifecycle management — enable, disable, state persistence."""

import pytest

from kernel.registry.app_registry import AppRecord, AppStatus, get_app_registry
from kernel.registry.manifest import AppManifest, CapabilitiesDef


def _register_lifecycle_app(app_id: str = "lifecycle-app"):
    """Register a test app for lifecycle tests."""
    from kernel.registry.hooks import AppBase

    class _LifecycleApp(AppBase):
        hooks_called: list[str] = []

        @property
        def app_id(self):
            return app_id

        async def on_enable(self, kernel):
            _LifecycleApp.hooks_called.append("on_enable")

        async def on_disable(self, kernel):
            _LifecycleApp.hooks_called.append("on_disable")

        async def on_startup(self, kernel):
            _LifecycleApp.hooks_called.append("on_startup")

        async def on_shutdown(self, kernel):
            _LifecycleApp.hooks_called.append("on_shutdown")

    _LifecycleApp.hooks_called = []

    manifest = AppManifest(
        id=app_id,
        python_module="apps.test",
        entry_point="TestApp",
        capabilities=CapabilitiesDef(
            required=["settings:read", "settings:write", "vfs:read", "vfs:write"],
        ),
    )
    registry = get_app_registry()
    instance = _LifecycleApp()
    registry._apps[app_id] = AppRecord(
        manifest=manifest, instance=instance, status=AppStatus.ENABLED,
    )
    return instance


class TestAppEnableDisable:
    """Tests for the enable/disable API endpoints."""

    @pytest.mark.asyncio
    async def test_disable_app(self, client):
        instance = _register_lifecycle_app("disable-test")
        resp = await client.post("/api/kernel/apps/disable-test/disable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_enable_app(self, client):
        _register_lifecycle_app("enable-test")
        # First disable
        await client.post("/api/kernel/apps/enable-test/disable")
        # Then enable
        resp = await client.post("/api/kernel/apps/enable-test/enable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enabled"

    @pytest.mark.asyncio
    async def test_disable_nonexistent_app(self, client):
        resp = await client.post("/api/kernel/apps/nonexistent/disable")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_enable_nonexistent_app(self, client):
        resp = await client.post("/api/kernel/apps/nonexistent/enable")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_disable_already_disabled(self, client):
        _register_lifecycle_app("double-disable")
        await client.post("/api/kernel/apps/double-disable/disable")
        resp = await client.post("/api/kernel/apps/double-disable/disable")
        assert resp.status_code == 200
        assert "Already disabled" in resp.json().get("message", "")

    @pytest.mark.asyncio
    async def test_enable_already_enabled(self, client):
        _register_lifecycle_app("double-enable")
        resp = await client.post("/api/kernel/apps/double-enable/enable")
        assert resp.status_code == 200
        assert "Already enabled" in resp.json().get("message", "")


class TestDisabledAppReturns503:
    """Disabled apps should return 503 on kernel service endpoints."""

    @pytest.mark.asyncio
    async def test_disabled_app_vfs_returns_503(self, client):
        _register_lifecycle_app("disabled-vfs-app")
        await client.post("/api/kernel/apps/disabled-vfs-app/disable")
        resp = await client.get("/api/kernel/vfs/disabled-vfs-app/children")
        assert resp.status_code == 503
        assert "disabled" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_disabled_app_settings_returns_503(self, client):
        _register_lifecycle_app("disabled-settings-app")
        await client.post("/api/kernel/apps/disabled-settings-app/disable")
        resp = await client.get("/api/kernel/settings/disabled-settings-app")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_disabled_app_storage_returns_503(self, client):
        _register_lifecycle_app("disabled-storage-app")
        await client.post("/api/kernel/apps/disabled-storage-app/disable")
        resp = await client.get("/api/kernel/storage/disabled-storage-app/collections")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_reenabled_app_works(self, client):
        _register_lifecycle_app("reenable-app")
        await client.post("/api/kernel/apps/reenable-app/disable")
        resp = await client.get("/api/kernel/vfs/reenable-app/children")
        assert resp.status_code == 503

        await client.post("/api/kernel/apps/reenable-app/enable")
        resp = await client.get("/api/kernel/vfs/reenable-app/children")
        assert resp.status_code == 200


class TestAppStatusEndpoint:
    """Tests for the detailed status endpoint."""

    @pytest.mark.asyncio
    async def test_get_app_status(self, client):
        _register_lifecycle_app("status-app")
        resp = await client.get("/api/kernel/apps/status-app/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "status-app"
        assert data["status"] == "enabled"
        assert "capabilities" in data
        assert "resource_quotas" in data

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, client):
        resp = await client.get("/api/kernel/apps/nonexistent/status")
        assert resp.status_code == 404


class TestLifecycleHooks:
    """Tests that lifecycle hooks are invoked correctly."""

    @pytest.mark.asyncio
    async def test_disable_calls_shutdown_then_disable(self, client):
        instance = _register_lifecycle_app("hooks-disable")
        type(instance).hooks_called = []
        await client.post("/api/kernel/apps/hooks-disable/disable")
        hooks = type(instance).hooks_called
        assert "on_shutdown" in hooks
        assert "on_disable" in hooks
        # Shutdown should be called before disable
        assert hooks.index("on_shutdown") < hooks.index("on_disable")

    @pytest.mark.asyncio
    async def test_enable_calls_enable_then_startup(self, client):
        instance = _register_lifecycle_app("hooks-enable")
        await client.post("/api/kernel/apps/hooks-enable/disable")
        type(instance).hooks_called = []
        await client.post("/api/kernel/apps/hooks-enable/enable")
        hooks = type(instance).hooks_called
        assert "on_enable" in hooks
        assert "on_startup" in hooks
        assert hooks.index("on_enable") < hooks.index("on_startup")
