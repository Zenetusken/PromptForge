"""Tests for the hierarchical folder system (filesystem API)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.constants import MAX_FOLDER_DEPTH
from apps.promptforge.repositories.project import ProjectRepository, ensure_project_by_name

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_folder(
    client: AsyncClient, name: str, parent_id: str | None = None,
) -> dict:
    resp = await client.post(
        "/api/apps/promptforge/projects",
        json={"name": name, "parent_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_prompt(client: AsyncClient, project_id: str, content: str) -> dict:
    resp = await client.post(
        f"/api/apps/promptforge/projects/{project_id}/prompts",
        json={"content": content},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Schema: parent_id / depth on Project
# ---------------------------------------------------------------------------

class TestProjectHierarchy:

    @pytest.mark.asyncio
    async def test_create_root_folder(self, client: AsyncClient):
        data = await _create_folder(client, "Root Folder")
        assert data["parent_id"] is None
        assert data["depth"] == 0

    @pytest.mark.asyncio
    async def test_create_subfolder(self, client: AsyncClient):
        root = await _create_folder(client, "Parent")
        child = await _create_folder(client, "Child", parent_id=root["id"])
        assert child["parent_id"] == root["id"]
        assert child["depth"] == 1

    @pytest.mark.asyncio
    async def test_same_name_different_parents(self, client: AsyncClient):
        """Same name under different parents should be OK."""
        root_a = await _create_folder(client, "A")
        root_b = await _create_folder(client, "B")
        child_a = await _create_folder(client, "same-name", parent_id=root_a["id"])
        child_b = await _create_folder(client, "same-name", parent_id=root_b["id"])
        assert child_a["id"] != child_b["id"]

    @pytest.mark.asyncio
    async def test_same_name_same_parent_409(self, client: AsyncClient):
        """Same name under the same parent should fail with 409."""
        root = await _create_folder(client, "DupParent")
        await _create_folder(client, "Dup", parent_id=root["id"])
        resp = await client.post(
            "/api/apps/promptforge/projects",
            json={"name": "Dup", "parent_id": root["id"]},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_depth_limit_enforced(self, client: AsyncClient):
        """Chain up to MAX_FOLDER_DEPTH should succeed; one more should fail."""
        # Build a chain: depth 0, 1, 2, ..., MAX_FOLDER_DEPTH
        parent_id = None
        for i in range(MAX_FOLDER_DEPTH + 1):
            folder = await _create_folder(client, f"Level-{i}", parent_id=parent_id)
            parent_id = folder["id"]
            assert folder["depth"] == i

        # The last folder is at depth MAX_FOLDER_DEPTH; creating one more
        # child should exceed the limit.
        resp = await client.post(
            "/api/apps/promptforge/projects",
            json={"name": "Too Deep", "parent_id": parent_id},
        )
        assert resp.status_code == 400
        assert "depth" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_parent_id(self, client: AsyncClient):
        resp = await client.post(
            "/api/apps/promptforge/projects",
            json={"name": "Orphan", "parent_id": "nonexistent-id"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_get_project_includes_hierarchy_fields(self, client: AsyncClient):
        root = await _create_folder(client, "HierRoot")
        child = await _create_folder(client, "HierChild", parent_id=root["id"])
        resp = await client.get(f"/api/apps/promptforge/projects/{child['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent_id"] == root["id"]
        assert data["depth"] == 1

    @pytest.mark.asyncio
    async def test_list_projects_includes_hierarchy_fields(self, client: AsyncClient):
        root = await _create_folder(client, "ListRoot")
        await _create_folder(client, "ListChild", parent_id=root["id"])
        resp = await client.get("/api/apps/promptforge/projects")
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert "parent_id" in item
            assert "depth" in item


# ---------------------------------------------------------------------------
# Filesystem API: /api/fs/*
# ---------------------------------------------------------------------------

class TestFsChildren:

    @pytest.mark.asyncio
    async def test_root_children(self, client: AsyncClient):
        await _create_folder(client, "FsRoot1")
        await _create_folder(client, "FsRoot2")
        resp = await client.get("/api/apps/promptforge/fs/children")
        assert resp.status_code == 200
        data = resp.json()
        names = [n["name"] for n in data["nodes"]]
        assert "FsRoot1" in names
        assert "FsRoot2" in names
        assert data["path"] == []

    @pytest.mark.asyncio
    async def test_folder_children(self, client: AsyncClient):
        root = await _create_folder(client, "FsParent")
        await _create_folder(client, "FsSub", parent_id=root["id"])
        await _add_prompt(client, root["id"], "Hello world")
        resp = await client.get("/api/apps/promptforge/fs/children", params={"parent_id": root["id"]})
        assert resp.status_code == 200
        data = resp.json()
        types = {n["type"] for n in data["nodes"]}
        assert "folder" in types
        assert "prompt" in types
        # Path should include the parent
        assert len(data["path"]) >= 1
        assert data["path"][-1]["id"] == root["id"]

    @pytest.mark.asyncio
    async def test_children_of_nonexistent_parent(self, client: AsyncClient):
        resp = await client.get("/api/apps/promptforge/fs/children", params={"parent_id": "bad-id"})
        assert resp.status_code == 404


class TestFsTree:

    @pytest.mark.asyncio
    async def test_full_tree(self, client: AsyncClient):
        root = await _create_folder(client, "TreeRoot")
        child = await _create_folder(client, "TreeChild", parent_id=root["id"])
        await _create_folder(client, "TreeGrandchild", parent_id=child["id"])

        resp = await client.get("/api/apps/promptforge/fs/tree", params={"root_id": root["id"]})
        assert resp.status_code == 200
        nodes = resp.json()["nodes"]
        names = [n["name"] for n in nodes]
        assert "TreeRoot" in names
        assert "TreeChild" in names
        assert "TreeGrandchild" in names

    @pytest.mark.asyncio
    async def test_root_tree(self, client: AsyncClient):
        await _create_folder(client, "RootTree1")
        resp = await client.get("/api/apps/promptforge/fs/tree")
        assert resp.status_code == 200
        names = [n["name"] for n in resp.json()["nodes"]]
        assert "RootTree1" in names


class TestFsPath:

    @pytest.mark.asyncio
    async def test_path_chain(self, client: AsyncClient):
        a = await _create_folder(client, "PathA")
        b = await _create_folder(client, "PathB", parent_id=a["id"])
        c = await _create_folder(client, "PathC", parent_id=b["id"])

        resp = await client.get(f"/api/apps/promptforge/fs/path/{c['id']}")
        assert resp.status_code == 200
        segments = resp.json()["segments"]
        names = [s["name"] for s in segments]
        assert names == ["PathA", "PathB", "PathC"]

    @pytest.mark.asyncio
    async def test_path_not_found(self, client: AsyncClient):
        resp = await client.get("/api/apps/promptforge/fs/path/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Move operations
# ---------------------------------------------------------------------------

class TestFsMove:

    @pytest.mark.asyncio
    async def test_move_project_to_subfolder(self, client: AsyncClient):
        root = await _create_folder(client, "MoveRoot")
        target = await _create_folder(client, "MoveTarget")
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "project", "id": root["id"], "new_parent_id": target["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["node"]["parent_id"] == target["id"]

    @pytest.mark.asyncio
    async def test_move_project_to_root(self, client: AsyncClient):
        root = await _create_folder(client, "MoveRootParent")
        child = await _create_folder(client, "MoveRootChild", parent_id=root["id"])
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "project", "id": child["id"], "new_parent_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["node"]["parent_id"] is None

    @pytest.mark.asyncio
    async def test_move_prompt_between_folders(self, client: AsyncClient):
        folder_a = await _create_folder(client, "PromptFolderA")
        folder_b = await _create_folder(client, "PromptFolderB")
        prompt = await _add_prompt(client, folder_a["id"], "Move me")
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "prompt", "id": prompt["id"], "new_parent_id": folder_b["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["node"]["parent_id"] == folder_b["id"]

    @pytest.mark.asyncio
    async def test_move_prompt_to_desktop(self, client: AsyncClient):
        folder = await _create_folder(client, "PromptDesktopFolder")
        prompt = await _add_prompt(client, folder["id"], "To desktop")
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "prompt", "id": prompt["id"], "new_parent_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["node"]["parent_id"] is None

    @pytest.mark.asyncio
    async def test_circular_ref_rejected(self, client: AsyncClient):
        """A -> B -> C; moving A under C should fail."""
        a = await _create_folder(client, "CircA")
        b = await _create_folder(client, "CircB", parent_id=a["id"])
        c = await _create_folder(client, "CircC", parent_id=b["id"])
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "project", "id": a["id"], "new_parent_id": c["id"]},
        )
        assert resp.status_code == 400
        assert "circular" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_self_nesting_rejected(self, client: AsyncClient):
        folder = await _create_folder(client, "SelfNest")
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "project", "id": folder["id"], "new_parent_id": folder["id"]},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_move_depth_limit(self, client: AsyncClient):
        """Moving a subtree that would exceed depth limit should fail."""
        # Create a chain up to MAX_FOLDER_DEPTH (depth 0..MAX_FOLDER_DEPTH)
        parent_id = None
        for i in range(MAX_FOLDER_DEPTH + 1):
            folder = await _create_folder(client, f"Deep-{i}", parent_id=parent_id)
            parent_id = folder["id"]
        # The last folder is at depth MAX_FOLDER_DEPTH
        deep_folder = folder

        # Create a separate small chain: X -> Y (X at depth 0, Y at depth 1)
        x = await _create_folder(client, "X")
        await _create_folder(client, "Y", parent_id=x["id"])

        # Moving X under deep_folder would put X at depth MAX_FOLDER_DEPTH+1
        # which exceeds the limit
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "project", "id": x["id"], "new_parent_id": deep_folder["id"]},
        )
        assert resp.status_code == 400
        assert "depth" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_move_recomputes_subtree_depth(self, client: AsyncClient):
        """Moving a folder with children should recompute depth for entire subtree."""
        root = await _create_folder(client, "DepthRoot")
        child = await _create_folder(client, "DepthChild", parent_id=root["id"])
        grandchild = await _create_folder(client, "DepthGC", parent_id=child["id"])
        assert grandchild["depth"] == 2

        # Move child to root level
        resp = await client.post(
            "/api/apps/promptforge/fs/move",
            json={"type": "project", "id": child["id"], "new_parent_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["node"]["depth"] == 0

        # Verify grandchild depth is now 1
        gc_resp = await client.get(f"/api/apps/promptforge/projects/{grandchild['id']}")
        assert gc_resp.status_code == 200
        assert gc_resp.json()["depth"] == 1


# ---------------------------------------------------------------------------
# MCP compatibility: ensure_project_by_name matches only root-level
# ---------------------------------------------------------------------------

class TestMCPCompat:

    @pytest.mark.asyncio
    async def test_ensure_matches_root_only(self, db_session: AsyncSession):
        """ensure_project_by_name should only match root-level projects."""
        repo = ProjectRepository(db_session)
        # Create a root project
        root = await repo.create(name="mcp-proj")
        await db_session.flush()

        # Create a subfolder with the same name
        await repo.create(name="mcp-proj", parent_id=root.id)
        await db_session.flush()

        # ensure_project_by_name should return the root one
        info = await ensure_project_by_name(db_session, "mcp-proj")
        assert info is not None
        assert info.id == root.id


# ---------------------------------------------------------------------------
# Repository: direct unit tests
# ---------------------------------------------------------------------------

class TestRepositoryFilesystem:

    @pytest.mark.asyncio
    async def test_get_children_root(self, db_session: AsyncSession):
        repo = ProjectRepository(db_session)
        await repo.create(name="RepoRoot")
        await db_session.flush()

        folders, prompts = await repo.get_children(None)
        names = [f.name for f in folders]
        assert "RepoRoot" in names
        assert prompts == []

    @pytest.mark.asyncio
    async def test_get_children_folder(self, db_session: AsyncSession):
        repo = ProjectRepository(db_session)
        parent = await repo.create(name="RepoParent")
        await db_session.flush()

        await repo.create(name="RepoChild", parent_id=parent.id)
        await repo.add_prompt(parent, "repo prompt content")
        await db_session.flush()

        folders, prompts = await repo.get_children(parent.id)
        assert len(folders) == 1
        assert folders[0].name == "RepoChild"
        assert len(prompts) == 1

    @pytest.mark.asyncio
    async def test_get_subtree(self, db_session: AsyncSession):
        repo = ProjectRepository(db_session)
        root = await repo.create(name="SubRoot")
        await db_session.flush()
        child = await repo.create(name="SubChild", parent_id=root.id)
        await db_session.flush()
        await repo.create(name="SubGC", parent_id=child.id)
        await db_session.flush()

        tree = await repo.get_subtree(root.id)
        names = [n["name"] for n in tree]
        assert "SubRoot" in names
        assert "SubChild" in names
        assert "SubGC" in names

    @pytest.mark.asyncio
    async def test_get_path(self, db_session: AsyncSession):
        repo = ProjectRepository(db_session)
        a = await repo.create(name="PathRepoA")
        await db_session.flush()
        b = await repo.create(name="PathRepoB", parent_id=a.id)
        await db_session.flush()

        path = await repo.get_path(b.id)
        names = [s["name"] for s in path]
        assert names == ["PathRepoA", "PathRepoB"]

    @pytest.mark.asyncio
    async def test_move_prompt_to_none(self, db_session: AsyncSession):
        repo = ProjectRepository(db_session)
        folder = await repo.create(name="PromptMoveFolder")
        await db_session.flush()
        prompt = await repo.add_prompt(folder, "move me to desktop")
        await db_session.flush()

        moved = await repo.move_prompt(prompt.id, None)
        assert moved.project_id is None

    @pytest.mark.asyncio
    async def test_validate_name_unique(self, db_session: AsyncSession):
        repo = ProjectRepository(db_session)
        await repo.create(name="UniqueTest")
        await db_session.flush()

        with pytest.raises(ValueError, match="already exists"):
            await repo._validate_name_unique("UniqueTest", None)
