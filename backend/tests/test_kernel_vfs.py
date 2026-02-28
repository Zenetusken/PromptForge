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
