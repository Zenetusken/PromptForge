"""Tests for quota enforcement in kernel VFS, Storage, and Settings routers."""

import pytest

from kernel.registry.app_registry import AppRecord, AppStatus, get_app_registry
from kernel.registry.manifest import AppManifest, CapabilitiesDef, ResourceQuota


def _register_test_app(
    app_id: str = "test-app",
    max_api_calls: int = 1000,
    capabilities: list[str] | None = None,
):
    """Register a test app in the registry with specific quotas."""
    from kernel.registry.hooks import AppBase

    class _TestApp(AppBase):
        @property
        def app_id(self):
            return app_id

    manifest = AppManifest(
        id=app_id,
        python_module="apps.test",
        entry_point="TestApp",
        capabilities=CapabilitiesDef(
            required=capabilities or ["vfs:read", "vfs:write", "storage:read",
                                       "storage:write", "settings:read", "settings:write"],
        ),
        resource_quotas=ResourceQuota(max_api_calls_per_hour=max_api_calls),
    )
    registry = get_app_registry()
    registry._apps[app_id] = AppRecord(
        manifest=manifest, instance=_TestApp(), status=AppStatus.ENABLED,
    )


class TestVfsQuotaEnforcement:
    """VFS mutation endpoints return 429 when quota exceeded."""

    @pytest.mark.asyncio
    async def test_create_folder_quota_exceeded(self, client, db_session):
        _register_test_app("quota-app", max_api_calls=0)
        resp = await client.post(
            "/api/kernel/vfs/quota-app/folders",
            json={"name": "test"},
        )
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_create_file_quota_exceeded(self, client, db_session):
        _register_test_app("quota-app2", max_api_calls=0)
        resp = await client.post(
            "/api/kernel/vfs/quota-app2/files",
            json={"name": "test.txt", "content": "hi"},
        )
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_create_folder_quota_ok(self, client, db_session):
        _register_test_app("ok-app", max_api_calls=100)
        resp = await client.post(
            "/api/kernel/vfs/ok-app/folders",
            json={"name": "test"},
        )
        assert resp.status_code == 201


class TestStorageQuotaEnforcement:
    """Storage mutation endpoints return 429 when quota exceeded."""

    @pytest.mark.asyncio
    async def test_create_collection_quota_exceeded(self, client, db_session):
        _register_test_app("storage-q-app", max_api_calls=0)
        resp = await client.post(
            "/api/kernel/storage/storage-q-app/collections",
            json={"name": "test-coll"},
        )
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_create_document_quota_exceeded(self, client, db_session):
        _register_test_app("storage-q-app2", max_api_calls=0)
        resp = await client.post(
            "/api/kernel/storage/storage-q-app2/documents",
            json={"name": "doc", "content": "data"},
        )
        assert resp.status_code == 429


class TestSettingsQuotaEnforcement:
    """Settings mutation endpoints return 429 when quota exceeded."""

    @pytest.mark.asyncio
    async def test_update_settings_quota_exceeded(self, client, db_session):
        _register_test_app("settings-q-app", max_api_calls=0)
        resp = await client.put(
            "/api/kernel/settings/settings-q-app",
            json={"settings": {"key": "val"}},
        )
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_reset_settings_quota_exceeded(self, client, db_session):
        _register_test_app("settings-q-app2", max_api_calls=0)
        resp = await client.delete("/api/kernel/settings/settings-q-app2")
        assert resp.status_code == 429
