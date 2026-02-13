const BASE_URL = import.meta.env.VITE_API_URL
	? `${import.meta.env.VITE_API_URL}/api`
	: '/api';

export interface OptimizationResult {
	id: string;
	optimized_prompt: string;
	raw_prompt: string;
	task_type: string;
	complexity: string;
	weaknesses: string[];
	strengths: string[];
	changes_made: string[];
	framework_applied: string;
	optimization_notes: string;
	clarity_score: number;
	specificity_score: number;
	structure_score: number;
	faithfulness_score: number;
	overall_score: number;
	is_improvement: boolean;
	verdict: string;
	duration_ms: number;
	model_used: string;
	status: string;
}

export interface HistoryItem {
	id: string;
	created_at: string;
	raw_prompt: string;
	optimized_prompt: string | null;
	task_type: string | null;
	complexity: string | null;
	weaknesses: string[] | null;
	strengths: string[] | null;
	changes_made: string[] | null;
	framework_applied: string | null;
	optimization_notes: string | null;
	clarity_score: number | null;
	specificity_score: number | null;
	structure_score: number | null;
	faithfulness_score: number | null;
	overall_score: number | null;
	is_improvement: boolean | null;
	verdict: string | null;
	duration_ms: number | null;
	model_used: string | null;
	status: string;
	error_message: string | null;
	project: string | null;
	tags: string[] | null;
	title: string | null;
}

export interface HistoryResponse {
	items: HistoryItem[];
	total: number;
	page: number;
	per_page: number;
}

export interface PipelineEvent {
	type: 'step_start' | 'step_complete' | 'step_progress' | 'step_error' | 'result' | 'error';
	step?: string;
	data?: Record<string, unknown>;
	error?: string;
	message?: string;
}

export interface OptimizeMetadata {
	title?: string;
	project?: string;
	tags?: string[];
}

export interface StatsResponse {
	total_optimizations: number;
	average_overall_score: number | null;
	average_clarity_score: number | null;
	average_specificity_score: number | null;
	average_structure_score: number | null;
	average_faithfulness_score: number | null;
	improvement_rate: number | null;
	total_projects: number;
	most_common_task_type: string | null;
	optimizations_today: number;
}

/**
 * Map backend SSE event types to frontend PipelineEvent types.
 * Backend sends: event: stage|analysis|optimization|validation|complete
 * Frontend expects: step_start|step_complete|step_progress|result|error
 */
function mapSSEEvent(eventType: string, data: Record<string, unknown>): PipelineEvent | null {
	switch (eventType) {
		case 'stage': {
			const stage = data.stage as string;
			// Map stage names to step names
			const stepMap: Record<string, string> = {
				analyzing: 'analyze',
				optimizing: 'optimize',
				validating: 'validate'
			};
			return {
				type: 'step_start',
				step: stepMap[stage] || stage,
				message: data.message as string
			};
		}
		case 'step_progress': {
			return {
				type: 'step_progress',
				step: data.step as string,
				data: data
			};
		}
		case 'analysis': {
			return {
				type: 'step_complete',
				step: 'analyze',
				data: data
			};
		}
		case 'optimization': {
			return {
				type: 'step_complete',
				step: 'optimize',
				data: data
			};
		}
		case 'validation': {
			return {
				type: 'step_complete',
				step: 'validate',
				data: data
			};
		}
		case 'complete': {
			return {
				type: 'result',
				data: data
			};
		}
		case 'error': {
			return {
				type: 'error',
				error: (data.error as string) || 'Unknown error'
			};
		}
		default:
			return null;
	}
}

/**
 * Open an SSE stream from a fetch request and dispatch parsed events.
 * Shared by fetchOptimize and fetchRetry.
 */
