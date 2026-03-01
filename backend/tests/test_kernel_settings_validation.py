"""Tests for settings schema validation in kernel settings router."""

import pytest

from kernel.registry.app_registry import AppRecord, AppStatus, get_app_registry
from kernel.registry.manifest import (
    AppManifest,
    CapabilitiesDef,
    FrontendManifest,
    SettingsDef,
)


def _register_app_with_schema(app_id: str, schema: dict):
    """Register a test app with a settings schema."""
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
            required=["settings:read", "settings:write"],
        ),
        frontend=FrontendManifest(
            settings=SettingsDef(schema=schema),
        ),
    )
    registry = get_app_registry()
    registry._apps[app_id] = AppRecord(
        manifest=manifest, instance=_TestApp(), status=AppStatus.ENABLED,
    )


def _register_app_without_schema(app_id: str):
    """Register a test app without a settings schema."""
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
            required=["settings:read", "settings:write"],
        ),
    )
    registry = get_app_registry()
    registry._apps[app_id] = AppRecord(
        manifest=manifest, instance=_TestApp(), status=AppStatus.ENABLED,
    )


class TestSettingsSchemaValidation:
    """Tests for schema-based validation of settings updates."""

    @pytest.mark.asyncio
    async def test_unknown_key_rejected(self, client):
        _register_app_with_schema("schema-app", {
            "theme": {"type": "string", "default": "dark"},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-app",
            json={"settings": {"invalid_key": "value"}},
        )
        assert resp.status_code == 422
        assert "Unknown setting key" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_valid_key_accepted(self, client):
        _register_app_with_schema("schema-app2", {
            "theme": {"type": "string", "default": "dark"},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-app2",
            json={"settings": {"theme": "light"}},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_type_mismatch_rejected(self, client):
        _register_app_with_schema("schema-app3", {
            "enabled": {"type": "boolean", "default": True},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-app3",
            json={"settings": {"enabled": "not-a-bool"}},
        )
        assert resp.status_code == 422
        assert "expects type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_boolean_type_check(self, client):
        _register_app_with_schema("schema-app4", {
            "flag": {"type": "boolean", "default": False},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-app4",
            json={"settings": {"flag": True}},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_schema_accepts_anything(self, client):
        _register_app_without_schema("no-schema-app")
        resp = await client.put(
            "/api/kernel/settings/no-schema-app",
            json={"settings": {"any_key": "any_value", "another": 42}},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_app_accepts_anything(self, client):
        # Apps not in registry get permissive access
        resp = await client.put(
            "/api/kernel/settings/nonexistent-app",
            json={"settings": {"key": "val"}},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_boolean_false_accepted(self, client):
        _register_app_with_schema("schema-bool-false", {
            "flag": {"type": "boolean", "default": True},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-bool-false",
            json={"settings": {"flag": False}},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_integer_rejects_bool_true(self, client):
        """bool is a subclass of int in Python — ensure booleans are rejected for integer type."""
        _register_app_with_schema("schema-int-bool", {
            "count": {"type": "integer", "default": 0},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-int-bool",
            json={"settings": {"count": True}},
        )
        assert resp.status_code == 422
        assert "expects type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_integer_rejects_string(self, client):
        _register_app_with_schema("schema-int-str", {
            "count": {"type": "integer", "default": 0},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-int-str",
            json={"settings": {"count": "123"}},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_number_accepts_float(self, client):
        _register_app_with_schema("schema-num-float", {
            "ratio": {"type": "number", "default": 1.0},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-num-float",
            json={"settings": {"ratio": 3.14}},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_number_rejects_bool(self, client):
        _register_app_with_schema("schema-num-bool", {
            "ratio": {"type": "number", "default": 1.0},
        })
        resp = await client.put(
            "/api/kernel/settings/schema-num-bool",
            json={"settings": {"ratio": False}},
        )
        assert resp.status_code == 422
