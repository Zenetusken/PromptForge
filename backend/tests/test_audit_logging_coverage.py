"""Tests for the shared audit_log() helper and audit logging coverage."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kernel.models.audit import AuditLog


# ---------------------------------------------------------------------------
# audit_log() helper unit tests (PromptForge thin wrapper → kernel helper)
# ---------------------------------------------------------------------------


class TestAuditLogHelper:
    """Test the shared audit_log() helper in _audit.py."""

    @pytest.mark.asyncio
    async def test_creates_db_entry_and_publishes_event(self, db_engine):
        """Successful call creates a DB row and publishes a bus event."""
        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False,
        )

        with (
            patch("app.database.async_session_factory", session_factory),
            patch("kernel.bus.helpers.publish_event") as mock_publish,
        ):
            from apps.promptforge.routers._audit import audit_log

            await audit_log(
                "create", "project",
                resource_id="proj-123",
                details={"name": "My Project"},
            )

        # Verify DB entry was created
        async with session_factory() as session:
            result = await session.execute(select(AuditLog))
            entries = result.scalars().all()
            assert len(entries) == 1
            entry = entries[0]
            assert entry.app_id == "promptforge"
            assert entry.action == "create"
            assert entry.resource_type == "project"
            assert entry.resource_id == "proj-123"
            details = json.loads(entry.details_json)
            assert details == {"name": "My Project"}

        # Verify bus event was published
        mock_publish.assert_called_once_with(
            "kernel:audit.logged",
            {
                "app_id": "promptforge",
                "action": "create",
                "resource_type": "project",
                "resource_id": "proj-123",
            },
            "kernel",
        )

    @pytest.mark.asyncio
    async def test_no_details_stores_null(self, db_engine):
        """When details is None, details_json is stored as NULL."""
        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False,
        )

        with (
            patch("app.database.async_session_factory", session_factory),
            patch("kernel.bus.helpers.publish_event"),
        ):
            from apps.promptforge.routers._audit import audit_log
            await audit_log("delete", "optimization", resource_id="opt-456")

        async with session_factory() as session:
            result = await session.execute(select(AuditLog))
            entry = result.scalars().first()
            assert entry is not None
            assert entry.details_json is None

    @pytest.mark.asyncio
    async def test_does_not_raise_on_db_error(self):
        """If the DB session fails, audit_log swallows the exception."""
        # Create a factory whose context manager raises on __aenter__
        broken_cm = MagicMock()
        broken_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        broken_cm.__aexit__ = AsyncMock(return_value=False)

        broken_factory = MagicMock(return_value=broken_cm)

        with (
            patch("app.database.async_session_factory", broken_factory),
            patch("kernel.bus.helpers.publish_event") as mock_publish,
        ):
            from apps.promptforge.routers._audit import audit_log

            # Should NOT raise
            await audit_log("delete", "project", resource_id="proj-999")

        # Bus event should not be published on failure (exception caught before it)
        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_resource_id_optional(self, db_engine):
        """resource_id can be omitted (defaults to None)."""
        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False,
        )

        with (
            patch("app.database.async_session_factory", session_factory),
            patch("kernel.bus.helpers.publish_event"),
        ):
            from apps.promptforge.routers._audit import audit_log
            await audit_log("clear_all", "optimization", details={"count": 42})

        async with session_factory() as session:
            result = await session.execute(select(AuditLog))
            entry = result.scalars().first()
            assert entry is not None
            assert entry.resource_id is None
            assert entry.action == "clear_all"
            details = json.loads(entry.details_json)
            assert details == {"count": 42}


# ---------------------------------------------------------------------------
# kernel_audit_log() direct tests
# ---------------------------------------------------------------------------


class TestKernelAuditLog:
    """Test the kernel-level audit helper directly."""

    @pytest.mark.asyncio
    async def test_textforge_app_id(self, db_engine):
        """kernel_audit_log with textforge app_id creates correct DB entry."""
        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False,
        )

        with (
            patch("app.database.async_session_factory", session_factory),
            patch("kernel.bus.helpers.publish_event") as mock_publish,
        ):
            from kernel.bus.helpers import kernel_audit_log

            await kernel_audit_log(
                "textforge", "delete", "transform",
                resource_id="tx-789",
            )

        async with session_factory() as session:
            result = await session.execute(select(AuditLog))
            entry = result.scalars().first()
            assert entry is not None
            assert entry.app_id == "textforge"
            assert entry.action == "delete"
            assert entry.resource_type == "transform"
            assert entry.resource_id == "tx-789"

        mock_publish.assert_called_once_with(
            "kernel:audit.logged",
            {
                "app_id": "textforge",
                "action": "delete",
                "resource_type": "transform",
                "resource_id": "tx-789",
            },
            "kernel",
        )

    @pytest.mark.asyncio
    async def test_does_not_raise_on_error(self):
        """kernel_audit_log swallows exceptions."""
        broken_cm = MagicMock()
        broken_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        broken_cm.__aexit__ = AsyncMock(return_value=False)
        broken_factory = MagicMock(return_value=broken_cm)

        with (
            patch("app.database.async_session_factory", broken_factory),
            patch("kernel.bus.helpers.publish_event") as mock_publish,
        ):
            from kernel.bus.helpers import kernel_audit_log

            # Should NOT raise
            await kernel_audit_log("textforge", "delete", "transform")

        mock_publish.assert_not_called()
