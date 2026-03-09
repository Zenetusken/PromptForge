"""Application settings endpoints.

Provides REST endpoints for reading and updating application-level
settings such as default model, pipeline timeout, and max retries.
Settings are stored in a JSON file to persist across restarts.
"""

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter(tags=["settings"])

SETTINGS_FILE = os.path.join("data", "app_settings.json")

# Default application settings
_DEFAULT_SETTINGS = {
    "default_model": "auto",
    "pipeline_timeout": 120,
    "max_retries": 1,
    "default_strategy": None,
    "auto_validate": True,
    "stream_optimize": True,
}


class SettingsUpdate(BaseModel):
    """Schema for partial settings updates."""

    default_model: Optional[str] = Field(
        None,
        description='Model selection mode: "auto" or a specific model ID',
    )
    pipeline_timeout: Optional[int] = Field(
        None,
        ge=10,
        le=600,
        description="Pipeline timeout in seconds (10-600)",
    )
    max_retries: Optional[int] = Field(
        None,
        ge=0,
        le=5,
        description="Maximum retry attempts for failed stages (0-5)",
    )
    default_strategy: Optional[str] = Field(
        None,
        description="Default optimization strategy framework, or null for auto",
    )
    auto_validate: Optional[bool] = Field(
        None,
        description="Whether to run the validation stage automatically",
    )
    stream_optimize: Optional[bool] = Field(
        None,
        description="Whether to stream the optimize stage output",
    )


def _load_settings() -> dict:
    """Load settings from the JSON file, falling back to defaults.

    Returns:
        Dict of current settings values.
    """
    settings = dict(_DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                stored = json.load(f)
            settings.update(stored)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load settings file: %s", e)
    return settings


def _save_settings(settings: dict) -> None:
    """Persist settings to the JSON file.

    Args:
        settings: Dict of settings values to persist.
    """
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except OSError as e:
        logger.error("Failed to save settings: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")


@router.get("/api/settings")
async def get_settings(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Get current application settings.

    Returns all settings with their current values, including defaults
    for any settings that have not been explicitly configured.

    Returns:
        Dict of all setting key-value pairs.
    """
    return _load_settings()


@router.patch("/api/settings")
async def update_settings(
    update: SettingsUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Update application settings.

    Only the fields included in the request body are updated.
    Other settings remain unchanged.

    Args:
        update: Partial settings update with only the fields to change.

    Returns:
        Dict of all settings after the update.
    """
    current = _load_settings()

    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        return current

    current.update(update_data)
    _save_settings(current)

    logger.info("Settings updated: %s", list(update_data.keys()))
    return current
