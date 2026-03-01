"""Tests for kernel access control — capabilities, quotas, audit log."""

import pytest

from kernel.registry.manifest import AppManifest, CapabilitiesDef, ResourceQuota
from kernel.security.access import AppContext, check_capability, check_quota


# ── AppContext ───────────────────────────────────────────────────────


class TestAppContext:
    """Tests for AppContext construction."""

    def test_from_manifest(self):
        manifest = AppManifest(
            id="test-app",
            python_module="apps.test",
            entry_point="TestApp",
            capabilities=CapabilitiesDef(
                required=["storage:read", "storage:write"],
                optional=["llm:invoke"],
            ),
            resource_quotas=ResourceQuota(
                max_storage_mb=50,
                max_api_calls_per_hour=500,
                max_documents=5000,
            ),
        )
        ctx = AppContext.from_manifest(manifest)
        assert ctx.app_id == "test-app"
        assert "storage:read" in ctx.capabilities
        assert "storage:write" in ctx.capabilities
        assert "llm:invoke" in ctx.capabilities
        assert ctx.max_storage_mb == 50
        assert ctx.max_api_calls_per_hour == 500
        assert ctx.max_documents == 5000

    def test_from_manifest_defaults(self):
        manifest = AppManifest(
            id="minimal",
            python_module="apps.minimal",
            entry_point="MinimalApp",
        )
        ctx = AppContext.from_manifest(manifest)
        assert ctx.capabilities == []
        assert ctx.max_storage_mb == 100
        assert ctx.max_api_calls_per_hour == 1000
        assert ctx.max_documents == 10000

    def test_context_is_frozen(self):
        ctx = AppContext(app_id="test")
        with pytest.raises(AttributeError):
            ctx.app_id = "changed"  # type: ignore[misc]


# ── check_capability ─────────────────────────────────────────────────


class TestCheckCapability:
    """Tests for capability enforcement."""

    def test_capability_present(self):
        ctx = AppContext(app_id="test", capabilities=["storage:read", "llm:invoke"])
        # Should not raise
        check_capability(ctx, "storage:read")
        check_capability(ctx, "llm:invoke")

    def test_capability_missing_raises_403(self):
        ctx = AppContext(app_id="test", capabilities=["storage:read"])
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            check_capability(ctx, "llm:invoke")
        assert exc_info.value.status_code == 403
        assert "llm:invoke" in str(exc_info.value.detail)

    def test_empty_capabilities_raises_403(self):
        ctx = AppContext(app_id="test", capabilities=[])
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            check_capability(ctx, "storage:read")
        assert exc_info.value.status_code == 403


# ── check_quota ──────────────────────────────────────────────────────


class TestCheckQuota:
    """Tests for quota enforcement via audit repository."""

    @pytest.mark.asyncio
    async def test_quota_under_limit(self, db_session):
        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        ctx = AppContext(app_id="test", max_api_calls_per_hour=10)
        # Should not raise
        await check_quota(ctx, "api_calls", repo)

    @pytest.mark.asyncio
    async def test_quota_exceeded_raises_429(self, db_session):
        from fastapi import HTTPException

        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        ctx = AppContext(app_id="test", max_api_calls_per_hour=3)

        # Use up the quota
        for _ in range(3):
            await repo.increment_usage("test", "api_calls")

        with pytest.raises(HTTPException) as exc_info:
            await check_quota(ctx, "api_calls", repo)
        assert exc_info.value.status_code == 429


# ── Manifest extensions ──────────────────────────────────────────────


class TestManifestExtensions:
    """Tests for capabilities and resource_quotas in AppManifest."""

    def test_capabilities_in_manifest(self):
        manifest = AppManifest(
            id="test",
            python_module="apps.test",
            entry_point="TestApp",
            capabilities={"required": ["storage:read"], "optional": ["llm:invoke"]},
        )
        assert manifest.capabilities.required == ["storage:read"]
        assert manifest.capabilities.optional == ["llm:invoke"]

    def test_resource_quotas_in_manifest(self):
        manifest = AppManifest(
            id="test",
            python_module="apps.test",
            entry_point="TestApp",
            resource_quotas={"max_storage_mb": 200, "max_api_calls_per_hour": 2000},
        )
        assert manifest.resource_quotas.max_storage_mb == 200
        assert manifest.resource_quotas.max_api_calls_per_hour == 2000
        assert manifest.resource_quotas.max_documents == 10000  # default

    def test_defaults_when_omitted(self):
        manifest = AppManifest(
            id="test",
            python_module="apps.test",
            entry_point="TestApp",
        )
        assert manifest.capabilities.required == []
        assert manifest.capabilities.optional == []
        assert manifest.resource_quotas.max_storage_mb == 100


# ── Audit router ─────────────────────────────────────────────────────


