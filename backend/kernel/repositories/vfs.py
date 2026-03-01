"""Repository for kernel VFS — virtual filesystem operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from kernel.models.vfs import VfsFile, VfsFileVersion, VfsFolder

MAX_VFS_DEPTH = 8


class VfsRepository:
    """Data access for the vfs_folders, vfs_files, and vfs_file_versions tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Folders ---

    async def list_children(self, app_id: str, parent_id: str | None = None) -> dict:
        """List child folders and files of a parent folder (or root)."""
        # Folders
        folder_query = select(VfsFolder).where(VfsFolder.app_id == app_id)
        if parent_id:
            folder_query = folder_query.where(VfsFolder.parent_id == parent_id)
        else:
            folder_query = folder_query.where(VfsFolder.parent_id.is_(None))
        folder_result = await self.session.execute(folder_query.order_by(VfsFolder.name))
        folders = [self._folder_to_dict(f) for f in folder_result.scalars().all()]

        # Files
        file_query = select(VfsFile).where(VfsFile.app_id == app_id)
        if parent_id:
            file_query = file_query.where(VfsFile.folder_id == parent_id)
        else:
            file_query = file_query.where(VfsFile.folder_id.is_(None))
        file_result = await self.session.execute(file_query.order_by(VfsFile.name))
        files = [self._file_to_dict(f) for f in file_result.scalars().all()]

        return {"folders": folders, "files": files}

    async def create_folder(
        self, app_id: str, name: str, parent_id: str | None = None, metadata: dict | None = None
    ) -> dict:
        """Create a new folder."""
        depth = 0
        if parent_id:
            parent = await self.session.get(VfsFolder, parent_id)
            if not parent or parent.app_id != app_id:
                raise ValueError("Parent folder not found")
            depth = parent.depth + 1
            if depth >= MAX_VFS_DEPTH:
                raise ValueError(f"Max folder depth ({MAX_VFS_DEPTH}) exceeded")

        now = datetime.now(timezone.utc)
        folder = VfsFolder(
            app_id=app_id, name=name, parent_id=parent_id, depth=depth,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=now, updated_at=now,
        )
        self.session.add(folder)
        await self.session.flush()
        return self._folder_to_dict(folder)

    async def get_folder(self, app_id: str, folder_id: str) -> dict | None:
        """Get a folder by ID."""
        result = await self.session.execute(
            select(VfsFolder).where(VfsFolder.id == folder_id, VfsFolder.app_id == app_id)
        )
        folder = result.scalar_one_or_none()
        return self._folder_to_dict(folder) if folder else None

    async def delete_folder(self, app_id: str, folder_id: str) -> bool:
        """Delete a folder and all contents (cascade)."""
        result = await self.session.execute(
            delete(VfsFolder).where(VfsFolder.id == folder_id, VfsFolder.app_id == app_id)
        )
        return result.rowcount > 0

    async def get_path(self, app_id: str, folder_id: str) -> list[dict]:
        """Get the path from root to a folder (breadcrumb trail)."""
        path = []
        current_id = folder_id
        while current_id:
            result = await self.session.execute(
                select(VfsFolder).where(VfsFolder.id == current_id, VfsFolder.app_id == app_id)
            )
            folder = result.scalar_one_or_none()
            if not folder:
                break
            path.append(self._folder_to_dict(folder))
            current_id = folder.parent_id
        path.reverse()
        return path

    # --- Files ---

    async def create_file(
        self, app_id: str, name: str, content: str = "",
        *, folder_id: str | None = None, content_type: str = "text/plain",
        metadata: dict | None = None,
    ) -> dict:
        """Create a new file."""
        now = datetime.now(timezone.utc)
        file = VfsFile(
            app_id=app_id, folder_id=folder_id, name=name, content=content,
            content_type=content_type, version=1,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=now, updated_at=now,
        )
        self.session.add(file)
        await self.session.flush()
        return self._file_to_dict(file)

    async def get_file(self, app_id: str, file_id: str) -> dict | None:
        """Get a file by ID."""
        result = await self.session.execute(
            select(VfsFile).where(VfsFile.id == file_id, VfsFile.app_id == app_id)
        )
        file = result.scalar_one_or_none()
        return self._file_to_dict(file) if file else None

    async def update_file(
        self, app_id: str, file_id: str, *,
        name: str | None = None, content: str | None = None,
        content_type: str | None = None, metadata: dict | None = None,
        change_source: str | None = None,
    ) -> dict | None:
        """Update a file. Auto-creates a version snapshot before overwriting content."""
        result = await self.session.execute(
            select(VfsFile).where(VfsFile.id == file_id, VfsFile.app_id == app_id)
        )
        file = result.scalar_one_or_none()
        if not file:
            return None

        # Auto-version if content is changing
        if content is not None and content != file.content:
            version_snapshot = VfsFileVersion(
                file_id=file.id, version=file.version,
                content=file.content, change_source=change_source,
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(version_snapshot)
            file.version += 1

        if name is not None:
            file.name = name
        if content is not None:
            file.content = content
        if content_type is not None:
            file.content_type = content_type
        if metadata is not None:
            file.metadata_json = json.dumps(metadata)
        file.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        return self._file_to_dict(file)

    async def delete_file(self, app_id: str, file_id: str) -> bool:
        """Delete a file and its version history (cascade)."""
        result = await self.session.execute(
            delete(VfsFile).where(VfsFile.id == file_id, VfsFile.app_id == app_id)
        )
        return result.rowcount > 0

    async def list_versions(self, app_id: str, file_id: str) -> list[dict]:
        """List all version snapshots for a file."""
        # Verify file belongs to app
        file_result = await self.session.execute(
            select(VfsFile.id).where(VfsFile.id == file_id, VfsFile.app_id == app_id)
        )
        if not file_result.scalar_one_or_none():
            return []

        result = await self.session.execute(
            select(VfsFileVersion).where(VfsFileVersion.file_id == file_id)
            .order_by(VfsFileVersion.version.desc())
        )
        return [
            {
                "id": v.id, "file_id": v.file_id, "version": v.version,
                "content": v.content, "change_source": v.change_source,
                "created_at": v.created_at.isoformat(),
            }
            for v in result.scalars().all()
        ]

    # --- Move / Rename ---

    async def move_folder(
        self, app_id: str, folder_id: str, new_parent_id: str | None,
    ) -> dict | None:
        """Move a folder to a new parent. Validates circular refs and depth limit."""
        result = await self.session.execute(
            select(VfsFolder).where(VfsFolder.id == folder_id, VfsFolder.app_id == app_id)
        )
        folder = result.scalar_one_or_none()
        if not folder:
            return None

        # Calculate new depth
        new_depth = 0
        if new_parent_id:
            # Can't move into itself
            if new_parent_id == folder_id:
                raise ValueError("Cannot move folder into itself")
            # Walk up from new_parent to root to check for circular ref.
            # Cache the immediate target parent (first iteration) for depth calc.
            target_parent: VfsFolder | None = None
            current_id = new_parent_id
            while current_id:
                if current_id == folder_id:
                    raise ValueError("Circular reference: target is a descendant of source")
                parent_result = await self.session.execute(
                    select(VfsFolder).where(
                        VfsFolder.id == current_id, VfsFolder.app_id == app_id,
                    )
                )
                parent = parent_result.scalar_one_or_none()
                if not parent:
                    raise ValueError("Target parent folder not found")
                if target_parent is None:
                    target_parent = parent
                current_id = parent.parent_id
            new_depth = target_parent.depth + 1  # type: ignore[union-attr]

        if new_depth >= MAX_VFS_DEPTH:
            raise ValueError(f"Max folder depth ({MAX_VFS_DEPTH}) exceeded")

        old_depth = folder.depth
        folder.parent_id = new_parent_id
        folder.depth = new_depth
        folder.updated_at = datetime.now(timezone.utc)

        # Cascade depth change to all descendants
        depth_delta = new_depth - old_depth
        if depth_delta != 0:
            await self._cascade_depth(folder.id, depth_delta)

        await self.session.flush()
        return self._folder_to_dict(folder)

    async def rename_folder(self, app_id: str, folder_id: str, new_name: str) -> dict | None:
        """Rename a folder."""
        result = await self.session.execute(
            select(VfsFolder).where(VfsFolder.id == folder_id, VfsFolder.app_id == app_id)
        )
        folder = result.scalar_one_or_none()
        if not folder:
            return None
        folder.name = new_name
        folder.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return self._folder_to_dict(folder)

    async def move_file(
        self, app_id: str, file_id: str, new_folder_id: str | None,
    ) -> dict | None:
        """Move a file to a different folder (or root if None)."""
        result = await self.session.execute(
            select(VfsFile).where(VfsFile.id == file_id, VfsFile.app_id == app_id)
        )
        file = result.scalar_one_or_none()
        if not file:
            return None

        if new_folder_id:
            folder_result = await self.session.execute(
                select(VfsFolder).where(
                    VfsFolder.id == new_folder_id, VfsFolder.app_id == app_id,
                )
            )
            if not folder_result.scalar_one_or_none():
                raise ValueError("Target folder not found")

        file.folder_id = new_folder_id
        file.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return self._file_to_dict(file)

    async def rename_file(self, app_id: str, file_id: str, new_name: str) -> dict | None:
        """Rename a file."""
        result = await self.session.execute(
            select(VfsFile).where(VfsFile.id == file_id, VfsFile.app_id == app_id)
        )
        file = result.scalar_one_or_none()
        if not file:
            return None
        file.name = new_name
        file.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return self._file_to_dict(file)

    # --- Restore ---

    async def restore_version(
        self, app_id: str, file_id: str, version_id: str,
    ) -> dict | None:
        """Restore a file to a previous version.

        Snapshots current content as a new VfsFileVersion, then overwrites
        the file content from the target version.
        """
        # Get the file
        file_result = await self.session.execute(
            select(VfsFile).where(VfsFile.id == file_id, VfsFile.app_id == app_id)
        )
        file = file_result.scalar_one_or_none()
        if not file:
            return None

        # Get the target version
        version_result = await self.session.execute(
            select(VfsFileVersion).where(
                VfsFileVersion.id == version_id,
                VfsFileVersion.file_id == file_id,
            )
        )
        target_version = version_result.scalar_one_or_none()
        if not target_version:
            raise ValueError("Version not found")

        # Snapshot current content before restoring
        now = datetime.now(timezone.utc)
        snapshot = VfsFileVersion(
            file_id=file.id, version=file.version,
            content=file.content, change_source="restore",
            created_at=now,
        )
        self.session.add(snapshot)

        # Overwrite file content from the target version
        file.content = target_version.content
        file.version += 1
        file.updated_at = now
        await self.session.flush()
        return self._file_to_dict(file)

    async def search_files(self, app_id: str, query: str) -> list[dict]:
        """Search files by name within an app."""
        result = await self.session.execute(
            select(VfsFile).where(
                VfsFile.app_id == app_id, VfsFile.name.ilike(f"%{query}%")
            ).order_by(VfsFile.name).limit(50)
        )
        return [self._file_to_dict(f) for f in result.scalars().all()]

    # --- Helpers ---

    async def _cascade_depth(self, parent_id: str, delta: int) -> None:
        """Recursively update depth for all descendant folders."""
        result = await self.session.execute(
            select(VfsFolder).where(VfsFolder.parent_id == parent_id)
        )
        for child in result.scalars().all():
            child.depth += delta
            await self._cascade_depth(child.id, delta)

    def _folder_to_dict(self, folder: VfsFolder) -> dict:
        return {
            "id": folder.id, "app_id": folder.app_id, "name": folder.name,
            "parent_id": folder.parent_id, "depth": folder.depth,
            "metadata": json.loads(folder.metadata_json) if folder.metadata_json else None,
            "created_at": folder.created_at.isoformat(),
            "updated_at": folder.updated_at.isoformat(),
        }

    def _file_to_dict(self, file: VfsFile) -> dict:
        return {
            "id": file.id, "app_id": file.app_id, "folder_id": file.folder_id,
            "name": file.name, "content": file.content, "content_type": file.content_type,
            "version": file.version,
            "metadata": json.loads(file.metadata_json) if file.metadata_json else None,
            "created_at": file.created_at.isoformat(),
            "updated_at": file.updated_at.isoformat(),
        }
