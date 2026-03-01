"""SQLAlchemy ORM model for project knowledge sources."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(StrEnum):
    DOCUMENT = "document"
    PASTE = "paste"
    API_REFERENCE = "api_reference"
    SPECIFICATION = "specification"
    NOTES = "notes"


MAX_SOURCES_PER_PROJECT = 50
MAX_SOURCE_CONTENT_CHARS = 100_000


class ProjectSource(Base):
    """A named knowledge source document attached to a project.

    Like NotebookLM sources — named reference documents that automatically
    flow through all 4 pipeline stages to ground prompt optimization in
    project-specific knowledge.
    """

    __tablename__ = "project_sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_generate_uuid)
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        Text, nullable=False, default=SourceType.DOCUMENT,
    )
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    project: Mapped["Project"] = relationship(  # noqa: F821
        back_populates="sources", foreign_keys=[project_id],
    )

    __table_args__ = (
        Index("ix_project_sources_project_id", "project_id"),
        Index("ix_project_sources_enabled", "project_id", "enabled"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectSource(id={self.id!r}, project_id={self.project_id!r}, "
            f"title={self.title!r})>"
        )
