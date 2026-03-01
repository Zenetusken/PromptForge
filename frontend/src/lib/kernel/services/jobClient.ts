/**
 * Kernel Job Queue client — REST API for background jobs.
 */

import { throwIfNotOk } from "$lib/kernel/utils/errors";

export interface JobRecord {
	id: string;
	app_id: string;
	job_type: string;
	payload: Record<string, unknown>;
	priority: number;
	status: "pending" | "running" | "completed" | "failed" | "cancelled";
	result: Record<string, unknown> | null;
	error: string | null;
	progress: number;
	max_retries: number;
	retry_count: number;
	created_at: string;
	started_at: string | null;
	completed_at: string | null;
}

export async function submitJob(
	appId: string,
	jobType: string,
	payload: Record<string, unknown> = {},
	priority = 0,
	maxRetries = 0,
): Promise<{ job_id: string; status: string; job: JobRecord | null }> {
	const resp = await fetch("/api/kernel/jobs/submit", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			app_id: appId,
			job_type: jobType,
			payload,
			priority,
			max_retries: maxRetries,
		}),
	});
	await throwIfNotOk(resp, "submit job");
	return resp.json();
}

export async function getJob(jobId: string): Promise<JobRecord> {
	const resp = await fetch(`/api/kernel/jobs/${jobId}`);
	await throwIfNotOk(resp, "get job");
	return resp.json();
}

export async function cancelJob(
	jobId: string,
): Promise<{ job_id: string; status: string }> {
	const resp = await fetch(`/api/kernel/jobs/${jobId}/cancel`, {
		method: "POST",
	});
	await throwIfNotOk(resp, "cancel job");
	return resp.json();
}

export async function listJobs(params?: {
	app_id?: string;
	status?: string;
	limit?: number;
}): Promise<{ jobs: JobRecord[]; total: number }> {
	const searchParams = new URLSearchParams();
	if (params?.app_id) searchParams.set("app_id", params.app_id);
	if (params?.status) searchParams.set("status", params.status);
	if (params?.limit) searchParams.set("limit", String(params.limit));
	const qs = searchParams.toString();
	const resp = await fetch(`/api/kernel/jobs${qs ? `?${qs}` : ""}`);
	await throwIfNotOk(resp, "list jobs");
	return resp.json();
}
