/**
 * VfsClient — frontend wrapper for kernel VFS REST API.
 *
 * Provides folder/file CRUD, versioning, and search for any app.
 */

import { API_BASE } from "$lib/api/client";

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
		if (!res.ok) throw new Error(`Failed to list children: ${res.status}`);
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
		if (!res.ok) throw new Error(`Failed to create folder: ${res.status}`);
		return res.json();
	}

	async getFolder(appId: string, folderId: string): Promise<VfsFolder> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}`,
		);
		if (!res.ok) throw new Error(`Failed to get folder: ${res.status}`);
		return res.json();
	}

	async deleteFolder(appId: string, folderId: string): Promise<void> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}`,
			{ method: "DELETE" },
		);
		if (!res.ok) throw new Error(`Failed to delete folder: ${res.status}`);
	}

	async getFolderPath(appId: string, folderId: string): Promise<VfsFolder[]> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/folders/${encodeURIComponent(folderId)}/path`,
		);
		if (!res.ok) throw new Error(`Failed to get folder path: ${res.status}`);
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
		if (!res.ok) throw new Error(`Failed to create file: ${res.status}`);
		return res.json();
	}

	async getFile(appId: string, fileId: string): Promise<VfsFile> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}`,
		);
		if (!res.ok) throw new Error(`Failed to get file: ${res.status}`);
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
		if (!res.ok) throw new Error(`Failed to update file: ${res.status}`);
		return res.json();
	}

	async deleteFile(appId: string, fileId: string): Promise<void> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}`,
			{ method: "DELETE" },
		);
		if (!res.ok) throw new Error(`Failed to delete file: ${res.status}`);
	}

	// --- Versions ---

	async listVersions(
		appId: string,
		fileId: string,
	): Promise<VfsFileVersion[]> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/files/${encodeURIComponent(fileId)}/versions`,
		);
		if (!res.ok)
			throw new Error(`Failed to list file versions: ${res.status}`);
		const data = await res.json();
		return data.versions;
	}

	// --- Search ---

	async searchFiles(appId: string, query: string): Promise<VfsFile[]> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/search?q=${encodeURIComponent(query)}`,
		);
		if (!res.ok) throw new Error(`Failed to search files: ${res.status}`);
		const data = await res.json();
		return data.results;
	}
}

export const vfs = new VfsClient();
