/**
 * AppStorageClient — frontend wrapper for kernel document storage REST API.
 *
 * Provides CRUD operations for per-app collections and documents.
 */

import { API_BASE } from "$lib/api/client";

const BASE = `${API_BASE}/kernel/storage`;

export interface StorageCollection {
	id: string;
	app_id: string;
	name: string;
	parent_id: string | null;
	created_at: string;
	updated_at: string;
}

export interface StorageDocument {
	id: string;
	app_id: string;
	collection_id: string | null;
	name: string;
	content_type: string;
	content: string;
	metadata: Record<string, unknown> | null;
	created_at: string;
	updated_at: string;
}

class AppStorageClient {
	// --- Collections ---

	async listCollections(
		appId: string,
		parentId?: string,
	): Promise<StorageCollection[]> {
		const params = parentId ? `?parent_id=${encodeURIComponent(parentId)}` : "";
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/collections${params}`,
		);
		if (!res.ok) throw new Error(`Failed to list collections: ${res.status}`);
		const data = await res.json();
		return data.collections;
	}

	async createCollection(
		appId: string,
		name: string,
		parentId?: string,
	): Promise<StorageCollection> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/collections`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ name, parent_id: parentId ?? null }),
			},
		);
		if (!res.ok) throw new Error(`Failed to create collection: ${res.status}`);
		return res.json();
	}

	async deleteCollection(appId: string, collectionId: string): Promise<void> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/collections/${encodeURIComponent(collectionId)}`,
			{ method: "DELETE" },
		);
		if (!res.ok) throw new Error(`Failed to delete collection: ${res.status}`);
	}

	// --- Documents ---

	async listDocuments(
		appId: string,
		collectionId?: string,
	): Promise<StorageDocument[]> {
		const params = collectionId
			? `?collection_id=${encodeURIComponent(collectionId)}`
			: "";
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/documents${params}`,
		);
		if (!res.ok) throw new Error(`Failed to list documents: ${res.status}`);
		const data = await res.json();
		return data.documents;
	}

	async getDocument(
		appId: string,
		documentId: string,
	): Promise<StorageDocument> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/documents/${encodeURIComponent(documentId)}`,
		);
		if (!res.ok) throw new Error(`Failed to get document: ${res.status}`);
		return res.json();
	}

	async createDocument(
		appId: string,
		opts: {
			name: string;
			content: string;
			collectionId?: string;
			contentType?: string;
			metadata?: Record<string, unknown>;
		},
	): Promise<StorageDocument> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/documents`,
			{
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					name: opts.name,
					content: opts.content,
					collection_id: opts.collectionId ?? null,
					content_type: opts.contentType ?? "application/json",
					metadata: opts.metadata ?? null,
				}),
			},
		);
		if (!res.ok) throw new Error(`Failed to create document: ${res.status}`);
		return res.json();
	}

	async updateDocument(
		appId: string,
		documentId: string,
		opts: {
			name?: string;
			content?: string;
			contentType?: string;
			metadata?: Record<string, unknown>;
		},
	): Promise<StorageDocument> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/documents/${encodeURIComponent(documentId)}`,
			{
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					name: opts.name ?? null,
					content: opts.content ?? null,
					content_type: opts.contentType ?? null,
					metadata: opts.metadata ?? null,
				}),
			},
		);
		if (!res.ok) throw new Error(`Failed to update document: ${res.status}`);
		return res.json();
	}

	async deleteDocument(appId: string, documentId: string): Promise<void> {
		const res = await fetch(
			`${BASE}/${encodeURIComponent(appId)}/documents/${encodeURIComponent(documentId)}`,
			{ method: "DELETE" },
		);
		if (!res.ok) throw new Error(`Failed to delete document: ${res.status}`);
	}
}

export const appStorage = new AppStorageClient();
