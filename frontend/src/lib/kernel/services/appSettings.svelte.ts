/**
 * AppSettingsService — reactive wrapper for per-app settings via kernel REST API.
 *
 * Provides load/save/reset operations with a local $state cache.
 */

import { API_BASE } from "$lib/api/client";
import { throwIfNotOk } from "$lib/kernel/utils/errors";

const BASE = `${API_BASE}/api/kernel/settings`;

class AppSettingsService {
	/** Cache of loaded settings keyed by app ID. */
	private _cache = $state<Record<string, Record<string, unknown>>>({});

	/** Loading states per app. */
	private _loading = $state<Record<string, boolean>>({});

	/** Get cached settings for an app (returns empty object if not loaded). */
	get(appId: string): Record<string, unknown> {
		return this._cache[appId] ?? {};
	}

	/** Check if settings are loading for an app. */
	isLoading(appId: string): boolean {
		return this._loading[appId] ?? false;
	}

	/** Load settings for an app from the backend. */
	async load(appId: string): Promise<Record<string, unknown>> {
		this._loading[appId] = true;
		try {
			const res = await fetch(`${BASE}/${encodeURIComponent(appId)}`);
			await throwIfNotOk(res, "load settings");
			const data = await res.json();
			this._cache[appId] = data.settings ?? {};
			return this._cache[appId];
		} finally {
			this._loading[appId] = false;
		}
	}

	/** Save settings for an app (merge with existing). */
	async save(appId: string, settings: Record<string, unknown>): Promise<void> {
		const res = await fetch(`${BASE}/${encodeURIComponent(appId)}`, {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ settings }),
		});
		await throwIfNotOk(res, "save settings");
		const data = await res.json();
		this._cache[appId] = data.settings ?? {};
	}

	/** Reset all settings for an app. */
	async reset(appId: string): Promise<void> {
		const res = await fetch(`${BASE}/${encodeURIComponent(appId)}`, {
			method: "DELETE",
		});
		await throwIfNotOk(res, "reset settings");
		await res.json(); // Consume response body
		this._cache[appId] = {};
	}
}

export const appSettings = new AppSettingsService();
