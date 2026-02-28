"""Tests for GitHub OAuth and workspace management endpoints."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.models.project import Project
from apps.promptforge.models.workspace import GitHubConnection, WorkspaceLink
from apps.promptforge.repositories.workspace import STALENESS_HOURS, WorkspaceRepository
from apps.promptforge.services.github import (
    _oauth_states,
    create_oauth_state,
    decrypt_token,
    encrypt_token,
    validate_oauth_state,
)

# --- Helpers ---

def _utcnow():
    return datetime.now(timezone.utc)


async def _seed_project(session: AsyncSession, name: str = "TestProject") -> Project:
    project = Project(name=name, description="Test", status="active",
                      created_at=_utcnow(), updated_at=_utcnow())
    session.add(project)
    await session.flush()
    return project


async def _seed_connection(session: AsyncSession) -> GitHubConnection:
    conn = GitHubConnection(
        github_user_id="12345",
        github_username="testuser",
        access_token_encrypted=encrypt_token("ghp_test_token_123"),
        avatar_url="https://avatars.githubusercontent.com/u/12345",
        scopes="repo",
        token_valid=True,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(conn)
    await session.flush()
    return conn


async def _seed_workspace_link(
    session: AsyncSession, project_id: str, conn_id: str | None = None,
) -> WorkspaceLink:
    link = WorkspaceLink(
        project_id=project_id,
        github_connection_id=conn_id,
        repo_full_name="testuser/testrepo",
        repo_url="https://github.com/testuser/testrepo",
        default_branch="main",
        sync_status="synced",
        sync_source="github",
        last_synced_at=_utcnow(),
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(link)
    await session.flush()
    return link


# --- Encryption Tests ---

class TestFernetEncryption:
    def test_round_trip(self):
        """Encrypt → decrypt returns original token."""
        token = "ghp_1234567890abcdef"
        encrypted = encrypt_token(token)
        assert encrypted != token
        assert decrypt_token(encrypted) == token

    def test_decrypt_invalid(self):
        """Invalid ciphertext returns None."""
        assert decrypt_token("not_valid_ciphertext") is None


# --- Repository Tests ---

class TestWorkspaceRepository:
    @pytest.mark.asyncio
    async def test_upsert_connection_create(self, db_session):
        """Create new connection via upsert."""
        repo = WorkspaceRepository(db_session)
        conn = await repo.upsert_connection(
            github_user_id="99",
            github_username="newuser",
            access_token_encrypted=encrypt_token("tok"),
        )
        assert conn.github_username == "newuser"
        assert conn.token_valid is True

    @pytest.mark.asyncio
    async def test_upsert_connection_update(self, db_session):
        """Update existing connection via upsert."""
        await _seed_connection(db_session)
        repo = WorkspaceRepository(db_session)
        conn = await repo.upsert_connection(
            github_user_id="12345",  # same user ID
            github_username="updated_user",
            access_token_encrypted=encrypt_token("new_tok"),
        )
        assert conn.github_username == "updated_user"

    @pytest.mark.asyncio
    async def test_get_connection(self, db_session):
        """Fetch the single GitHub connection."""
        await _seed_connection(db_session)
        repo = WorkspaceRepository(db_session)
        conn = await repo.get_connection()
        assert conn is not None
        assert conn.github_username == "testuser"

    @pytest.mark.asyncio
    async def test_create_and_get_link(self, db_session):
        """Create workspace link and retrieve by project ID."""
        project = await _seed_project(db_session)
        conn = await _seed_connection(db_session)
        repo = WorkspaceRepository(db_session)

        link = await repo.create_link(
            project_id=project.id,
            repo_full_name="owner/repo",
            repo_url="https://github.com/owner/repo",
            github_connection_id=conn.id,
        )
        assert link.sync_status == "pending"

        fetched = await repo.get_link_by_project_id(project.id)
        assert fetched is not None
        assert fetched.id == link.id

    @pytest.mark.asyncio
    async def test_update_sync_status(self, db_session):
        """Update sync status stores context and timestamps."""
        project = await _seed_project(db_session)
        repo = WorkspaceRepository(db_session)
        link = await repo.create_link(
            project_id=project.id,
            repo_full_name="o/r",
            repo_url="https://github.com/o/r",
        )

        await repo.update_sync_status(
            link, "synced",
            workspace_context={"language": "Python", "framework": "FastAPI"},
            file_tree_snapshot=["app/main.py"],
        )
        assert link.sync_status == "synced"
        assert link.last_synced_at is not None
        assert json.loads(link.workspace_context)["language"] == "Python"

    @pytest.mark.asyncio
    async def test_get_workspace_context_by_project_name(self, db_session):
        """Fetch auto-context by project name."""
        project = await _seed_project(db_session, "MyProject")
        repo = WorkspaceRepository(db_session)
        link = await repo.create_link(
            project_id=project.id,
            repo_full_name="o/r",
            repo_url="https://github.com/o/r",
        )
        await repo.update_sync_status(
            link, "synced",
            workspace_context={"language": "Go", "framework": "Gin"},
        )
        await db_session.commit()

        ctx = await repo.get_workspace_context_by_project_name("MyProject")
        assert ctx is not None
        assert ctx.language == "Go"
        assert ctx.framework == "Gin"

    @pytest.mark.asyncio
    async def test_get_workspace_context_no_link(self, db_session):
        """No workspace link returns None."""
        repo = WorkspaceRepository(db_session)
        ctx = await repo.get_workspace_context_by_project_name("Nonexistent")
        assert ctx is None

    @pytest.mark.asyncio
    async def test_delete_link(self, db_session):
        """Delete workspace link."""
        project = await _seed_project(db_session)
        repo = WorkspaceRepository(db_session)
        link = await repo.create_link(
            project_id=project.id,
            repo_full_name="o/r",
            repo_url="https://github.com/o/r",
        )
        assert await repo.delete_link(link.id) is True
        assert await repo.get_link_by_id(link.id) is None

    @pytest.mark.asyncio
    async def test_health_summary(self, db_session):
        """Health summary reports correct counts."""
        conn = await _seed_connection(db_session)
        project = await _seed_project(db_session)
        repo = WorkspaceRepository(db_session)
        link = await repo.create_link(
            project_id=project.id,
            repo_full_name="o/r",
            repo_url="https://github.com/o/r",
            github_connection_id=conn.id,
        )
        await repo.update_sync_status(link, "synced")

        summary = await repo.get_health_summary()
        assert summary["github_connected"] is True
        assert summary["github_username"] == "testuser"
        assert summary["total_links"] == 1
        assert summary["synced"] == 1
        assert summary["errors"] == 0


# --- Router Tests ---

class TestGitHubStatusEndpoint:
    @pytest.mark.asyncio
    async def test_no_connection(self, client):
        """Returns disconnected when no GitHub connection exists."""
        resp = await client.get("/api/apps/promptforge/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False


class TestWorkspaceStatusEndpoint:
    @pytest.mark.asyncio
    async def test_empty_status(self, client):
        """Returns empty list when no workspace links exist."""
        resp = await client.get("/api/apps/promptforge/workspace/status")
        assert resp.status_code == 200
        assert resp.json() == []


class TestHealthEndpointWorkspace:
    @pytest.mark.asyncio
    async def test_health_includes_workspace(self, client):
        """Health endpoint includes workspace section."""
        resp = await client.get("/api/apps/promptforge/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "workspace" in data
        ws = data["workspace"]
        assert "github_connected" in ws
        assert "total_links" in ws
        assert "synced" in ws
        assert "stale" in ws
        assert "errors" in ws


# --- OAuth Endpoint Tests ---

class TestGitHubAuthorizeEndpoint:
    @pytest.mark.asyncio
    async def test_authorize_no_config(self, client):
        """Returns 501 when GitHub OAuth is not configured."""
        with (
            patch("apps.promptforge.services.github.config.GITHUB_CLIENT_ID", ""),
            patch("apps.promptforge.services.github.config.GITHUB_CLIENT_SECRET", ""),
        ):
            resp = await client.get("/api/apps/promptforge/github/authorize")
            assert resp.status_code == 501

    @pytest.mark.asyncio
    async def test_authorize_returns_url(self, client):
        """Returns authorization URL when configured via env vars."""
        with (
            patch("apps.promptforge.services.github.config.GITHUB_CLIENT_ID", "test_client_id"),
            patch("apps.promptforge.services.github.config.GITHUB_CLIENT_SECRET", "test_secret"),
            patch("apps.promptforge.services.github.config.GITHUB_REDIRECT_URI", "http://localhost:8000/api/apps/promptforge/github/callback"),
            patch("apps.promptforge.services.github.config.GITHUB_SCOPE", "repo"),
        ):
            resp = await client.get("/api/apps/promptforge/github/authorize")
            assert resp.status_code == 200
            data = resp.json()
            assert "url" in data
            assert "state" in data
            assert "test_client_id" in data["url"]


class TestGitHubDisconnectEndpoint:
    @pytest.mark.asyncio
    async def test_disconnect_no_connection(self, client):
        """Returns 404 when no connection exists."""
        resp = await client.delete("/api/apps/promptforge/github/disconnect")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_disconnect_success(self, client, db_session):
        """Disconnects and removes connection."""
        await _seed_connection(db_session)
        await db_session.commit()

        with patch("apps.promptforge.routers.github.revoke_token", new_callable=AsyncMock, return_value=True):
            resp = await client.delete("/api/apps/promptforge/github/disconnect")
        assert resp.status_code == 200
        assert resp.json()["status"] == "disconnected"

        # Verify connection is deleted
        check = await client.get("/api/apps/promptforge/github/status")
        assert check.json()["connected"] is False


class TestGitHubReposEndpoint:
    @pytest.mark.asyncio
    async def test_repos_no_connection(self, client):
        """Returns 401 when no GitHub connection exists."""
        resp = await client.get("/api/apps/promptforge/github/repos")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_repos_invalid_token(self, client, db_session):
        """Returns 401 when connection has invalid token."""
        conn = await _seed_connection(db_session)
        conn.token_valid = False
        await db_session.commit()

        resp = await client.get("/api/apps/promptforge/github/repos")
        assert resp.status_code == 401


# --- Workspace Link Endpoint Tests ---

class TestLinkRepoEndpoint:
    @pytest.mark.asyncio
    async def test_link_no_connection(self, client, db_session):
        """Returns 401 when no GitHub connection exists."""
        project = await _seed_project(db_session)
        await db_session.commit()

        resp = await client.post("/api/apps/promptforge/workspace/link", json={
            "project_id": project.id,
            "repo_full_name": "owner/repo",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_link_invalid_repo_format(self, client, db_session):
        """Returns 400 for invalid repo_full_name format."""
        project = await _seed_project(db_session)
        _conn = await _seed_connection(db_session)
        await db_session.commit()

        resp = await client.post("/api/apps/promptforge/workspace/link", json={
            "project_id": project.id,
            "repo_full_name": "invalid-no-slash",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_link_duplicate(self, client, db_session):
        """Returns 409 when project already has a workspace link."""
        project = await _seed_project(db_session)
        conn = await _seed_connection(db_session)
        await _seed_workspace_link(db_session, project.id, conn.id)
        await db_session.commit()

        resp = await client.post("/api/apps/promptforge/workspace/link", json={
            "project_id": project.id,
            "repo_full_name": "owner/repo2",
        })
        assert resp.status_code == 409


class TestUnlinkWorkspaceEndpoint:
    @pytest.mark.asyncio
    async def test_unlink_not_found(self, client):
        """Returns 404 for non-existent link ID."""
        resp = await client.delete("/api/apps/promptforge/workspace/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unlink_success(self, client, db_session):
        """Successfully unlinks a workspace."""
        project = await _seed_project(db_session)
        conn = await _seed_connection(db_session)
        link = await _seed_workspace_link(db_session, project.id, conn.id)
        await db_session.commit()

        resp = await client.delete(f"/api/apps/promptforge/workspace/{link.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unlinked"


class TestSyncWorkspaceEndpoint:
    @pytest.mark.asyncio
    async def test_sync_not_found(self, client):
        """Returns 404 for non-existent link ID."""
        resp = await client.post("/api/apps/promptforge/workspace/nonexistent-id/sync")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_no_connection(self, client, db_session):
        """Returns 401 when no valid GitHub connection for sync."""
        project = await _seed_project(db_session)
        link = await _seed_workspace_link(db_session, project.id)
        await db_session.commit()

        resp = await client.post(f"/api/apps/promptforge/workspace/{link.id}/sync")
        assert resp.status_code == 401


class TestWorkspaceStatusResponse:
    @pytest.mark.asyncio
    async def test_status_includes_link_id(self, client, db_session):
        """Workspace status response includes the link id field."""
        project = await _seed_project(db_session)
        conn = await _seed_connection(db_session)
        link = await _seed_workspace_link(db_session, project.id, conn.id)
        await db_session.commit()

        resp = await client.get("/api/apps/promptforge/workspace/status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == link.id
        assert data[0]["project_id"] == project.id
        assert data[0]["repo"] == "testuser/testrepo"
        assert data[0]["sync_status"] == "synced"
        assert "context_completeness" in data[0]

    @pytest.mark.asyncio
    async def test_status_staleness_detection(self, db_session):
        """Workspace with old sync time is marked stale."""
        project = await _seed_project(db_session)
        conn = await _seed_connection(db_session)
        repo = WorkspaceRepository(db_session)
        link = await repo.create_link(
            project_id=project.id,
            repo_full_name="o/r",
            repo_url="https://github.com/o/r",
            github_connection_id=conn.id,
        )
        # Set last_synced_at to 25 hours ago (past staleness threshold)
        # Use naive UTC to match SQLite behavior
        link.sync_status = "synced"
        link.last_synced_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(hours=STALENESS_HOURS + 1)
        )
        await db_session.flush()

        statuses = await repo.get_all_workspace_statuses()
        assert len(statuses) == 1
        assert statuses[0]["stale"] is True

    @pytest.mark.asyncio
    async def test_status_error_count(self, db_session):
        """Health summary reports error count correctly."""
        conn = await _seed_connection(db_session)
        project = await _seed_project(db_session)
        repo = WorkspaceRepository(db_session)
        link = await repo.create_link(
            project_id=project.id,
            repo_full_name="o/r",
            repo_url="https://github.com/o/r",
            github_connection_id=conn.id,
        )
        await repo.update_sync_status(link, "error", error="API rate limit exceeded")

        summary = await repo.get_health_summary()
        assert summary["errors"] == 1
        assert summary["synced"] == 0


# --- OAuth CSRF State Validation Tests ---

class TestOAuthStateValidation:
    def test_create_state(self):
        """create_oauth_state returns a non-empty string."""
        state = create_oauth_state()
        assert isinstance(state, str)
        assert len(state) > 10

    def test_validate_valid_state(self):
        """Valid state token passes validation."""
        state = create_oauth_state()
        assert validate_oauth_state(state) is True

    def test_validate_consumed_state(self):
        """State token is consumed after first validation (one-time use)."""
        state = create_oauth_state()
        assert validate_oauth_state(state) is True
        assert validate_oauth_state(state) is False

    def test_validate_unknown_state(self):
        """Unknown state token fails validation."""
        assert validate_oauth_state("unknown_state_token") is False

    def test_validate_empty_state(self):
        """Empty state token fails validation."""
        assert validate_oauth_state("") is False

    def test_validate_expired_state(self):
        """Expired state token fails validation."""
        import time
        state = create_oauth_state()
        # Manually expire it
        _oauth_states[state] = time.time() - 10
        assert validate_oauth_state(state) is False


# --- OAuth Config Repository Tests ---

class TestOAuthConfigRepository:
    @pytest.mark.asyncio
    async def test_get_config_empty(self, db_session):
        """No config returns None."""
        repo = WorkspaceRepository(db_session)
        cfg = await repo.get_oauth_config()
        assert cfg is None

    @pytest.mark.asyncio
    async def test_upsert_config_create(self, db_session):
        """Create new config via upsert."""
        repo = WorkspaceRepository(db_session)
        cfg = await repo.upsert_oauth_config(
            client_id="Iv1.test123",
            client_secret_encrypted=encrypt_token("secret_value"),
        )
        assert cfg.client_id == "Iv1.test123"
        assert cfg.redirect_uri == "http://localhost:8000/api/apps/promptforge/github/callback"
        assert cfg.scope == "repo"

    @pytest.mark.asyncio
    async def test_upsert_config_update(self, db_session):
        """Update existing config via upsert."""
        repo = WorkspaceRepository(db_session)
        await repo.upsert_oauth_config(
            client_id="old_id",
            client_secret_encrypted=encrypt_token("old_secret"),
        )
        await repo.upsert_oauth_config(
            client_id="new_id",
            client_secret_encrypted=encrypt_token("new_secret"),
        )
        cfg = await repo.get_oauth_config()
        assert cfg is not None
        assert cfg.client_id == "new_id"

    @pytest.mark.asyncio
    async def test_delete_config(self, db_session):
        """Delete stored config."""
        repo = WorkspaceRepository(db_session)
        await repo.upsert_oauth_config(
            client_id="test",
            client_secret_encrypted=encrypt_token("secret"),
        )
        assert await repo.delete_oauth_config() is True
        assert await repo.get_oauth_config() is None

    @pytest.mark.asyncio
    async def test_delete_config_not_found(self, db_session):
        """Delete when no config exists returns False."""
        repo = WorkspaceRepository(db_session)
        assert await repo.delete_oauth_config() is False


# --- Config Endpoint Tests ---

class TestGitHubConfigEndpoints:
    @pytest.mark.asyncio
    async def test_get_config_unconfigured(self, client):
        """Returns not configured when no config exists."""
        with patch("apps.promptforge.routers.github.config") as mock_cfg:
            mock_cfg.GITHUB_CLIENT_ID = ""
            mock_cfg.GITHUB_CLIENT_SECRET = ""
            resp = await client.get("/api/apps/promptforge/github/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["client_id_hint"] == ""

    @pytest.mark.asyncio
    async def test_save_config(self, client):
        """Save config returns configured: true."""
        resp = await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.abc123",
            "client_secret": "secret_value_12345",
        })
        assert resp.status_code == 200
        assert resp.json()["configured"] is True

    @pytest.mark.asyncio
    async def test_get_config_after_save(self, client):
        """Config is returned after save with masked hint."""
        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.abc123def456",
            "client_secret": "secret_value",
        })
        resp = await client.get("/api/apps/promptforge/github/config")
        data = resp.json()
        assert data["configured"] is True
        assert data["source"] == "database"
        # Hint: first 4 + **** + last 4
        assert data["client_id_hint"] == "Iv1.****f456"
        # Secret is never returned
        assert "client_secret" not in data

    @pytest.mark.asyncio
    async def test_save_config_empty_client_id(self, client):
        """Rejects empty client_id."""
        resp = await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "  ",
            "client_secret": "secret",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_save_config_invalid_chars(self, client):
        """Rejects client_id with invalid characters."""
        resp = await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "invalid id with spaces!",
            "client_secret": "secret",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_save_config_empty_secret(self, client):
        """Rejects empty client_secret."""
        resp = await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.test",
            "client_secret": "",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_config(self, client):
        """Delete config removes stored credentials."""
        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.test",
            "client_secret": "secret",
        })
        resp = await client.delete("/api/apps/promptforge/github/config")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_config_not_found(self, client):
        """Delete when no config exists returns 404."""
        resp = await client.delete("/api/apps/promptforge/github/config")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_config_then_get_returns_unconfigured(self, client):
        """After delete, GET shows configured: false (env vars empty)."""
        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.test",
            "client_secret": "secret",
        })
        await client.delete("/api/apps/promptforge/github/config")
        with (
            patch("apps.promptforge.routers.github.config.GITHUB_CLIENT_ID", ""),
            patch("apps.promptforge.routers.github.config.GITHUB_CLIENT_SECRET", ""),
        ):
            resp = await client.get("/api/apps/promptforge/github/config")
        data = resp.json()
        assert data["configured"] is False
        assert data["client_id_hint"] == ""

    @pytest.mark.asyncio
    async def test_delete_config_twice_returns_404(self, client):
        """Double delete is safe — second delete returns 404."""
        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.test",
            "client_secret": "secret",
        })
        resp1 = await client.delete("/api/apps/promptforge/github/config")
        assert resp1.status_code == 200
        resp2 = await client.delete("/api/apps/promptforge/github/config")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_env_only_config_returns_404(self, client):
        """Env-var-only credentials are not deletable via API — 404."""
        with (
            patch("apps.promptforge.routers.github.config.GITHUB_CLIENT_ID", "env_id"),
            patch("apps.promptforge.routers.github.config.GITHUB_CLIENT_SECRET", "env_secret"),
        ):
            resp = await client.delete("/api/apps/promptforge/github/config")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_config_then_authorize_returns_501(self, client):
        """After removing DB config + no env vars, authorize fails with 501."""
        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.test",
            "client_secret": "secret",
        })
        await client.delete("/api/apps/promptforge/github/config")
        with (
            patch("apps.promptforge.services.github.config.GITHUB_CLIENT_ID", ""),
            patch("apps.promptforge.services.github.config.GITHUB_CLIENT_SECRET", ""),
        ):
            resp = await client.get("/api/apps/promptforge/github/authorize")
        assert resp.status_code == 501

    @pytest.mark.asyncio
    async def test_delete_config_does_not_cascade_to_connection(self, client, db_session):
        """Deleting OAuth config does NOT delete the active GitHub connection."""
        await _seed_connection(db_session)
        await db_session.commit()

        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.test",
            "client_secret": "secret",
        })
        resp = await client.delete("/api/apps/promptforge/github/config")
        assert resp.status_code == 200

        status = await client.get("/api/apps/promptforge/github/status")
        assert status.json()["connected"] is True

    @pytest.mark.asyncio
    async def test_delete_config_health_reflects_change(self, client):
        """After delete (no env vars), health shows github_configured: false."""
        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.test",
            "client_secret": "secret",
        })
        await client.delete("/api/apps/promptforge/github/config")
        with (
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_ID", ""),
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_SECRET", ""),
        ):
            resp = await client.get("/api/apps/promptforge/health")
        assert resp.json()["workspace"]["github_configured"] is False

    @pytest.mark.asyncio
    async def test_save_after_delete_works(self, client):
        """Can re-save credentials after deleting them (full lifecycle)."""
        await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.first",
            "client_secret": "secret1",
        })
        await client.delete("/api/apps/promptforge/github/config")
        resp = await client.put("/api/apps/promptforge/github/config", json={
            "client_id": "Iv1.second",
            "client_secret": "secret2",
        })
        assert resp.status_code == 200
        assert resp.json()["configured"] is True

        get_resp = await client.get("/api/apps/promptforge/github/config")
        data = get_resp.json()
        assert data["configured"] is True
        assert "second" in data["client_id_hint"] or data["client_id_hint"] == "Iv1.****cond"


# --- Health Endpoint github_configured Tests ---

class TestHealthGitHubConfigured:
    @pytest.mark.asyncio
    async def test_health_not_configured(self, client):
        """Health shows github_configured: false when unconfigured."""
        with (
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_ID", ""),
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_SECRET", ""),
        ):
            resp = await client.get("/api/apps/promptforge/health")
        data = resp.json()
        assert data["workspace"]["github_configured"] is False

    @pytest.mark.asyncio
    async def test_health_configured_via_env(self, client):
        """Health shows github_configured: true with env vars."""
        with (
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_ID", "test_id"),
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_SECRET", "test_secret"),
        ):
            resp = await client.get("/api/apps/promptforge/health")
        data = resp.json()
        assert data["workspace"]["github_configured"] is True

    @pytest.mark.asyncio
    async def test_health_configured_via_db(self, client, db_session):
        """Health shows github_configured: true with DB config."""
        repo = WorkspaceRepository(db_session)
        await repo.upsert_oauth_config(
            client_id="Iv1.test",
            client_secret_encrypted=encrypt_token("secret"),
        )
        await db_session.commit()

        with (
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_ID", ""),
            patch("apps.promptforge.repositories.workspace.config.GITHUB_CLIENT_SECRET", ""),
        ):
            resp = await client.get("/api/apps/promptforge/health")
        data = resp.json()
        assert data["workspace"]["github_configured"] is True


# --- Callback State Validation Tests ---

class TestCallbackStateValidation:
    @pytest.mark.asyncio
    async def test_callback_invalid_state(self, client):
        """Callback with invalid state redirects with error."""
        resp = await client.get(
            "/api/apps/promptforge/github/callback",
            params={"code": "test_code", "state": "bad_state"},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert "invalid_state" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_empty_state(self, client):
        """Callback with empty state redirects with error."""
        resp = await client.get(
            "/api/apps/promptforge/github/callback",
            params={"code": "test_code", "state": ""},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert "invalid_state" in resp.headers["location"]


# --- Auth Middleware Callback Exemption ---

class TestAuthMiddlewareCallbackExemption:
    @pytest.mark.asyncio
    async def test_callback_exempt_from_auth(self, client):
        """OAuth callback is accessible without auth token."""
        with patch("app.middleware.auth.config.AUTH_TOKEN", "secret_token"):
            resp = await client.get(
                "/api/apps/promptforge/github/callback",
                params={"code": "test_code", "state": "invalid"},
                follow_redirects=False,
            )
            # Should NOT get 401 — should get redirect (state validation error)
            assert resp.status_code != 401
