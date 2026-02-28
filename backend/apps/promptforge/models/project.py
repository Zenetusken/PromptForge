"""SQLAlchemy ORM models for projects and prompts."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """A named project/folder that groups related prompts and subfolders."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_generate_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    parent_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True,
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )
    workspace_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    children: Mapped[list["Project"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys="Project.parent_id",
    )
    parent: Mapped["Project | None"] = relationship(
        back_populates="children",
        remote_side="Project.id",
        foreign_keys="Project.parent_id",
    )
    prompts: Mapped[list["Prompt"]] = relationship(
        back_populates="project",
        order_by="Prompt.order_index",
        foreign_keys="Prompt.project_id",
    )

    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_projects_name_parent"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_created_at", "created_at"),
        Index("ix_projects_updated_at", "updated_at"),
        Index("ix_projects_parent_id", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id!r}, name={self.name!r}, status={self.status!r})>"


class Prompt(Base):
    """A prompt with versioning and ordering, optionally inside a folder.

    ``project_id`` is nullable — NULL means the prompt lives on the desktop
    (root level) rather than inside a folder.  ON DELETE SET NULL ensures
    desktop prompts survive folder deletion.
    """

    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_generate_uuid)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    project: Mapped["Project | None"] = relationship(
        back_populates="prompts", foreign_keys=[project_id],
    )
    versions: Mapped[list["PromptVersion"]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="PromptVersion.version.desc()",
    )

    __table_args__ = (
        Index("ix_prompts_project_id", "project_id"),
        Index("ix_prompts_order_index", "project_id", "order_index"),
    )

    def __repr__(self) -> str:
        return f"<Prompt(id={self.id!r}, project_id={self.project_id!r}, v{self.version})>"


class PromptVersion(Base):
    """Immutable snapshot of a prompt's content at a prior version.

    Created automatically before each content change so that the previous
    version is preserved.  The *current* version always lives in
    ``prompts.content``; this table only stores superseded versions.
    """

    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_generate_uuid)
    prompt_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    optimization_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("optimizations.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    prompt: Mapped["Prompt"] = relationship(back_populates="versions")

    __table_args__ = (
        Index("ix_prompt_versions_prompt_id", "prompt_id"),
        Index("ix_prompt_versions_prompt_version", "prompt_id", "version"),
    )
