/**
 * App Manager Client — frontend wrapper for kernel app management REST API.
 */

import { throwIfNotOk } from '$lib/kernel/utils/errors';

const API_BASE = import.meta.env.VITE_API_URL || '';

export interface KernelApp {
	id: string;
	name: string;
	version: string;
	status: string;
	icon?: string;
	accent_color?: string;
	services_satisfied?: boolean;
	/** Number of windows declared in manifest */
	windows?: number;
	/** Number of routers declared in manifest */
	routers?: number;
	capabilities?: { required: string[]; optional: string[] };
	resource_quotas?: Record<string, number>;
	error?: string;
}

export async function fetchApps(): Promise<{ apps: KernelApp[] }> {
	const res = await fetch(`${API_BASE}/api/kernel/apps`);
	await throwIfNotOk(res, 'fetchApps');
	return res.json();
}

export async function fetchAppStatus(appId: string): Promise<KernelApp> {
	const res = await fetch(`${API_BASE}/api/kernel/apps/${appId}/status`);
	await throwIfNotOk(res, 'fetchAppStatus');
	return res.json();
}

export async function enableApp(appId: string): Promise<void> {
	const res = await fetch(`${API_BASE}/api/kernel/apps/${appId}/enable`, { method: 'POST' });
	await throwIfNotOk(res, 'enableApp');
}

export async function disableApp(appId: string): Promise<void> {
	const res = await fetch(`${API_BASE}/api/kernel/apps/${appId}/disable`, { method: 'POST' });
	await throwIfNotOk(res, 'disableApp');
}
