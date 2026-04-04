# backend/app/routers/seed.py
"""Batch seed REST endpoints for UI consumption."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.config import PROMPTS_DIR
from app.schemas.seed import SeedOutput, SeedRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["seed"])


@router.post("/api/seed", response_model=SeedOutput)
async def seed_taxonomy(body: SeedRequest, request: Request) -> SeedOutput:
    """Seed the taxonomy with generated or user-provided prompts.

    Routing is resolved from request.app.state.routing — NOT from
    tools/_shared.get_routing() which is MCP-only.
    """
    try:
        from app.tools.seed import handle_seed
        # REST context: inject routing directly from app.state to bypass
        # the MCP-only _shared.py singleton
        routing = getattr(request.app.state, "routing", None)
        return await handle_seed(
            project_description=body.project_description,
            workspace_path=body.workspace_path,
            repo_full_name=body.repo_full_name,
            prompt_count=body.prompt_count,
            agents=body.agents,
            prompts=body.prompts,
            routing=routing,
        )
    except Exception as exc:
        logger.error("POST /api/seed failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Seed failed: {exc}") from exc


@router.get("/api/seed/agents")
async def list_seed_agents() -> list[dict]:
    """List available seed agents with metadata.

    NOTE: This endpoint is not in the spec but required for the SeedModal
    agent selector in the Phase 4 frontend.
    """
    from app.services.agent_loader import AgentLoader
    loader = AgentLoader(PROMPTS_DIR / "seed-agents")
    return [
        {
            "name": a.name,
            "description": a.description,
            "task_types": a.task_types,
            "prompts_per_run": a.prompts_per_run,
            "enabled": a.enabled,
        }
        for a in loader.list_enabled()
    ]
