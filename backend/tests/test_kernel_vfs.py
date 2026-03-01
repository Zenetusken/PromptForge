"""Tests for the kernel VFS — virtual filesystem router and repository."""

import pytest


# ── Router tests (via httpx client) ──────────────────────────────────


class TestVfsFolders:
    """CRUD operations on VFS folders."""

    @pytest.mark.asyncio
    async def test_create_folder(self, client):
        response = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "Documents"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Documents"
        assert data["app_id"] == "test-app"
        assert data["parent_id"] is None
        assert data["depth"] == 0

    @pytest.mark.asyncio
    async def test_create_nested_folder(self, client):
        parent = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "Root"},
        )
        parent_id = parent.json()["id"]

        child = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "Child", "parent_id": parent_id},
        )
        assert child.status_code == 201
        assert child.json()["depth"] == 1
        assert child.json()["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_create_folder_max_depth_exceeded(self, client):
        # Build a chain up to MAX_VFS_DEPTH (8)
        current_id = None
        for i in range(8):
            resp = await client.post(
                "/api/kernel/vfs/test-app/folders",
                json={"name": f"level-{i}", "parent_id": current_id},
            )
            assert resp.status_code == 201, f"level {i}: {resp.text}"
            current_id = resp.json()["id"]

        # One more should fail
        resp = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "too-deep", "parent_id": current_id},
        )
        assert resp.status_code == 400
        assert "depth" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_folder(self, client):
        created = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "GetMe"},
        )
        folder_id = created.json()["id"]

        resp = await client.get(f"/api/kernel/vfs/test-app/folders/{folder_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetMe"

    @pytest.mark.asyncio
    async def test_get_folder_not_found(self, client):
        resp = await client.get("/api/kernel/vfs/test-app/folders/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_folder(self, client):
        created = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "DeleteMe"},
        )
        folder_id = created.json()["id"]

        resp = await client.delete(f"/api/kernel/vfs/test-app/folders/{folder_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify gone
        resp = await client.get(f"/api/kernel/vfs/test-app/folders/{folder_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_folder_not_found(self, client):
        resp = await client.delete("/api/kernel/vfs/test-app/folders/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_folder_path(self, client):
        root = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "A"},
        )
        mid = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "B", "parent_id": root.json()["id"]},
        )
        leaf = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "C", "parent_id": mid.json()["id"]},
        )

        resp = await client.get(
            f"/api/kernel/vfs/test-app/folders/{leaf.json()['id']}/path"
        )
        assert resp.status_code == 200
        path = resp.json()["path"]
        assert len(path) == 3
        assert path[0]["name"] == "A"
        assert path[1]["name"] == "B"
        assert path[2]["name"] == "C"

    @pytest.mark.asyncio
    async def test_create_folder_with_metadata(self, client):
        resp = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "Meta", "metadata": {"icon": "folder"}},
        )
        assert resp.status_code == 201
        assert resp.json()["metadata"] == {"icon": "folder"}


class TestVfsFiles:
    """CRUD operations on VFS files."""

    @pytest.mark.asyncio
    async def test_create_file(self, client):
        resp = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "readme.md", "content": "# Hello"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "readme.md"
        assert data["content"] == "# Hello"
        assert data["version"] == 1
        assert data["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_create_file_in_folder(self, client):
        folder = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "Docs"},
        )
        folder_id = folder.json()["id"]

        resp = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "notes.txt", "content": "notes", "folder_id": folder_id},
        )
        assert resp.status_code == 201
        assert resp.json()["folder_id"] == folder_id

    @pytest.mark.asyncio
    async def test_get_file(self, client):
        created = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "test.txt", "content": "test content"},
        )
        file_id = created.json()["id"]

        resp = await client.get(f"/api/kernel/vfs/test-app/files/{file_id}")
        assert resp.status_code == 200
        assert resp.json()["content"] == "test content"

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, client):
        resp = await client.get("/api/kernel/vfs/test-app/files/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_file_content(self, client):
        created = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "versioned.txt", "content": "v1"},
        )
        file_id = created.json()["id"]

        resp = await client.put(
            f"/api/kernel/vfs/test-app/files/{file_id}",
            json={"content": "v2", "change_source": "user-edit"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "v2"
        assert resp.json()["version"] == 2

    @pytest.mark.asyncio
    async def test_update_file_not_found(self, client):
        resp = await client.put(
            "/api/kernel/vfs/test-app/files/nonexistent",
            json={"content": "new"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_file(self, client):
        created = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "delete-me.txt", "content": "bye"},
        )
        file_id = created.json()["id"]

        resp = await client.delete(f"/api/kernel/vfs/test-app/files/{file_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, client):
        resp = await client.delete("/api/kernel/vfs/test-app/files/nonexistent")
        assert resp.status_code == 404


class TestVfsVersioning:
    """File version history via auto-snapshotting."""

    @pytest.mark.asyncio
    async def test_versions_created_on_content_change(self, client):
        created = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "v-test.txt", "content": "original"},
        )
        file_id = created.json()["id"]

        await client.put(
            f"/api/kernel/vfs/test-app/files/{file_id}",
            json={"content": "updated-1"},
        )
        await client.put(
            f"/api/kernel/vfs/test-app/files/{file_id}",
            json={"content": "updated-2"},
        )

        resp = await client.get(
            f"/api/kernel/vfs/test-app/files/{file_id}/versions"
        )
        assert resp.status_code == 200
        versions = resp.json()["versions"]
        assert len(versions) == 2
        # Most recent version snapshot first
        assert versions[0]["version"] == 2
        assert versions[0]["content"] == "updated-1"
        assert versions[1]["version"] == 1
        assert versions[1]["content"] == "original"

    @pytest.mark.asyncio
    async def test_no_version_when_content_unchanged(self, client):
        created = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "stable.txt", "content": "same"},
        )
        file_id = created.json()["id"]

        # Update name only, content stays the same
        await client.put(
            f"/api/kernel/vfs/test-app/files/{file_id}",
            json={"name": "renamed.txt"},
        )

        resp = await client.get(
            f"/api/kernel/vfs/test-app/files/{file_id}/versions"
        )
        assert len(resp.json()["versions"]) == 0


