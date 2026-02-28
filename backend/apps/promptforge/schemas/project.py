"""Pydantic v2 schemas for projects and prompts."""

from pydantic import BaseModel, Field, field_validator

from apps.promptforge.utils.datetime import UTCDatetime


class ProjectCreate(BaseModel):
    """Request body for creating a project."""

    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    description: str | None = Field(None, max_length=2000, description="Project description")
    context_profile: dict | None = Field(None, description="Codebase context profile (JSON)")
    parent_id: str | None = Field(None, description="Parent folder ID (null = root level)")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name must not be empty or whitespace-only")
        return stripped


class ProjectUpdate(BaseModel):
    """Request body for updating a project."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    context_profile: dict | None = Field(
        None,
        description="Codebase context profile (JSON). Null clears.",
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Project name must not be empty or whitespace-only")
            return stripped
        return v


class PromptCreate(BaseModel):
    """Request body for adding a prompt to a project."""

    content: str = Field(..., min_length=1, max_length=10000, description="Prompt content")

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Prompt content must not be empty or whitespace-only")
        return v


class PromptUpdate(BaseModel):
    """Request body for updating a prompt."""

    content: str | None = Field(None, min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Prompt content must not be empty or whitespace-only")
        return v


class ReorderRequest(BaseModel):
    """Request body for reordering prompts within a project."""

    prompt_ids: list[str] = Field(..., min_length=1, description="Ordered list of prompt IDs")


class LatestForgeInfo(BaseModel):
    """Metadata from the most recent completed forge for a prompt."""

    id: str
    title: str | None = None
    task_type: str | None = None
    complexity: str | None = None
    framework_applied: str | None = None
    overall_score: float | None = None
    is_improvement: bool | None = None
    tags: list[str] = []
    version: str | None = None


class PromptResponse(BaseModel):
    """Response for a single prompt."""

    id: str
    content: str
    version: int
    project_id: str | None
    order_index: int
    created_at: UTCDatetime
    updated_at: UTCDatetime
    forge_count: int = 0
    latest_forge: LatestForgeInfo | None = None

    model_config = {"from_attributes": True}


class ProjectSummaryResponse(BaseModel):
    """Summary response for project list views."""

    id: str
    name: str
    description: str | None = None
    status: str
    parent_id: str | None = None
    depth: int = 0
    prompt_count: int = 0
    has_context: bool = False
    created_at: UTCDatetime
    updated_at: UTCDatetime


class ProjectDetailResponse(BaseModel):
    """Full project detail with prompts."""

    id: str
    name: str
    description: str | None = None
    context_profile: dict | None = None
    status: str
    parent_id: str | None = None
    depth: int = 0
    created_at: UTCDatetime
    updated_at: UTCDatetime
    prompts: list[PromptResponse] = []

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Paginated response for project list."""

    items: list[ProjectSummaryResponse]
    total: int
    page: int
    per_page: int


class PromptVersionResponse(BaseModel):
    """Response for a single prompt version snapshot."""

    id: str
    prompt_id: str
    version: int
    content: str
    created_at: UTCDatetime
    optimization_id: str | None = None

    model_config = {"from_attributes": True}


class PromptVersionListResponse(BaseModel):
    """Paginated response for prompt version history."""

    items: list[PromptVersionResponse]
    total: int


class ForgeResultSummary(BaseModel):
    """Lightweight summary of an optimization linked to a prompt."""

    id: str
    created_at: UTCDatetime
    overall_score: float | None = None
    framework_applied: str | None = None
    is_improvement: bool | None = None
    status: str = "pending"
    title: str | None = None
    task_type: str | None = None
    complexity: str | None = None
    tags: list[str] = []
    version: str | None = None


class ForgeResultListResponse(BaseModel):
    """Paginated response for forge results linked to a prompt."""

    items: list[ForgeResultSummary]
    total: int
