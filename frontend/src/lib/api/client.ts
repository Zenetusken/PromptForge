const BASE_URL = import.meta.env.VITE_API_URL
	? `${import.meta.env.VITE_API_URL}/api`
	: '/api';

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
	strategy_reasoning: string | null;
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

export interface HistorySummaryItem {
	id: string;
	created_at: string;
	raw_prompt: string;
	title: string | null;
	task_type: string | null;
	project: string | null;
	tags: string[] | null;
	overall_score: number | null;
	status: string;
	error_message: string | null;
}

export interface HistoryResponse {
	items: HistorySummaryItem[];
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
function isString(v: unknown): v is string {
	return typeof v === 'string';
}

function mapSSEEvent(eventType: string, data: Record<string, unknown>): PipelineEvent | null {
	switch (eventType) {
		case 'stage': {
			const stage = isString(data.stage) ? data.stage : '';
			const stepMap: Record<string, string> = {
				analyzing: 'analyze',
				optimizing: 'optimize',
				validating: 'validate'
			};
			return {
				type: 'step_start',
				step: stepMap[stage] || stage,
				message: isString(data.message) ? data.message : undefined
			};
		}
		case 'step_progress': {
			return {
				type: 'step_progress',
				step: isString(data.step) ? data.step : '',
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
				error: isString(data.error) ? data.error : 'Unknown error'
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

// ---------------------------------------------------------------------------
// Generic fetch helpers — single try-catch shared by all API functions
// ---------------------------------------------------------------------------

async function apiFetch<T>(
	url: string,
	fallback: T,
	options?: RequestInit & { fetchFn?: typeof fetch; signal?: AbortSignal }
): Promise<T> {
	try {
		const fetchFn = options?.fetchFn ?? fetch;
		const { fetchFn: _, signal, ...init } = options ?? {};
		const response = await fetchFn(url, { ...init, signal });
		if (!response.ok) return fallback;
		return await response.json();
	} catch (err) {
		if (err instanceof DOMException && err.name === 'AbortError') return fallback;
		console.warn('[PromptForge] API request failed:', url, err);
		return fallback;
	}
}

async function apiFetchOk(url: string, options?: RequestInit): Promise<boolean> {
	try {
		const response = await fetch(url, options);
		return response.ok;
	} catch (err) {
		if (err instanceof DOMException && err.name === 'AbortError') return false;
		console.warn('[PromptForge] API request failed:', url, err);
		return false;
	}
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

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
		signal?: AbortSignal;
	}
): Promise<HistoryResponse> {
	const searchParams = new URLSearchParams();
	if (params?.page) searchParams.set('page', String(params.page));
	if (params?.per_page) searchParams.set('per_page', String(params.per_page));
	if (params?.search) searchParams.set('search', params.search);
	if (params?.sort) searchParams.set('sort', params.sort);
	if (params?.order) searchParams.set('order', params.order);
	if (params?.task_type) searchParams.set('task_type', params.task_type);
	if (params?.project) searchParams.set('project', params.project);

	const qs = searchParams.toString();
	return apiFetch(`${BASE_URL}/history${qs ? '?' + qs : ''}`, { items: [], total: 0, page: 1, per_page: 20 }, { signal: params?.signal });
}

/**
 * Fetch a single optimization by ID.
 * Accepts a custom fetchFn for SSR deep-linking (SvelteKit load function).
 */
export async function fetchOptimization(id: string, fetchFn: typeof fetch = fetch): Promise<HistoryItem | null> {
	return apiFetch(`${BASE_URL}/optimize/${id}`, null, { fetchFn });
}

/** Delete an optimization from history */
export async function deleteOptimization(id: string): Promise<boolean> {
	return apiFetchOk(`${BASE_URL}/history/${id}`, { method: 'DELETE' });
}

/** Clear all history entries */
export async function clearAllHistory(): Promise<boolean> {
	return apiFetchOk(`${BASE_URL}/history/all`, { method: 'DELETE' });
}

/** Fetch usage statistics. */
export async function fetchStats(): Promise<StatsResponse | null> {
	return apiFetch(`${BASE_URL}/history/stats`, null);
}

export interface HealthResponse {
	status: string;
	claude_available: boolean;
	db_connected: boolean;
	version: string;
}

/** Fetch API health status. */
export async function fetchHealth(): Promise<HealthResponse | null> {
	return apiFetch(`${BASE_URL}/health`, null);
}