class TestVfsChildren:
    """Combined folder + file listing."""

    @pytest.mark.asyncio
    async def test_list_root_children(self, client):
        await client.post("/api/kernel/vfs/test-app/folders", json={"name": "F1"})
        await client.post(
            "/api/kernel/vfs/test-app/files", json={"name": "root.txt", "content": "hi"},
        )

        resp = await client.get("/api/kernel/vfs/test-app/children")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["folders"]) >= 1
        assert len(data["files"]) >= 1

    @pytest.mark.asyncio
    async def test_list_folder_children(self, client):
        folder = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "Parent"},
        )
        folder_id = folder.json()["id"]

        await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "SubFolder", "parent_id": folder_id},
        )
        await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "child.txt", "content": "c", "folder_id": folder_id},
        )

        resp = await client.get(
            f"/api/kernel/vfs/test-app/children?parent_id={folder_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["folders"]) == 1
        assert data["folders"][0]["name"] == "SubFolder"
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "child.txt"


class TestVfsSearch:
    """File search by name."""

    @pytest.mark.asyncio
    async def test_search_files(self, client):
        await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "searchable-doc.md", "content": "content"},
        )
        await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "other.txt", "content": "other"},
        )

        resp = await client.get("/api/kernel/vfs/test-app/search?q=searchable")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["name"] == "searchable-doc.md"

    @pytest.mark.asyncio
    async def test_search_empty_query_rejected(self, client):
        resp = await client.get("/api/kernel/vfs/test-app/search?q=")
        assert resp.status_code == 422


class TestVfsAppIsolation:
    """Files and folders are scoped to app_id."""

    @pytest.mark.asyncio
    async def test_different_apps_isolated(self, client):
        await client.post(
            "/api/kernel/vfs/app-a/folders", json={"name": "OnlyA"},
        )
        await client.post(
            "/api/kernel/vfs/app-b/folders", json={"name": "OnlyB"},
        )

        resp_a = await client.get("/api/kernel/vfs/app-a/children")
        resp_b = await client.get("/api/kernel/vfs/app-b/children")

        names_a = [f["name"] for f in resp_a.json()["folders"]]
        names_b = [f["name"] for f in resp_b.json()["folders"]]

        assert "OnlyA" in names_a
        assert "OnlyB" not in names_a
        assert "OnlyB" in names_b
        assert "OnlyA" not in names_b

    @pytest.mark.asyncio
    async def test_get_folder_wrong_app(self, client):
        created = await client.post(
            "/api/kernel/vfs/app-a/folders", json={"name": "Secret"},
        )
        folder_id = created.json()["id"]

        # Should not find it under app-b
        resp = await client.get(f"/api/kernel/vfs/app-b/folders/{folder_id}")
        assert resp.status_code == 404


# ── Move / Rename ────────────────────────────────────────────────────


