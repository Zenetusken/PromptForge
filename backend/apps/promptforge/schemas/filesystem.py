"""Pydantic v2 schemas for filesystem operations."""

from typing import Literal

from pydantic import BaseModel, Field

from apps.promptforge.utils.datetime import UTCDatetime


class PathSegment(BaseModel):
    """A single segment of a breadcrumb path."""

    id: str
    name: str


class FsNode(BaseModel):
    """A filesystem node — either a folder or a prompt."""

    id: str
    name: str
    type: Literal["folder", "prompt"]
    parent_id: str | None = None
    depth: int = 0
    # Folder-specific
    children: list["FsNode"] | None = None
    # Prompt-specific
    content: str | None = None
    version: int | None = None
    forge_count: int | None = None
    latest_forge: dict | None = None
    # Shared
    created_at: UTCDatetime | None = None
    updated_at: UTCDatetime | None = None


class FsChildrenResponse(BaseModel):
    """Response for listing children of a folder."""

    nodes: list[FsNode]
    path: list[PathSegment]


class FsTreeResponse(BaseModel):
    """Response for a recursive tree."""

    nodes: list[FsNode]


class FsPathResponse(BaseModel):
    """Response for breadcrumb path."""

    segments: list[PathSegment]


class MoveRequest(BaseModel):
    """Request body for moving a node."""

    type: Literal["project", "prompt"] = Field(
        ..., description="Type of node to move",
    )
    id: str = Field(..., description="ID of the node to move")
    new_parent_id: str | None = Field(
        None, description="Target folder ID (null = root/desktop)",
    )


class MoveResponse(BaseModel):
    """Response after a successful move."""

    success: bool = True
    node: FsNode