class TestAuditRouter:
    """Tests for the kernel audit REST API."""

    @pytest.mark.asyncio
    async def test_list_audit_logs_empty(self, client):
        # Use a registered app (promptforge has audit:read capability)
        resp = await client.get("/api/kernel/audit/promptforge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["app_id"] == "promptforge"
        assert data["logs"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_usage_empty(self, client):
        resp = await client.get("/api/kernel/audit/usage/promptforge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["app_id"] == "promptforge"
        assert data["usage"] == []


# ── Audit repository ─────────────────────────────────────────────────


class TestAuditRepository:
    """Tests for audit repository operations."""

    @pytest.mark.asyncio
    async def test_log_action(self, db_session):
        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        entry = await repo.log_action(
            app_id="test", action="create", resource_type="document",
            resource_id="doc-1", details={"name": "test.txt"},
        )
        assert entry["app_id"] == "test"
        assert entry["action"] == "create"
        assert entry["resource_type"] == "document"
        assert entry["details"] == {"name": "test.txt"}

    @pytest.mark.asyncio
    async def test_list_logs(self, db_session):
        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        await repo.log_action("test", "create", "doc", "1")
        await repo.log_action("test", "update", "doc", "1")
        await repo.log_action("test", "delete", "doc", "1")

        logs = await repo.list_logs("test")
        assert len(logs) == 3
        # Most recent first
        assert logs[0]["action"] == "delete"

    @pytest.mark.asyncio
    async def test_count_logs(self, db_session):
        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        await repo.log_action("test", "create", "doc", "1")
        await repo.log_action("test", "update", "doc", "1")

        count = await repo.count_logs("test")
        assert count == 2

    @pytest.mark.asyncio
    async def test_increment_and_get_usage(self, db_session):
        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        count1 = await repo.increment_usage("test", "api_calls")
        assert count1 == 1
        count2 = await repo.increment_usage("test", "api_calls")
        assert count2 == 2
        usage = await repo.get_usage("test", "api_calls")
        assert usage == 2

    @pytest.mark.asyncio
    async def test_get_all_usage(self, db_session):
        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        await repo.increment_usage("test", "api_calls")
        await repo.increment_usage("test", "documents")

        all_usage = await repo.get_all_usage("test")
        resources = {u["resource"] for u in all_usage}
        assert "api_calls" in resources
        assert "documents" in resources

    @pytest.mark.asyncio
    async def test_usage_isolated_by_app(self, db_session):
        from kernel.repositories.audit import AuditRepository

        repo = AuditRepository(db_session)
        await repo.increment_usage("app-a", "api_calls")
        await repo.increment_usage("app-b", "api_calls")

        assert await repo.get_usage("app-a", "api_calls") == 1
        assert await repo.get_usage("app-b", "api_calls") == 1


# ── Permissive fallback ─────────────────────────────────────────────


class TestDenyByDefaultForUnknownApps:
    """Test that unknown apps get empty capabilities (deny-by-default)."""

    def test_unknown_app_gets_empty_capabilities(self):
        from kernel.security.dependencies import get_app_context

        ctx = get_app_context("unknown-nonexistent-app")
        assert ctx.app_id == "unknown-nonexistent-app"
        assert ctx.capabilities == []

    def test_unknown_app_denied_storage_read(self):
        from fastapi import HTTPException
        from kernel.security.dependencies import get_app_context

        ctx = get_app_context("unknown-nonexistent-app")
        with pytest.raises(HTTPException) as exc_info:
            check_capability(ctx, "storage:read")
        assert exc_info.value.status_code == 403

    def test_unknown_app_logs_warning(self, caplog):
        import logging
        from kernel.security.dependencies import get_app_context

        with caplog.at_level(logging.WARNING, logger="kernel.security.dependencies"):
            get_app_context("another-unknown-app")
        assert any("not found in registry" in r.message for r in caplog.records)


# ── Disabled app access ─────────────────────────────────────────────


class TestDisabledAppAccess:
    """Test that disabled apps raise 503 via get_app_context."""

    def test_disabled_app_raises_503(self):
        from fastapi import HTTPException
        from kernel.registry.app_registry import (
            AppRecord,
            AppStatus,
            get_app_registry,
        )
        from kernel.registry.hooks import AppBase
        from kernel.security.dependencies import get_app_context

        class _DisabledApp(AppBase):
            @property
            def app_id(self):
                return "disabled-test"

        manifest = AppManifest(
            id="disabled-test",
            python_module="apps.test",
            entry_point="TestApp",
        )
        registry = get_app_registry()
        registry._apps["disabled-test"] = AppRecord(
            manifest=manifest,
            instance=_DisabledApp(),
            status=AppStatus.DISABLED,
        )

        with pytest.raises(HTTPException) as exc_info:
            get_app_context("disabled-test")
        assert exc_info.value.status_code == 503