function openSSEStream(
	url: string,
	init: RequestInit,
	onEvent: (event: PipelineEvent) => void,
	onError?: (error: Error) => void
): AbortController {
	const controller = new AbortController();

	fetch(url, { ...init, signal: controller.signal })
		.then(async (response) => {
			if (!response.ok) {
				throw new Error(`HTTP ${response.status}: ${response.statusText}`);
			}

			const reader = response.body?.getReader();
			if (!reader) {
				throw new Error('No response body');
			}

			const decoder = new TextDecoder();
			let buffer = '';
			let currentEventType = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';

				for (const line of lines) {
					const trimmed = line.trim();
					if (trimmed.startsWith('event: ')) {
						currentEventType = trimmed.slice(7).trim();
					} else if (trimmed.startsWith('data: ')) {
						try {
							const data = JSON.parse(trimmed.slice(6));
							const mapped = mapSSEEvent(currentEventType || 'unknown', data);
							if (mapped) {
								onEvent(mapped);
							}
						} catch {
							// Skip malformed JSON
						}
						currentEventType = '';
					} else if (trimmed === '') {
						currentEventType = '';
					}
				}
			}
		})
		.catch((err) => {
			if (err.name !== 'AbortError') {
				onError?.(err);
			}
		});

	return controller;
}

/**
 * Opens an SSE connection to the optimization endpoint.
 */
export function fetchOptimize(
	prompt: string,
	onEvent: (event: PipelineEvent) => void,
	onError?: (error: Error) => void,
	metadata?: OptimizeMetadata
): AbortController {
	return openSSEStream(
		`${BASE_URL}/optimize`,
		{ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt, ...metadata }) },
		onEvent,
		onError
	);
}

/**
 * Retry an existing optimization via the backend retry endpoint.
 * Preserves project/tags metadata from the original.
 */
export function fetchRetry(
	id: string,
	onEvent: (event: PipelineEvent) => void,
	onError?: (error: Error) => void
): AbortController {
	return openSSEStream(
		`${BASE_URL}/optimize/${id}/retry`,
		{ method: 'POST' },
		onEvent,
		onError
	);
}

/**
 * Fetch optimization history
 */
export async function fetchHistory(
	params?: {
		page?: number;
		per_page?: number;
		search?: string;
		sort?: string;
		order?: string;
		task_type?: string;
		project?: string;
	}
): Promise<HistoryResponse> {
	try {
		const searchParams = new URLSearchParams();
		if (params?.page) searchParams.set('page', String(params.page));
		if (params?.per_page) searchParams.set('per_page', String(params.per_page));
		if (params?.search) searchParams.set('search', params.search);
		if (params?.sort) searchParams.set('sort', params.sort);
		if (params?.order) searchParams.set('order', params.order);
		if (params?.task_type) searchParams.set('task_type', params.task_type);
		if (params?.project) searchParams.set('project', params.project);

		const url = `${BASE_URL}/history${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
		const response = await fetch(url);
		if (!response.ok) return { items: [], total: 0, page: 1, per_page: 20 };
		return await response.json();
	} catch {
		return { items: [], total: 0, page: 1, per_page: 20 };
	}
}

/**
 * Fetch a single optimization by ID.
 * Currently unused — available for future deep-linking to individual results.
 */
export async function fetchOptimization(id: string, fetchFn: typeof fetch = fetch): Promise<HistoryItem | null> {
	try {
		const response = await fetchFn(`${BASE_URL}/optimize/${id}`);
		if (!response.ok) return null;
		return await response.json();
	} catch {
		return null;
	}
}

/**
 * Delete an optimization from history
 */
export async function deleteOptimization(id: string): Promise<boolean> {
	try {
		const response = await fetch(`${BASE_URL}/history/${id}`, {
			method: 'DELETE'
		});
		return response.ok;
	} catch {
		return false;
	}
}

/**
 * Clear all history entries
 */
export async function clearAllHistory(): Promise<boolean> {
	try {
		const response = await fetch(`${BASE_URL}/history/all`, {
			method: 'DELETE'
		});
		return response.ok;
	} catch {
		return false;
	}
}

/**
 * Fetch usage statistics.
 */
export async function fetchStats(): Promise<StatsResponse | null> {
	try {
		const response = await fetch(`${BASE_URL}/history/stats`);
		if (!response.ok) return null;
		return await response.json();
	} catch {
		return null;
	}
}

export interface HealthResponse {
	status: string;
	claude_available: boolean;
	db_connected: boolean;
	version: string;
}

/**
 * Fetch API health status.
 */
export async function fetchHealth(): Promise<HealthResponse | null> {
	try {
		const response = await fetch(`${BASE_URL}/health`);
		if (!response.ok) return null;
		return await response.json();
	} catch {
		return null;
	}
}
