"""Centralized database access for GitHub connections and workspace links."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from apps.promptforge.models.project import Project
from apps.promptforge.models.workspace import GitHubConnection, GitHubOAuthConfig, WorkspaceLink
from apps.promptforge.schemas.context import CodebaseContext, context_from_json

logger = logging.getLogger(__name__)

# Workspace auto-context older than 24h is considered stale
STALENESS_HOURS = 24


class WorkspaceRepository:
    """Database operations for GitHub connections and workspace links."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # --- GitHub Connections ---

    async def get_connection(self) -> GitHubConnection | None:
        """Get the current GitHub connection (single-user system)."""
        result = await self._session.execute(
            select(GitHubConnection).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_connection_by_id(self, connection_id: str) -> GitHubConnection | None:
        """Get a specific GitHub connection by ID."""
        result = await self._session.execute(
            select(GitHubConnection).where(GitHubConnection.id == connection_id)
        )
        return result.scalar_one_or_none()

    async def upsert_connection(
        self,
        github_user_id: str,
        github_username: str,
        access_token_encrypted: str,
        avatar_url: str | None = None,
        scopes: str | None = None,
    ) -> GitHubConnection:
        """Create or update a GitHub connection (upsert by github_user_id)."""
        result = await self._session.execute(
            select(GitHubConnection).where(
                GitHubConnection.github_user_id == github_user_id
            )
        )
        conn = result.scalar_one_or_none()

        if conn:
            conn.github_username = github_username
            conn.access_token_encrypted = access_token_encrypted
            conn.avatar_url = avatar_url
            conn.scopes = scopes
            conn.token_valid = True
            conn.updated_at = datetime.now(timezone.utc)
        else:
            conn = GitHubConnection(
                github_user_id=github_user_id,
                github_username=github_username,
                access_token_encrypted=access_token_encrypted,
                avatar_url=avatar_url,
                scopes=scopes,
            )
            self._session.add(conn)

        await self._session.flush()
        return conn

    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a GitHub connection and nullify related workspace links."""
        conn = await self.get_connection_by_id(connection_id)
        if not conn:
            return False
        await self._session.delete(conn)
        await self._session.flush()
        return True

    async def mark_token_invalid(self, connection_id: str) -> None:
        """Mark a connection's token as invalid (401 from GitHub)."""
        conn = await self.get_connection_by_id(connection_id)
        if conn:
            conn.token_valid = False
            conn.updated_at = datetime.now(timezone.utc)
            await self._session.flush()

    # --- OAuth Config ---

    async def get_oauth_config(self) -> GitHubOAuthConfig | None:
        """Get the stored GitHub OAuth config (single-row table)."""
        result = await self._session.execute(
            select(GitHubOAuthConfig).limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_oauth_config(
        self,
        client_id: str,
        client_secret_encrypted: str,
        redirect_uri: str = "http://localhost:8000/api/apps/promptforge/github/callback",
        scope: str = "repo",
    ) -> GitHubOAuthConfig:
        """Create or update the GitHub OAuth config (single-row upsert)."""
        result = await self._session.execute(
            select(GitHubOAuthConfig).limit(1)
        )
        cfg = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if cfg:
            cfg.client_id = client_id
            cfg.client_secret_encrypted = client_secret_encrypted
            cfg.redirect_uri = redirect_uri
            cfg.scope = scope
            cfg.updated_at = now
        else:
            cfg = GitHubOAuthConfig(
                client_id=client_id,
                client_secret_encrypted=client_secret_encrypted,
                redirect_uri=redirect_uri,
                scope=scope,
            )
            self._session.add(cfg)

        await self._session.flush()
        return cfg

    async def delete_oauth_config(self) -> bool:
        """Delete the stored GitHub OAuth config."""
        cfg = await self.get_oauth_config()
        if not cfg:
            return False
        await self._session.delete(cfg)
        await self._session.flush()
        return True

    # --- Workspace Links ---

    async def get_link_by_id(self, link_id: str) -> WorkspaceLink | None:
        """Get a workspace link by ID."""
        result = await self._session.execute(
            select(WorkspaceLink).where(WorkspaceLink.id == link_id)
        )
        return result.scalar_one_or_none()

    async def get_link_by_project_id(self, project_id: str) -> WorkspaceLink | None:
        """Get the workspace link for a project (one link per project)."""
        result = await self._session.execute(
            select(WorkspaceLink).where(WorkspaceLink.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_link_by_project_name(self, name: str) -> WorkspaceLink | None:
        """Get workspace link by project name (joins through projects table).

        Uses most-recently-synced link when duplicate project names exist.
        """
        result = await self._session.execute(
            select(WorkspaceLink)
            .join(Project, WorkspaceLink.project_id == Project.id)
            .where(Project.name == name, Project.status != "deleted")
            .order_by(WorkspaceLink.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_links(self) -> list[WorkspaceLink]:
        """List all workspace links."""
        result = await self._session.execute(
            select(WorkspaceLink).order_by(WorkspaceLink.updated_at.desc())
        )
        return list(result.scalars().all())

    async def create_link(
        self,
        project_id: str,
        repo_full_name: str,
        repo_url: str,
        default_branch: str = "main",
        github_connection_id: str | None = None,
        sync_source: str = "github",
    ) -> WorkspaceLink:
        """Create a workspace link for a project."""
        link = WorkspaceLink(
            project_id=project_id,
            github_connection_id=github_connection_id,
            repo_full_name=repo_full_name,
            repo_url=repo_url,
            default_branch=default_branch,
            sync_source=sync_source,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def delete_link(self, link_id: str) -> bool:
        """Delete a workspace link."""
        link = await self.get_link_by_id(link_id)
        if not link:
            return False
        await self._session.delete(link)
        await self._session.flush()
        return True

    async def update_sync_status(
        self,
        link: WorkspaceLink,
        status: str,
        *,
        workspace_context: dict | None = None,
        dependencies_snapshot: dict | None = None,
        file_tree_snapshot: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        """Update sync status and optionally store extracted context."""
        link.sync_status = status
        link.sync_error = error
        link.updated_at = datetime.now(timezone.utc)

        if status == "synced":
            link.last_synced_at = datetime.now(timezone.utc)
            if workspace_context is not None:
                link.workspace_context = json.dumps(workspace_context)
            if dependencies_snapshot is not None:
                link.dependencies_snapshot = json.dumps(dependencies_snapshot)
            if file_tree_snapshot is not None:
                link.file_tree_snapshot = json.dumps(file_tree_snapshot)

            # Update project.workspace_synced_at
            result = await self._session.execute(
                select(Project).where(Project.id == link.project_id)
            )
            project = result.scalar_one_or_none()
            if project:
                project.workspace_synced_at = link.last_synced_at

        await self._session.flush()

    # --- Context Resolution ---

    async def get_workspace_context_by_project_name(
        self, name: str,
    ) -> CodebaseContext | None:
        """Fetch workspace auto-context for a project by name.

        Returns None if no workspace link exists or context hasn't been synced.
        """
        link = await self.get_link_by_project_name(name)
        if not link or not link.workspace_context:
            return None
        return context_from_json(link.workspace_context)

    async def get_workspace_context_by_project_id(
        self, project_id: str,
    ) -> CodebaseContext | None:
        """Fetch workspace auto-context for a project by ID."""
        link = await self.get_link_by_project_id(project_id)
        if not link or not link.workspace_context:
            return None
        return context_from_json(link.workspace_context)

    # --- Health & Status ---

    @staticmethod
    def _naive_utc(dt: datetime | None) -> datetime | None:
        """Normalize datetime to naive UTC for comparison (SQLite strips tzinfo)."""
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    async def get_health_summary(self) -> dict:
        """Get workspace health summary for the health endpoint."""
        conn = await self.get_connection()
        links = await self.list_links()

        now = self._naive_utc(datetime.now(timezone.utc))
        stale_threshold = now - timedelta(hours=STALENESS_HOURS)

        synced = 0
        stale = 0
        errors = 0
        for link in links:
            if link.sync_status == "error":
                errors += 1
            elif link.sync_status == "synced":
                synced_at = self._naive_utc(link.last_synced_at)
                if synced_at and synced_at < stale_threshold:
                    stale += 1
                else:
                    synced += 1

        # Check if GitHub OAuth is configured (DB first, then env)
        github_configured = False
        try:
            oauth_cfg = await self.get_oauth_config()
            if oauth_cfg:
                github_configured = True
        except Exception:
            pass
        if not github_configured:
            github_configured = bool(
                config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET
            )

        return {
            "github_configured": github_configured,
            "github_connected": bool(conn and conn.token_valid),
            "github_username": conn.github_username if conn else None,
            "total_links": len(links),
            "synced": synced,
            "stale": stale,
            "errors": errors,
        }

    async def get_all_workspace_statuses(self) -> list[dict]:
        """Get status info for all workspace links (for MCP resource)."""
        result = await self._session.execute(
            select(WorkspaceLink, Project.name)
            .join(Project, WorkspaceLink.project_id == Project.id)
            .where(Project.status != "deleted")
            .order_by(WorkspaceLink.updated_at.desc())
        )
        rows = result.all()

        now = self._naive_utc(datetime.now(timezone.utc))
        stale_threshold = now - timedelta(hours=STALENESS_HOURS)

        statuses = []
        for link, project_name in rows:
            synced_at = self._naive_utc(link.last_synced_at)
            is_stale = (
                link.sync_status == "synced"
                and synced_at
                and synced_at < stale_threshold
            )

            # Calculate context completeness (all 9 CodebaseContext fields)
            completeness = 0.0
            if link.workspace_context:
                ctx = context_from_json(link.workspace_context)
                if ctx:
                    fields = [
                        ctx.language, ctx.framework, ctx.description,
                        ctx.conventions, ctx.patterns, ctx.code_snippets,
                        ctx.documentation, ctx.test_framework,
                        ctx.test_patterns,
                    ]
                    filled = sum(1 for f in fields if f)
                    completeness = round(filled / len(fields), 2)

            statuses.append({
                "id": link.id,
                "project": project_name,
                "project_id": link.project_id,
                "repo": link.repo_full_name,
                "repo_url": link.repo_url,
                "branch": link.default_branch,
                "synced_at": link.last_synced_at.isoformat() if link.last_synced_at else None,
                "stale": is_stale,
                "sync_status": link.sync_status,
                "sync_error": link.sync_error,
                "sync_source": link.sync_source,
                "context_completeness": completeness,
            })

        return statuses
