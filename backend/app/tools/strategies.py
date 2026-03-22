"""Handler for synthesis_strategies MCP tool.

Copyright 2025-2026 Project Synthesis contributors.
"""

from __future__ import annotations

import logging

from app.config import PROMPTS_DIR
from app.schemas.mcp_models import StrategiesOutput, StrategyInfo
from app.services.strategy_loader import StrategyLoader

logger = logging.getLogger(__name__)


async def handle_strategies() -> StrategiesOutput:
    """List available optimization strategies with metadata."""
    strategy_loader = StrategyLoader(PROMPTS_DIR / "strategies")
    raw_strategies = strategy_loader.list_with_metadata()

    items = []
    for entry in raw_strategies:
        items.append(StrategyInfo(
            name=entry["name"],
            tagline=entry.get("tagline", ""),
            description=entry.get("description", ""),
        ))

    return StrategiesOutput(strategies=items)
