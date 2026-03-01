"""TextForge REST API — text transformation endpoints.

Uses kernel services for LLM access and per-app document storage.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.providers.errors import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
)
from app.providers.types import CompletionRequest
from kernel.bus.helpers import publish_event
from kernel.repositories.app_storage import AppStorageRepository

logger = logging.getLogger(__name__)

router = APIRouter()

APP_ID = "textforge"
COLLECTION_NAME = "transforms"

# --- Transform type templates ---

TRANSFORM_SYSTEM_PROMPTS: dict[str, str] = {
    "summarize": "You are an expert summarizer. Provide concise, accurate summaries that preserve key information.",
    "expand": "You are a skilled technical writer. Expand content with clear explanations and relevant examples.",
    "rewrite": "You are a versatile editor. Rewrite text in the requested tone while preserving the original meaning.",
    "simplify": "You are a clarity expert. Simplify text for a general audience using shorter sentences and simpler vocabulary.",
    "translate": "You are a professional translator. Translate text accurately while preserving the original meaning and tone.",
    "extract_keywords": "You are an information extraction specialist. Identify and extract the most important terms and concepts.",
    "fix_grammar": "You are a meticulous proofreader. Fix all grammar, spelling, and punctuation errors while preserving the original style.",
}

TRANSFORM_TEMPLATES: dict[str, str] = {
    "summarize": (
        "Summarize the following text concisely, preserving key points and main ideas. "
        "Output only the summary, no preamble.\n\nText:\n{input}"
    ),
    "expand": (
        "Expand the following text with more detail, examples, and explanations. "
        "Maintain the original tone and style.\n\nText:\n{input}"
    ),
    "rewrite": (
        "Rewrite the following text in a {tone} tone. Preserve the meaning but "
        "change the style and word choice.\n\nText:\n{input}"
    ),
    "simplify": (
        "Simplify the following text so it can be understood by a general audience. "
        "Use shorter sentences and simpler vocabulary.\n\nText:\n{input}"
    ),
    "translate": (
        "Translate the following text to {language}. Maintain the original meaning "
        "and tone as closely as possible.\n\nText:\n{input}"
    ),
    "extract_keywords": (
        "Extract the key terms and concepts from the following text. "
        "Return them as a comma-separated list.\n\nText:\n{input}"
    ),
    "fix_grammar": (
        "Fix any grammar, spelling, and punctuation errors in the following text. "
        "Preserve the original meaning and style. Output only the corrected text.\n\nText:\n{input}"
    ),
}

VALID_TRANSFORMS = list(TRANSFORM_TEMPLATES.keys())


# --- Request/Response schemas ---

class TransformRequest(BaseModel):
    input_text: str = Field(min_length=1)
    transform_type: str = "summarize"
    tone: str = "professional"
    language: str = "English"


class TransformResponse(BaseModel):
    id: str
    transform_type: str
    input_text: str
    output_text: str
    tone: str
    language: str
    created_at: str


class TransformListResponse(BaseModel):
    transforms: list[dict]


# --- Helpers ---

async def _ensure_collection(repo: AppStorageRepository) -> str:
    """Get or create the 'transforms' collection, return its ID."""
    collections = await repo.list_collections(APP_ID)
    for c in collections:
        if c["name"] == COLLECTION_NAME:
            return c["id"]
    created = await repo.create_collection(APP_ID, COLLECTION_NAME)
    return created["id"]


def _build_prompt(transform_type: str, input_text: str, **kwargs: str) -> tuple[str, str]:
    """Build the system prompt and user message from the template.

    Returns (system_prompt, user_message) tuple.
    """
    template = TRANSFORM_TEMPLATES.get(transform_type)
    system = TRANSFORM_SYSTEM_PROMPTS.get(transform_type, "You are a helpful assistant.")
    if not template:
        raise ValueError(f"Unknown transform type: {transform_type}")
    user_message = template.format(input=input_text, **kwargs)
    return system, user_message


# --- Endpoints ---

@router.post("/transform", response_model=TransformResponse)
async def create_transform(
    body: TransformRequest,
    session: AsyncSession = Depends(get_db),
):
    """Run a text transformation using the LLM."""
    if body.transform_type not in VALID_TRANSFORMS:
        raise HTTPException(
            400,
            f"Invalid transform_type. Must be one of: {VALID_TRANSFORMS}",
        )

    # Validate storage is ready before expensive LLM call
    repo = AppStorageRepository(session)
    collection_id = await _ensure_collection(repo)

    # Build prompt
    system_prompt, user_message = _build_prompt(
        body.transform_type,
        body.input_text,
        tone=body.tone,
        language=body.language,
    )

    # Get LLM provider via kernel
    from kernel.registry.app_registry import get_app_registry

    registry = get_app_registry()
    kernel = registry.kernel
    if not kernel or not hasattr(kernel, "get_provider"):
        raise HTTPException(503, "Kernel not available")

    try:
        provider = kernel.get_provider()
        request = CompletionRequest(
            system_prompt=system_prompt,
            user_message=user_message,
        )
        response = await provider.complete(request)
        output_text = response.text
    except RateLimitError:
        raise HTTPException(429, "LLM rate limited, try again later")
    except AuthenticationError:
        raise HTTPException(401, "LLM provider authentication failed")
    except ProviderError as exc:
        logger.error("TextForge LLM provider error: %s", exc)
        raise HTTPException(502, f"LLM provider error: {exc}")
    except Exception as exc:
        logger.error("TextForge LLM call failed: %s", exc)
        raise HTTPException(502, f"LLM error: {exc}")

    if not output_text or not output_text.strip():
        raise HTTPException(502, "LLM returned empty output")

    # Store in kernel document storage
    now = datetime.now(timezone.utc)
    doc_content = json.dumps({
        "transform_type": body.transform_type,
        "input_text": body.input_text,
        "output_text": output_text,
        "tone": body.tone,
        "language": body.language,
    })

    doc = await repo.create_document(
        APP_ID,
        f"transform-{now.strftime('%Y%m%d-%H%M%S')}",
        doc_content,
        collection_id=collection_id,
        content_type="application/json",
        metadata={"transform_type": body.transform_type},
    )

    # Publish transform.completed event
    publish_event("textforge:transform.completed", {
        "transform_id": doc["id"],
        "transform_type": body.transform_type,
        "input_length": len(body.input_text),
        "output_length": len(output_text),
    }, "textforge")

    return TransformResponse(
        id=doc["id"],
        transform_type=body.transform_type,
        input_text=body.input_text,
        output_text=output_text,
        tone=body.tone,
        language=body.language,
        created_at=doc["created_at"],
    )


@router.get("/transforms", response_model=TransformListResponse)
async def list_transforms(session: AsyncSession = Depends(get_db)):
    """List past transformations."""
    repo = AppStorageRepository(session)
    collections = await repo.list_collections(APP_ID)
    collection_id = None
    for c in collections:
        if c["name"] == COLLECTION_NAME:
            collection_id = c["id"]
            break

    if not collection_id:
        return TransformListResponse(transforms=[])

    docs = await repo.list_documents(APP_ID, collection_id=collection_id)
    transforms = []
    for doc in docs:
        try:
            data = json.loads(doc["content"])
            transforms.append({
                "id": doc["id"],
                "transform_type": data.get("transform_type", "unknown"),
                "input_text": data.get("input_text", "")[:200],
                "output_text": data.get("output_text", "")[:200],
                "created_at": doc["created_at"],
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return TransformListResponse(transforms=transforms)


@router.get("/transforms/{transform_id}")
async def get_transform(transform_id: str, session: AsyncSession = Depends(get_db)):
    """Get a specific transformation."""
    repo = AppStorageRepository(session)
    doc = await repo.get_document(APP_ID, transform_id)
    if not doc:
        raise HTTPException(404, "Transform not found")

    try:
        data = json.loads(doc["content"])
    except json.JSONDecodeError:
        raise HTTPException(500, "Corrupt transform data")

    return {
        "id": doc["id"],
        "transform_type": data.get("transform_type", "unknown"),
        "input_text": data.get("input_text", ""),
        "output_text": data.get("output_text", ""),
        "tone": data.get("tone"),
        "language": data.get("language"),
        "created_at": doc["created_at"],
    }


@router.delete("/transforms/{transform_id}")
async def delete_transform(transform_id: str, session: AsyncSession = Depends(get_db)):
    """Delete a transformation."""
    repo = AppStorageRepository(session)
    deleted = await repo.delete_document(APP_ID, transform_id)
    if not deleted:
        raise HTTPException(404, "Transform not found")
    return {"deleted": True}


@router.get("/types")
async def list_transform_types():
    """List available transform types."""
    return {
        "types": [
            {"id": t, "label": t.replace("_", " ").title()}
            for t in VALID_TRANSFORMS
        ]
    }