class TestVfsMoveFolder:
    """Move folder to a new parent."""

    @pytest.mark.asyncio
    async def test_move_folder_to_new_parent(self, client):
        a = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "A"})
        b = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "B"})

        resp = await client.post(
            f"/api/kernel/vfs/test-app/folders/{b.json()['id']}/move",
            json={"new_parent_id": a.json()["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["parent_id"] == a.json()["id"]
        assert resp.json()["depth"] == 1

    @pytest.mark.asyncio
    async def test_move_folder_to_root(self, client):
        parent = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "Parent"})
        child = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "Child", "parent_id": parent.json()["id"]},
        )

        resp = await client.post(
            f"/api/kernel/vfs/test-app/folders/{child.json()['id']}/move",
            json={"new_parent_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None
        assert resp.json()["depth"] == 0

    @pytest.mark.asyncio
    async def test_move_folder_into_itself_rejected(self, client):
        folder = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "Self"})
        folder_id = folder.json()["id"]

        resp = await client.post(
            f"/api/kernel/vfs/test-app/folders/{folder_id}/move",
            json={"new_parent_id": folder_id},
        )
        assert resp.status_code == 400
        assert "itself" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_move_folder_circular_ref_rejected(self, client):
        a = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "A"})
        b = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "B", "parent_id": a.json()["id"]},
        )

        # Try to move A under B (B is a child of A → circular)
        resp = await client.post(
            f"/api/kernel/vfs/test-app/folders/{a.json()['id']}/move",
            json={"new_parent_id": b.json()["id"]},
        )
        assert resp.status_code == 400
        assert "circular" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_move_folder_not_found(self, client):
        resp = await client.post(
            "/api/kernel/vfs/test-app/folders/nonexistent/move",
            json={"new_parent_id": None},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_move_folder_depth_limit(self, client):
        # Build a chain of 8 levels deep (depths 0-7, MAX_VFS_DEPTH=8)
        current_id = None
        for i in range(8):
            resp = await client.post(
                "/api/kernel/vfs/test-app/folders",
                json={"name": f"deep-{i}", "parent_id": current_id},
            )
            current_id = resp.json()["id"]

        # Create a standalone folder and try to move it under the deepest
        standalone = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "standalone"},
        )
        resp = await client.post(
            f"/api/kernel/vfs/test-app/folders/{standalone.json()['id']}/move",
            json={"new_parent_id": current_id},
        )
        assert resp.status_code == 400
        assert "depth" in resp.json()["detail"].lower()


