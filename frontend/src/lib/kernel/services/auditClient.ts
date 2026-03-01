/**
 * Audit Client — frontend wrapper for kernel audit log REST API.
 */

import { throwIfNotOk } from '$lib/kernel/utils/errors';

const API_BASE = import.meta.env.VITE_API_URL || '';

export interface AuditLogEntry {
	id: number;
	app_id: string;
	action: string;
	resource_type: string;
	resource_id: string | null;
	details: Record<string, unknown> | null;
	timestamp: string;
}

export interface AuditSummaryEntry {
	app_id: string;
	action: string;
	count: number;
}

export interface AppUsageEntry {
	app_id: string;
	resource: string;
	count: number;
	period: string;
	updated_at: string;
}

export async function fetchAuditLogs(
	appId?: string,
	limit = 50,
	offset = 0,
	action?: string,
	resourceType?: string,
): Promise<{ logs: AuditLogEntry[]; total: number }> {
	const params = new URLSearchParams();
	params.set('limit', String(limit));
	params.set('offset', String(offset));
	if (action) params.set('action', action);
	if (resourceType) params.set('resource_type', resourceType);

	const path = appId
		? `${API_BASE}/api/kernel/audit/${appId}?${params}`
		: `${API_BASE}/api/kernel/audit/all?${params}`;

	const res = await fetch(path);
	await throwIfNotOk(res, 'fetchAuditLogs');
	return res.json();
}

export async function fetchAuditSummary(): Promise<{ summary: AuditSummaryEntry[] }> {
	const res = await fetch(`${API_BASE}/api/kernel/audit/summary`);
	await throwIfNotOk(res, 'fetchAuditSummary');
	return res.json();
}

export async function fetchAppUsage(appId: string): Promise<{ app_id: string; usage: AppUsageEntry[] }> {
	const res = await fetch(`${API_BASE}/api/kernel/audit/usage/${appId}`);
	await throwIfNotOk(res, 'fetchAppUsage');
	return res.json();
}

export async function fetchAllUsage(): Promise<{ usage: AppUsageEntry[] }> {
	const res = await fetch(`${API_BASE}/api/kernel/audit/usage`);
	await throwIfNotOk(res, 'fetchAllUsage');
	return res.json();
}
