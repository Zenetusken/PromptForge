"""SQLAlchemy ORM models for GitHub connections and workspace links."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GitHubConnection(Base):
    """Stored GitHub OAuth connection with encrypted access token."""

    __tablename__ = "github_connections"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_generate_uuid)
    github_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    github_username: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("github_user_id", name="uq_github_connections_user_id"),
        Index("ix_github_connections_username", "github_username"),
    )

    def __repr__(self) -> str:
        return f"<GitHubConnection(id={self.id!r}, user={self.github_username!r})>"


class WorkspaceLink(Base):
    """Links a PromptForge project to a GitHub repository with auto-detected context."""

    __tablename__ = "workspace_links"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_generate_uuid)
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    github_connection_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("github_connections.id", ondelete="SET NULL"), nullable=True,
    )
    repo_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    sync_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    workspace_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependencies_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_tree_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_source: Mapped[str] = mapped_column(Text, nullable=False, default="github")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_workspace_links_project_id"),
        Index("ix_workspace_links_repo", "repo_full_name"),
        Index("ix_workspace_links_sync_status", "sync_status"),
        Index("ix_workspace_links_github_connection", "github_connection_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkspaceLink(id={self.id!r}, project={self.project_id!r}, "
            f"repo={self.repo_full_name!r}, status={self.sync_status!r})>"
        )


class GitHubOAuthConfig(Base):
    """Stored GitHub OAuth App credentials (single-row, like GitHubConnection).

    The client_secret is Fernet-encrypted at rest. The client_id is stored
    in plaintext (it's public — GitHub shows it in OAuth URLs).
    """

    __tablename__ = "github_oauth_config"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_generate_uuid)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(
        Text, nullable=False, default="http://localhost:8000/api/github/callback",
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="repo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    def __repr__(self) -> str:
        return f"<GitHubOAuthConfig(id={self.id!r}, client_id={self.client_id!r})>"
