"""Tests for kernel audit integration — cross-app audit endpoints and summary."""

import pytest
from kernel.repositories.audit import AuditRepository


class TestAuditRepository:
    """Tests for the new cross-app repository methods."""

    @pytest.mark.asyncio
    async def test_list_all_logs(self, db_session):
        repo = AuditRepository(db_session)
        await repo.log_action("promptforge", "optimize", "optimization", resource_id="opt-1")
        await repo.log_action("textforge", "transform", "transform", resource_id="tf-1")
        await db_session.commit()

        logs = await repo.list_all_logs(limit=50, offset=0)
        assert len(logs) == 2
        app_ids = {log["app_id"] for log in logs}
        assert app_ids == {"promptforge", "textforge"}

    @pytest.mark.asyncio
    async def test_list_all_logs_filter_by_action(self, db_session):
        repo = AuditRepository(db_session)
        await repo.log_action("promptforge", "optimize", "optimization")
        await repo.log_action("textforge", "transform", "transform")
        await db_session.commit()

        logs = await repo.list_all_logs(action="optimize")
        assert len(logs) == 1
        assert logs[0]["action"] == "optimize"

    @pytest.mark.asyncio
    async def test_list_all_logs_filter_by_resource_type(self, db_session):
        repo = AuditRepository(db_session)
        await repo.log_action("promptforge", "optimize", "optimization")
        await repo.log_action("textforge", "transform", "transform")
        await db_session.commit()

        logs = await repo.list_all_logs(resource_type="transform")
        assert len(logs) == 1
        assert logs[0]["resource_type"] == "transform"

    @pytest.mark.asyncio
    async def test_count_all_logs(self, db_session):
        repo = AuditRepository(db_session)
        await repo.log_action("promptforge", "optimize", "optimization")
        await repo.log_action("textforge", "transform", "transform")
        await db_session.commit()

        count = await repo.count_all_logs()
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_all_logs_with_filter(self, db_session):
        repo = AuditRepository(db_session)
        await repo.log_action("promptforge", "optimize", "optimization")
        await repo.log_action("textforge", "transform", "transform")
        await db_session.commit()

        count = await repo.count_all_logs(action="transform")
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_summary(self, db_session):
        repo = AuditRepository(db_session)
        await repo.log_action("promptforge", "optimize", "optimization")
        await repo.log_action("promptforge", "optimize", "optimization")
        await repo.log_action("textforge", "transform", "transform")
        await db_session.commit()

        summary = await repo.get_summary()
        assert len(summary) == 2

        pf_entry = next(s for s in summary if s["app_id"] == "promptforge")
        assert pf_entry["count"] == 2
        assert pf_entry["action"] == "optimize"

        tf_entry = next(s for s in summary if s["app_id"] == "textforge")
        assert tf_entry["count"] == 1

    @pytest.mark.asyncio
    async def test_get_all_apps_usage(self, db_session):
        repo = AuditRepository(db_session)
        await repo.increment_usage("promptforge", "api_calls")
        await repo.increment_usage("textforge", "api_calls")
        await db_session.commit()

        usage = await repo.get_all_apps_usage()
        assert len(usage) == 2
        app_ids = {u["app_id"] for u in usage}
        assert app_ids == {"promptforge", "textforge"}


class TestAuditEndpoints:
    """Tests for the new cross-app audit REST endpoints."""

    @pytest.mark.asyncio
    async def test_list_all_audit_logs(self, client):
        resp = await client.get("/api/kernel/audit/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_audit_summary(self, client):
        resp = await client.get("/api/kernel/audit/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_get_all_usage(self, client):
        resp = await client.get("/api/kernel/audit/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "usage" in data
