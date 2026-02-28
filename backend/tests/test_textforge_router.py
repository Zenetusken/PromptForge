"""Tests for TextForge transform endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.providers.types import CompletionResponse, TokenUsage


@pytest.fixture()
async def tf_client():
    """Client with textforge router manually mounted (since lifespan isn't run in tests)."""
    from fastapi import FastAPI
    from apps.textforge.router import router as tf_router

    test_app = FastAPI()
    test_app.include_router(tf_router, prefix="/api/apps/textforge", tags=["textforge"])

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create kernel tables
        from kernel.database import run_kernel_migrations
        await run_kernel_migrations(conn)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    test_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    test_app.dependency_overrides.clear()
    await engine.dispose()


def _mock_completion_response(text: str) -> CompletionResponse:
    """Create a CompletionResponse matching the real provider API."""
    return CompletionResponse(
        text=text,
        model="test-model",
        provider="test",
        usage=TokenUsage(input_tokens=10, output_tokens=20),
    )


@pytest.mark.asyncio
class TestTextForgeRouter:
    """Tests for /api/apps/textforge/* endpoints."""

    async def test_list_transform_types(self, tf_client):
        resp = await tf_client.get("/api/apps/textforge/types")
        assert resp.status_code == 200
        data = resp.json()
        assert "types" in data
        ids = [t["id"] for t in data["types"]]
        assert "summarize" in ids
        assert "expand" in ids
        assert "rewrite" in ids

    async def test_list_transforms_empty(self, tf_client):
        resp = await tf_client.get("/api/apps/textforge/transforms")
        assert resp.status_code == 200
        assert resp.json()["transforms"] == []

    async def test_transform_invalid_type(self, tf_client):
        resp = await tf_client.post(
            "/api/apps/textforge/transform",
            json={
                "input_text": "test",
                "transform_type": "nonexistent",
            },
        )
        assert resp.status_code == 400

    async def test_transform_empty_input(self, tf_client):
        """Pydantic validation rejects empty input_text."""
        resp = await tf_client.post(
            "/api/apps/textforge/transform",
            json={
                "input_text": "",
                "transform_type": "summarize",
            },
        )
        assert resp.status_code == 422

    async def test_transform_success(self, tf_client):
        """Test transform with a mocked LLM provider."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=_mock_completion_response("This is a summary.")
        )

        mock_kernel = MagicMock()
        mock_kernel.get_provider = MagicMock(return_value=mock_provider)

        from kernel.registry.app_registry import get_app_registry
        registry = get_app_registry()
        original_kernel = getattr(registry, 'kernel', None)

        try:
            registry.kernel = mock_kernel

            resp = await tf_client.post(
                "/api/apps/textforge/transform",
                json={
                    "input_text": "This is a long document about many topics.",
                    "transform_type": "summarize",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["output_text"] == "This is a summary."
            assert data["transform_type"] == "summarize"
            assert data["tone"] == "professional"
            assert data["language"] == "English"
        finally:
            registry.kernel = original_kernel

    async def test_transform_stores_in_history(self, tf_client):
        """Verify transforms appear in the history list."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=_mock_completion_response("Summary output.")
        )

        mock_kernel = MagicMock()
        mock_kernel.get_provider = MagicMock(return_value=mock_provider)

        from kernel.registry.app_registry import get_app_registry
        registry = get_app_registry()
        original_kernel = getattr(registry, 'kernel', None)

        try:
            registry.kernel = mock_kernel

            # Create a transform
            await tf_client.post(
                "/api/apps/textforge/transform",
                json={"input_text": "Test input.", "transform_type": "summarize"},
            )

            # List should include it
            resp = await tf_client.get("/api/apps/textforge/transforms")
            assert resp.status_code == 200
            transforms = resp.json()["transforms"]
            assert len(transforms) >= 1
            assert transforms[0]["transform_type"] == "summarize"
        finally:
            registry.kernel = original_kernel

    async def test_transform_id_roundtrip(self, tf_client):
        """Verify the returned ID can be used to GET/DELETE the transform."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=_mock_completion_response("Roundtrip test output.")
        )

        mock_kernel = MagicMock()
        mock_kernel.get_provider = MagicMock(return_value=mock_provider)

        from kernel.registry.app_registry import get_app_registry
        registry = get_app_registry()
        original_kernel = getattr(registry, 'kernel', None)

        try:
            registry.kernel = mock_kernel

            # Create a transform
            create_resp = await tf_client.post(
                "/api/apps/textforge/transform",
                json={"input_text": "Roundtrip test.", "transform_type": "summarize"},
            )
            assert create_resp.status_code == 200
            doc_id = create_resp.json()["id"]

            # GET by the returned ID should succeed
            get_resp = await tf_client.get(f"/api/apps/textforge/transforms/{doc_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["output_text"] == "Roundtrip test output."

            # DELETE by the returned ID should succeed
            del_resp = await tf_client.delete(f"/api/apps/textforge/transforms/{doc_id}")
            assert del_resp.status_code == 200
            assert del_resp.json()["deleted"] is True

            # Subsequent GET should 404
            get_resp2 = await tf_client.get(f"/api/apps/textforge/transforms/{doc_id}")
            assert get_resp2.status_code == 404
        finally:
            registry.kernel = original_kernel

    async def test_get_nonexistent_transform(self, tf_client):
        resp = await tf_client.get("/api/apps/textforge/transforms/nonexistent")
        assert resp.status_code == 404

    async def test_delete_nonexistent_transform(self, tf_client):
        resp = await tf_client.delete("/api/apps/textforge/transforms/nonexistent")
        assert resp.status_code == 404