class TestVfsMoveFile:
    """Move file to a different folder."""

    @pytest.mark.asyncio
    async def test_move_file_to_folder(self, client):
        folder = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "Target"})
        file = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "moveme.txt", "content": "hi"},
        )

        resp = await client.post(
            f"/api/kernel/vfs/test-app/files/{file.json()['id']}/move",
            json={"new_folder_id": folder.json()["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["folder_id"] == folder.json()["id"]

    @pytest.mark.asyncio
    async def test_move_file_to_root(self, client):
        folder = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "Source"})
        file = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "root.txt", "content": "hi", "folder_id": folder.json()["id"]},
        )

        resp = await client.post(
            f"/api/kernel/vfs/test-app/files/{file.json()['id']}/move",
            json={"new_folder_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["folder_id"] is None

    @pytest.mark.asyncio
    async def test_move_file_invalid_folder(self, client):
        file = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "bad-move.txt", "content": "hi"},
        )
        resp = await client.post(
            f"/api/kernel/vfs/test-app/files/{file.json()['id']}/move",
            json={"new_folder_id": "nonexistent-folder"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_move_file_not_found(self, client):
        resp = await client.post(
            "/api/kernel/vfs/test-app/files/nonexistent/move",
            json={"new_folder_id": None},
        )
        assert resp.status_code == 404


class TestVfsRenameFolder:
    """Rename folder."""

    @pytest.mark.asyncio
    async def test_rename_folder(self, client):
        folder = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "OldName"})

        resp = await client.patch(
            f"/api/kernel/vfs/test-app/folders/{folder.json()['id']}/rename",
            json={"name": "NewName"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    @pytest.mark.asyncio
    async def test_rename_folder_not_found(self, client):
        resp = await client.patch(
            "/api/kernel/vfs/test-app/folders/nonexistent/rename",
            json={"name": "New"},
        )
        assert resp.status_code == 404


class TestVfsRenameFile:
    """Rename file."""

    @pytest.mark.asyncio
    async def test_rename_file(self, client):
        file = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "old.txt", "content": "hi"},
        )

        resp = await client.patch(
            f"/api/kernel/vfs/test-app/files/{file.json()['id']}/rename",
            json={"name": "new.txt"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "new.txt"

    @pytest.mark.asyncio
    async def test_rename_file_not_found(self, client):
        resp = await client.patch(
            "/api/kernel/vfs/test-app/files/nonexistent/rename",
            json={"name": "new.txt"},
        )
        assert resp.status_code == 404


class TestVfsRestoreVersion:
    """Restore a file to a previous version."""

    @pytest.mark.asyncio
    async def test_restore_version(self, client):
        # Create file with v1 content
        created = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "restore.txt", "content": "original"},
        )
        file_id = created.json()["id"]

        # Update to v2
        await client.put(
            f"/api/kernel/vfs/test-app/files/{file_id}",
            json={"content": "updated"},
        )

        # Get versions — should have one snapshot (v1)
        versions_resp = await client.get(
            f"/api/kernel/vfs/test-app/files/{file_id}/versions"
        )
        versions = versions_resp.json()["versions"]
        assert len(versions) == 1
        v1_id = versions[0]["id"]

        # Restore to v1
        resp = await client.post(
            f"/api/kernel/vfs/test-app/files/{file_id}/versions/{v1_id}/restore"
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "original"
        assert resp.json()["version"] == 3  # v1 snapshot → v2 update → v3 restore

    @pytest.mark.asyncio
    async def test_restore_version_not_found(self, client):
        file = await client.post(
            "/api/kernel/vfs/test-app/files",
            json={"name": "no-restore.txt", "content": "hi"},
        )
        resp = await client.post(
            f"/api/kernel/vfs/test-app/files/{file.json()['id']}/versions/nonexistent/restore"
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_restore_file_not_found(self, client):
        resp = await client.post(
            "/api/kernel/vfs/test-app/files/nonexistent/versions/whatever/restore"
        )
        assert resp.status_code == 404


class TestVfsMoveFolderDepthCascade:
    """Moving a folder must cascade depth updates to all descendants."""

    @pytest.mark.asyncio
    async def test_move_folder_cascades_depth_to_children(self, client):
        # Create A (depth 0) → B (depth 1) → C (depth 2)
        a = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "A"})
        b = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "B", "parent_id": a.json()["id"]},
        )
        c = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "C", "parent_id": b.json()["id"]},
        )
        assert b.json()["depth"] == 1
        assert c.json()["depth"] == 2

        # Create D (depth 0), move A under D
        d = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "D"})
        resp = await client.post(
            f"/api/kernel/vfs/test-app/folders/{a.json()['id']}/move",
            json={"new_parent_id": d.json()["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["depth"] == 1  # A: 0 → 1

        # Verify B is now depth 2 (was 1)
        b_resp = await client.get(f"/api/kernel/vfs/test-app/folders/{b.json()['id']}")
        assert b_resp.json()["depth"] == 2

        # Verify C is now depth 3 (was 2)
        c_resp = await client.get(f"/api/kernel/vfs/test-app/folders/{c.json()['id']}")
        assert c_resp.json()["depth"] == 3

    @pytest.mark.asyncio
    async def test_move_folder_to_root_cascades_depth(self, client):
        # Create P (depth 0) → Q (depth 1) → R (depth 2)
        p = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "P"})
        q = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "Q", "parent_id": p.json()["id"]},
        )
        r = await client.post(
            "/api/kernel/vfs/test-app/folders",
            json={"name": "R", "parent_id": q.json()["id"]},
        )

        # Move Q to root: Q becomes depth 0, R becomes depth 1
        resp = await client.post(
            f"/api/kernel/vfs/test-app/folders/{q.json()['id']}/move",
            json={"new_parent_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["depth"] == 0

        r_resp = await client.get(f"/api/kernel/vfs/test-app/folders/{r.json()['id']}")
        assert r_resp.json()["depth"] == 1


class TestVfsRenameConflict:
    """Renaming to a duplicate name returns 409."""

    @pytest.mark.asyncio
    async def test_rename_folder_duplicate_name_returns_409(self, client):
        # Create a parent folder (non-NULL parent_id needed for SQLite UNIQUE enforcement)
        parent = await client.post("/api/kernel/vfs/test-app/folders", json={"name": "Parent"})
        pid = parent.json()["id"]
        # Create two sibling folders inside the parent
        await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "Existing", "parent_id": pid},
        )
        other = await client.post(
            "/api/kernel/vfs/test-app/folders", json={"name": "Other", "parent_id": pid},
        )

        # Rename Other → Existing (conflict in same parent)
        resp = await client.patch(
            f"/api/kernel/vfs/test-app/folders/{other.json()['id']}/rename",
            json={"name": "Existing"},
        )
        assert resp.status_code == 409
