"""Tests for quota enforcement integration."""

import pytest
from fastapi import HTTPException

from kernel.repositories.audit import AuditRepository
from kernel.security.access import AppContext, check_quota


class TestQuotaEnforcement:
    """Tests for check_quota with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_quota_check_passes_under_limit(self, db_session):
        repo = AuditRepository(db_session)
        ctx = AppContext(app_id="promptforge", max_api_calls_per_hour=100)
        # Should not raise
        await check_quota(ctx, "api_calls", repo)

    @pytest.mark.asyncio
    async def test_quota_exceeded_returns_429(self, db_session):
        repo = AuditRepository(db_session)
        ctx = AppContext(app_id="test-quota", max_api_calls_per_hour=2)

        # Use up the quota
        await repo.increment_usage("test-quota", "api_calls")
        await repo.increment_usage("test-quota", "api_calls")

        with pytest.raises(HTTPException) as exc_info:
            await check_quota(ctx, "api_calls", repo)
        assert exc_info.value.status_code == 429
        assert "exceeded quota" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_quota_increments_on_check(self, db_session):
        repo = AuditRepository(db_session)
        ctx = AppContext(app_id="test-inc", max_api_calls_per_hour=100)

        await check_quota(ctx, "api_calls", repo)
        usage = await repo.get_usage("test-inc", "api_calls")
        assert usage == 1

    @pytest.mark.asyncio
    async def test_documents_quota(self, db_session):
        repo = AuditRepository(db_session)
        ctx = AppContext(app_id="test-docs", max_documents=1)

        await check_quota(ctx, "documents", repo)

        with pytest.raises(HTTPException) as exc_info:
            await check_quota(ctx, "documents", repo)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_unknown_resource_no_limit(self, db_session):
        repo = AuditRepository(db_session)
        ctx = AppContext(app_id="test-unknown")

        # Unknown resource types have no limit configured — check_quota still increments
        await check_quota(ctx, "unknown_resource", repo)
        usage = await repo.get_usage("test-unknown", "unknown_resource")
        assert usage == 1


class TestUsageSummaryEndpoint:
    """Tests for the all-apps usage endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_usage_endpoint(self, client):
        resp = await client.get("/api/kernel/audit/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "usage" in data
        assert isinstance(data["usage"], list)
