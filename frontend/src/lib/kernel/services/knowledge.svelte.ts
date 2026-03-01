/**
 * KnowledgeService — reactive wrapper for the kernel Knowledge Base REST API.
 *
 * Follows the appSettings.svelte.ts pattern: class with $state cache, exported singleton.
 * Provides profile and source CRUD with per-entity caching.
 */

import { API_BASE } from "$lib/api/client";
import { throwIfNotOk } from "$lib/kernel/utils/errors";
import type { KnowledgeProfile, KnowledgeSource } from "$lib/kernel/types";

const BASE = `${API_BASE}/api/kernel/knowledge`;

class KnowledgeService {
	/** Profile cache keyed by "appId:entityId". */
	private _profiles = $state<Record<string, KnowledgeProfile | null>>({});

	/** Source list cache keyed by "appId:entityId". */
	private _sources = $state<Record<string, KnowledgeSource[]>>({});

	/** Loading states per entity. */
	private _loading = $state<Record<string, boolean>>({});

	private _key(appId: string, entityId: string): string {
		return `${appId}:${entityId}`;
	}

	/** Get cached profile (returns null if not loaded or missing). */
	getCachedProfile(appId: string, entityId: string): KnowledgeProfile | null {
		return this._profiles[this._key(appId, entityId)] ?? null;
	}

	/** Get cached sources (returns empty if not loaded). */
	getCachedSources(appId: string, entityId: string): KnowledgeSource[] {
		return this._sources[this._key(appId, entityId)] ?? [];
	}

	/** Check if data is loading for an entity. */
	isLoading(appId: string, entityId: string): boolean {
		return this._loading[this._key(appId, entityId)] ?? false;
	}

	/** Fetch profile from backend (via resolve endpoint). Returns null if no profile exists. */
	async getProfile(appId: string, entityId: string): Promise<KnowledgeProfile | null> {
		const key = this._key(appId, entityId);
		this._loading[key] = true;
		try {
			const res = await fetch(`${BASE}/${enc(appId)}/${enc(entityId)}`);
			if (res.status === 404) {
				this._profiles[key] = null;
				return null;
			}
			await throwIfNotOk(res, "get knowledge profile");
			const data = await res.json();
			if (!data.profile) {
				this._profiles[key] = null;
				return null;
			}
			// Compose full KnowledgeProfile from resolve response
			const profile: KnowledgeProfile = {
				...data.profile,
				metadata: data.metadata ?? {},
				auto_detected: data.auto_detected ?? {},
				created_at: data.profile.created_at ?? "",
				updated_at: data.profile.updated_at ?? "",
			};
			this._profiles[key] = profile;
			if (data.sources) {
				this._sources[key] = data.sources;
			}
			return profile;
		} finally {
			this._loading[key] = false;
		}
	}

	/** Create or update profile fields. */
	async updateProfile(
		appId: string,
		entityId: string,
		fields: Partial<Pick<KnowledgeProfile, "name" | "language" | "framework" | "description" | "test_framework">>
			& { metadata_json?: Record<string, unknown> },
	): Promise<KnowledgeProfile> {
		const key = this._key(appId, entityId);
		const res = await fetch(`${BASE}/${enc(appId)}/${enc(entityId)}`, {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(fields),
		});
		await throwIfNotOk(res, "update knowledge profile");
		const data = await res.json();
		this._profiles[key] = data;
		return data;
	}

	/** List sources for a profile. */
	async getSources(
		appId: string,
		entityId: string,
		opts?: { enabledOnly?: boolean },
	): Promise<KnowledgeSource[]> {
		const key = this._key(appId, entityId);
		this._loading[key] = true;
		try {
			const params = opts?.enabledOnly ? "?enabled_only=true" : "";
			const res = await fetch(`${BASE}/${enc(appId)}/${enc(entityId)}/sources${params}`);
			if (res.status === 404) {
				this._sources[key] = [];
				return [];
			}
			await throwIfNotOk(res, "list knowledge sources");
			const data = await res.json();
			const items = data.items ?? [];
			this._sources[key] = items;
			return items;
		} finally {
			this._loading[key] = false;
		}
	}

	/** Add a source to a profile. */
	async addSource(
		appId: string,
		entityId: string,
		data: { title: string; content: string; source_type?: string },
	): Promise<KnowledgeSource> {
		const key = this._key(appId, entityId);
		const res = await fetch(`${BASE}/${enc(appId)}/${enc(entityId)}/sources`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(data),
		});
		await throwIfNotOk(res, "add knowledge source");
		const source = await res.json();
		// Refresh cache
		const existing = this._sources[key] ?? [];
		this._sources[key] = [...existing, source];
		return source;
	}

	/** Update a source. Updates the cache entry in-place if found. */
	async updateSource(
		sourceId: string,
		data: Partial<Pick<KnowledgeSource, "title" | "content" | "enabled">>,
	): Promise<KnowledgeSource> {
		const res = await fetch(`${BASE}/sources/${enc(sourceId)}`, {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(data),
		});
		await throwIfNotOk(res, "update knowledge source");
		const updated: KnowledgeSource = await res.json();
		this._updateSourceInCache(updated);
		return updated;
	}

	/** Delete a source. Removes from cache. */
	async deleteSource(sourceId: string): Promise<void> {
		const res = await fetch(`${BASE}/sources/${enc(sourceId)}`, {
			method: "DELETE",
		});
		await throwIfNotOk(res, "delete knowledge source");
		this._removeSourceFromCache(sourceId);
	}

	/** Toggle a source's enabled state. Updates cache. */
	async toggleSource(sourceId: string): Promise<KnowledgeSource> {
		const res = await fetch(`${BASE}/sources/${enc(sourceId)}/toggle`, {
			method: "POST",
		});
		await throwIfNotOk(res, "toggle knowledge source");
		const updated: KnowledgeSource = await res.json();
		this._updateSourceInCache(updated);
		return updated;
	}

	/** Invalidate cached data for an entity. */
	invalidate(appId: string, entityId: string): void {
		const key = this._key(appId, entityId);
		delete this._profiles[key];
		delete this._sources[key];
	}

	/** Replace a source in any cached sources list (keyed by profile_id match). */
	private _updateSourceInCache(updated: KnowledgeSource): void {
		for (const [key, sources] of Object.entries(this._sources)) {
			const idx = sources.findIndex((s) => s.id === updated.id);
			if (idx !== -1) {
				this._sources[key] = sources.map((s) => (s.id === updated.id ? updated : s));
				return;
			}
		}
	}

	/** Remove a source from any cached sources list. */
	private _removeSourceFromCache(sourceId: string): void {
		for (const [key, sources] of Object.entries(this._sources)) {
			const idx = sources.findIndex((s) => s.id === sourceId);
			if (idx !== -1) {
				this._sources[key] = sources.filter((s) => s.id !== sourceId);
				return;
			}
		}
	}
}

function enc(s: string): string {
	return encodeURIComponent(s);
}

export const knowledge = new KnowledgeService();
