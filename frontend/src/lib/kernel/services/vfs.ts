/**
 * VfsClient — frontend wrapper for kernel VFS REST API.
 *
 * Provides folder/file CRUD, versioning, and search for any app.
 */

import { API_BASE } from "$lib/api/client";
import { throwIfNotOk } from "$lib/kernel/utils/errors";

const BASE = `${API_BASE}/api/kernel/vfs`;

export interface VfsFolder {
	id: string;
	app_id: string;
	name: string;
	parent_id: string | null;
	depth: number;
	metadata: Record<string, unknown> | null;
	created_at: string;
	updated_at: string;
}

export interface VfsFile {
	id: string;
	app_id: string;
	folder_id: string | null;
	name: string;
	content: string;
	content_type: string;
	version: number;
	metadata: Record<string, unknown> | null;
	created_at: string;
	updated_at: string;
}

export interface VfsFileVersion {
	id: string;
	file_id: string;
	version: number;
	content: string;
	change_source: string | null;
	created_at: string;
}

export interface VfsChildren {
	folders: VfsFolder[];
	files: VfsFile[];
}

class VfsClient {
	// --- Children ---

	async listChildren(
		appId: string,
		parentId?: string,
	): Promise<VfsChildren> {
		const params = parentId
			? `?parent_id=${encodeURIComponent(parentId)}`
			: "";
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/children${params}`,
		);
		await throwIfNotOk(res, "list children");
		return res.json();
	}

	// --- Folders ---

	async createFolder(
		appId: string,
		name: string,
		opts?: { parentId?: string; metadata?: Record<string, unknown> },
	): Promise<VfsFolder> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					name,
					parent_id: opts?.parentId ?? null,
					metadata: opts?.metadata ?? null,
				}),
			},
		);
		await throwIfNotOk(res, "create folder");
		return res.json();
	}

	async getFolder(appId: string, folderId: string): Promise<VfsFolder> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}`,
		);
		await throwIfNotOk(res, "get folder");
		return res.json();
	}

	async deleteFolder(appId: string, folderId: string): Promise<void> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}`,
			{ method: "DELETE" },
		);
		await throwIfNotOk(res, "delete folder");
	}

	async getFolderPath(appId: string, folderId: string): Promise<VfsFolder[]> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}/path`,
		);
		await throwIfNotOk(res, "get folder path");
		const data = await res.json();
		return data.path;
	}

	// --- Files ---

	async createFile(
		appId: string,
		opts: {
			name: string;
			content?: string;
			folderId?: string;
			contentType?: string;
			metadata?: Record<string, unknown>;
		},
	): Promise<VfsFile> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					name: opts.name,
					content: opts.content ?? "",
					folder_id: opts.folderId ?? null,
					content_type: opts.contentType ?? "text/plain",
					metadata: opts.metadata ?? null,
				}),
			},
		);
		await throwIfNotOk(res, "create file");
		return res.json();
	}

	async getFile(appId: string, fileId: string): Promise<VfsFile> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}`,
		);
		await throwIfNotOk(res, "get file");
		return res.json();
	}

	async updateFile(
		appId: string,
		fileId: string,
		opts: {
			name?: string;
			content?: string;
			contentType?: string;
			metadata?: Record<string, unknown>;
			changeSource?: string;
		},
	): Promise<VfsFile> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}`,
			{
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					name: opts.name ?? null,
					content: opts.content ?? null,
					content_type: opts.contentType ?? null,
					metadata: opts.metadata ?? null,
					change_source: opts.changeSource ?? null,
				}),
			},
		);
		await throwIfNotOk(res, "update file");
		return res.json();
	}

	async deleteFile(appId: string, fileId: string): Promise<void> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}`,
			{ method: "DELETE" },
		);
		await throwIfNotOk(res, "delete file");
	}

	// --- Move / Rename ---

	async moveFolder(
		appId: string,
		folderId: string,
		newParentId: string | null,
	): Promise<VfsFolder> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}/move`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ new_parent_id: newParentId }),
			},
		);
		await throwIfNotOk(res, "move folder");
		return res.json();
	}

	async renameFolder(
		appId: string,
		folderId: string,
		name: string,
	): Promise<VfsFolder> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}/rename`,
			{
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ name }),
			},
		);
		await throwIfNotOk(res, "rename folder");
		return res.json();
	}

	async moveFile(
		appId: string,
		fileId: string,
		newFolderId: string | null,
	): Promise<VfsFile> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}/move`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ new_folder_id: newFolderId }),
			},
		);
		await throwIfNotOk(res, "move file");
		return res.json();
	}

	async renameFile(
		appId: string,
		fileId: string,
		name: string,
	): Promise<VfsFile> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}/rename`,
			{
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ name }),
			},
		);
		await throwIfNotOk(res, "rename file");
		return res.json();
	}

	// --- Versions ---

	async listVersions(
		appId: string,
		fileId: string,
	): Promise<VfsFileVersion[]> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}/versions`,
		);
		await throwIfNotOk(res, "list file versions");
		const data = await res.json();
		return data.versions;
	}

	async restoreVersion(
		appId: string,
		fileId: string,
		versionId: string,
	): Promise<VfsFile> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}/versions/${encodeURIComponent(versionId)}/restore`,
			{ method: "POST" },
		);
		await throwIfNotOk(res, "restore version");
		return res.json();
	}

	// --- Search ---

	async searchFiles(appId: string, query: string): Promise<VfsFile[]> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/search?q=${encodeURIComponent(query)}`,
		);
		await throwIfNotOk(res, "search files");
		const data = await res.json();
		return data.results;
	}
}

export const vfs = new VfsClient();
