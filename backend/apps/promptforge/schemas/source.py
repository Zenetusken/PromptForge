"""Pydantic request/response schemas for project knowledge sources."""

from pydantic import BaseModel, Field

from apps.promptforge.utils.datetime import UTCDatetime


class SourceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=100_000)
    source_type: str = Field("document")


class SourceUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1, max_length=100_000)
    enabled: bool | None = None


class SourceResponse(BaseModel):
    id: str
    project_id: str
    title: str
    content: str
    source_type: str
    char_count: int
    enabled: bool
    order_index: int
    created_at: UTCDatetime
    updated_at: UTCDatetime


class SourceListResponse(BaseModel):
    items: list[SourceResponse]
    total: int
    total_chars: int


class SourceReorderRequest(BaseModel):
    source_ids: list[str] = Field(..., min_length=1)
