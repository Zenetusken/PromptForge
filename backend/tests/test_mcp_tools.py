import pytest

from unittest.mock import AsyncMock, patch, MagicMock
from app.mcp_server import synthesis_prepare_optimization

pytestmark = pytest.mark.asyncio

async def test_prepare_optimization():
    ctx = MagicMock()
    ctx.session.client_params.capabilities.sampling = None

    with patch("app.mcp_server.async_session_factory") as mock_session_factory, \
         patch("app.mcp_server.PreferencesService.get_snapshot"):
             
        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_db
        
        result = await synthesis_prepare_optimization(
            prompt="Hello World",
            strategy="auto",
            ctx=ctx
        )
        
        assert getattr(result, "status", None) == "pending_external"
