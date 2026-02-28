"""Tests for per-app settings endpoints and repository."""

import pytest

from kernel.repositories.app_settings import AppSettingsRepository


@pytest.mark.asyncio
class TestAppSettingsRepository:
    """CRUD tests for AppSettingsRepository."""

    async def test_get_all_empty(self, db_session):
        repo = AppSettingsRepository(db_session)
        result = await repo.get_all("test-app")
        assert result == {}

    async def test_set_and_get(self, db_session):
        repo = AppSettingsRepository(db_session)
        await repo.set("test-app", "theme", "dark")
        await db_session.commit()

        val = await repo.get("test-app", "theme")
        assert val == "dark"

    async def test_set_updates_existing(self, db_session):
        repo = AppSettingsRepository(db_session)
        await repo.set("test-app", "theme", "dark")
        await db_session.commit()

        await repo.set("test-app", "theme", "light")
        await db_session.commit()

        val = await repo.get("test-app", "theme")
        assert val == "light"

    async def test_get_all_multiple(self, db_session):
        repo = AppSettingsRepository(db_session)
        await repo.set("test-app", "a", 1)
        await repo.set("test-app", "b", "hello")
        await db_session.commit()

        result = await repo.get_all("test-app")
        assert result == {"a": 1, "b": "hello"}

    async def test_delete(self, db_session):
        repo = AppSettingsRepository(db_session)
        await repo.set("test-app", "key1", "val1")
        await db_session.commit()

        deleted = await repo.delete("test-app", "key1")
        await db_session.commit()
        assert deleted is True

        val = await repo.get("test-app", "key1")
        assert val is None

    async def test_reset(self, db_session):
        repo = AppSettingsRepository(db_session)
        await repo.set("test-app", "a", 1)
        await repo.set("test-app", "b", 2)
        await db_session.commit()

        count = await repo.reset("test-app")
        await db_session.commit()
        assert count == 2

        result = await repo.get_all("test-app")
        assert result == {}

    async def test_isolation_between_apps(self, db_session):
        repo = AppSettingsRepository(db_session)
        await repo.set("app-a", "key", "value-a")
        await repo.set("app-b", "key", "value-b")
        await db_session.commit()

        assert await repo.get("app-a", "key") == "value-a"
        assert await repo.get("app-b", "key") == "value-b"


@pytest.mark.asyncio
class TestAppSettingsEndpoints:
    """HTTP endpoint tests for /api/kernel/settings."""

    async def test_get_settings_empty(self, client):
        resp = await client.get("/api/kernel/settings/test-app")
        assert resp.status_code == 200
        data = resp.json()
        assert data["app_id"] == "test-app"
        assert data["settings"] == {}

    async def test_put_and_get_settings(self, client):
        resp = await client.put(
            "/api/kernel/settings/test-app",
            json={"settings": {"color": "blue", "size": 12}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["color"] == "blue"
        assert data["settings"]["size"] == 12

        # Verify via GET
        resp = await client.get("/api/kernel/settings/test-app")
        assert resp.json()["settings"]["color"] == "blue"

    async def test_delete_settings(self, client):
        # First set some settings
        await client.put(
            "/api/kernel/settings/test-app",
            json={"settings": {"a": 1, "b": 2}},
        )

        resp = await client.delete("/api/kernel/settings/test-app")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

        # Verify empty
        resp = await client.get("/api/kernel/settings/test-app")
        assert resp.json()["settings"] == {}
