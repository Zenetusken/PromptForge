"""Onboarding analytics router: fire-and-forget event tracking and funnel metrics."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_user
from app.models.onboarding_event import OnboardingEvent
from app.schemas.auth import AuthenticatedUser

router = APIRouter(tags=["onboarding"])


class OnboardingEventRequest(BaseModel):
    """Request body for POST /api/onboarding/events."""

    event_type: str = Field(..., max_length=64)
    metadata: dict | None = Field(default=None)


@router.post("/api/onboarding/events", status_code=201)
async def track_event(
    body: OnboardingEventRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Fire-and-forget event tracking for onboarding funnel analytics."""
    event = OnboardingEvent(
        user_id=current_user.id,
        event_type=body.event_type,
        metadata_=json.dumps(body.metadata) if body.metadata else None,
    )
    session.add(event)
    # Commit handled by get_session context manager
    return {"tracked": True}


class OnboardingFunnelResponse(BaseModel):
    """Aggregated onboarding funnel metrics."""
    total_users: int
    wizard_started: int
    wizard_completed: int
    wizard_skipped: int
    step_counts: dict[str, int]  # e.g. {"wizard_step_1": 45, "wizard_step_2": 38, ...}
    action_breakdown: dict[str, int]  # e.g. {"sample": 12, "write": 8, "github": 5}


@router.get("/api/onboarding/funnel", response_model=OnboardingFunnelResponse)
async def get_onboarding_funnel(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return aggregated onboarding funnel metrics.

    Counts distinct users per event type to measure conversion at each step.
    """
    # Count distinct users per event type
    result = await session.execute(
        select(
            OnboardingEvent.event_type,
            func.count(distinct(OnboardingEvent.user_id)).label("user_count"),
        ).group_by(OnboardingEvent.event_type)
    )
    counts = {row.event_type: row.user_count for row in result}

    # Total users (from User table)
    from app.models.auth import User
    total = await session.execute(select(func.count()).select_from(User))
    total_users = total.scalar() or 0

    # Extract step counts
    step_counts = {k: v for k, v in counts.items() if k.startswith("wizard_step_")}

    # Parse action breakdown from wizard_completed metadata
    action_result = await session.execute(
        select(OnboardingEvent.metadata_)
        .where(OnboardingEvent.event_type == "wizard_completed")
        .where(OnboardingEvent.metadata_.isnot(None))
    )
    action_breakdown: dict[str, int] = {}
    for row in action_result:
        try:
            meta = json.loads(row[0])
            action = meta.get("action", "unknown")
            action_breakdown[action] = action_breakdown.get(action, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "total_users": total_users,
        "wizard_started": counts.get("wizard_started", 0),
        "wizard_completed": counts.get("wizard_completed", 0),
        "wizard_skipped": counts.get("wizard_skipped", 0),
        "step_counts": step_counts,
        "action_breakdown": action_breakdown,
    }
