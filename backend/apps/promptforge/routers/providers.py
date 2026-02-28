"""Provider listing and validation endpoints."""

import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.providers import get_provider, invalidate_detect_cache, list_all_providers
from app.providers.errors import ProviderError

router = APIRouter(tags=["providers"])
logger = logging.getLogger(__name__)

# Simple module-level cache (10 seconds)
_cache: list[dict] = []
_cache_time: float = 0
_CACHE_TTL = 10.0


class ModelInfoSchema(BaseModel):
    """Schema for a single model entry."""

    id: str
    name: str
    description: str
    context_window: int
    tier: str
    capabilities: list[str] = []


class ProviderInfo(BaseModel):
    """Schema for a single provider entry."""

    name: str
    display_name: str
    model: str
    available: bool
    is_default: bool
    requires_api_key: bool = True
    models: list[ModelInfoSchema] = []


class ValidateKeyRequest(BaseModel):
    """Request body for API key validation."""

    provider: str
    api_key: str


class ValidateKeyResponse(BaseModel):
    """Response for API key validation."""

    valid: bool
    error: str | None = None
    provider_name: str | None = None
    model: str | None = None


def _bust_provider_cache() -> None:
    """Clear both the endpoint-level and auto-detect caches."""
    global _cache, _cache_time  # noqa: PLW0603
    _cache = []
    _cache_time = 0
    invalidate_detect_cache()


@router.get("/providers", response_model=list[ProviderInfo])
async def get_providers():
    """List all registered LLM providers with availability status."""
    global _cache, _cache_time  # noqa: PLW0603
    now = time.monotonic()
    if not _cache or now - _cache_time > _CACHE_TTL:
        _cache = list_all_providers()
        _cache_time = now
    return _cache


@router.post("/providers/validate-key", response_model=ValidateKeyResponse)
async def validate_key(request: ValidateKeyRequest):
    """Validate an API key by actually testing provider connectivity.

    Makes a minimal LLM request to verify the key works. On success,
    busts the provider-list cache so the next ``/api/providers`` call
    reflects updated availability.
    """
    try:
        provider = get_provider(request.provider, api_key=request.api_key)
    except (ValueError, RuntimeError, ImportError, ProviderError) as exc:
        return ValidateKeyResponse(valid=False, error=str(exc))
    except Exception:
        logger.debug("Key validation failed for %s", request.provider, exc_info=True)
        return ValidateKeyResponse(valid=False, error="Validation failed")

    ok, error = await provider.test_connection()
    if ok:
        logger.info("API key validated for %s (%s)", request.provider, provider.provider_name)
        _bust_provider_cache()
        return ValidateKeyResponse(
            valid=True,
            provider_name=provider.provider_name,
            model=provider.model_name,
        )
    logger.info("API key validation failed for %s: %s", request.provider, error)
    return ValidateKeyResponse(valid=False, error=error)
