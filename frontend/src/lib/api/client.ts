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
	strategy: string | null;
	strategy_reasoning: string | null;
	strategy_confidence: number | null;
	secondary_frameworks: string[] | null;
	clarity_score: number | null;
	specificity_score: number | null;
	structure_score: number | null;
	faithfulness_score: number | null;
	overall_score: number | null;
	is_improvement: boolean | null;
	verdict: string | null;
	duration_ms: number | null;
	model_used: string | null;
	input_tokens: number | null;
	output_tokens: number | null;
	cache_creation_input_tokens: number | null;
	cache_read_input_tokens: number | null;
	status: string;
	error_message: string | null;
	project: string | null;
	tags: string[] | null;
	title: string | null;
	version: string | null;
	prompt_id: string | null;
	project_id: string | null;
	project_status: string | null;
	codebase_context_snapshot: CodebaseContext | null;
}

export interface HistorySummaryItem {
	id: string;
	created_at: string;
	raw_prompt: string;
	title: string | null;
	version: string | null;
	task_type: string | null;
	complexity: string | null;
	project: string | null;
	tags: string[] | null;
	overall_score: number | null;
	strategy: string | null;
	secondary_frameworks: string[] | null;
	framework_applied: string | null;
	model_used: string | null;
	status: string;
	error_message: string | null;
	prompt_id: string | null;
	project_id: string | null;
	project_status: string | null;
}

export interface HistoryResponse {
	items: HistorySummaryItem[];
	total: number;
	page: number;
	per_page: number;
}

export interface PipelineEvent {
	type: 'step_start' | 'step_complete' | 'step_progress' | 'step_error' | 'strategy_selected' | 'iteration' | 'result' | 'error';
	step?: string;
	data?: Record<string, unknown>;
	error?: string;
	errorType?: string;
	retryAfter?: number;
	message?: string;
}

export interface CodebaseContext {
	language?: string;
	framework?: string;
	description?: string;
	conventions?: string[];
	patterns?: string[];
	code_snippets?: string[];
	documentation?: string;
	test_framework?: string;
	test_patterns?: string[];
}

export interface OptimizeMetadata {
	title?: string;
	project?: string;
	tags?: string[];
	version?: string;
	provider?: string;
	strategy?: string;
	secondary_frameworks?: string[];
	prompt_id?: string;
	codebase_context?: CodebaseContext;
	max_iterations?: number;
	score_threshold?: number;
}

export interface ScoreMatrixEntry {
	count: number;
	avg_score: number | null;
}

export interface ScoreVarianceEntry {
	min: number;
	max: number;
	avg: number;
	stddev: number;
	count: number;
}

export interface ComboEntry {
	count: number;
	avg_score: number | null;
}

export interface ImprovementEntry {
	improved: number;
	validated: number;
	rate: number | null;
}

export interface ErrorRateEntry {
	total: number;
	errors: number;
	rate: number;
}

export interface TrendEntry {
	count: number;
	avg_score: number | null;
}

export interface TokenEntry {
	avg_input_tokens: number | null;
	avg_output_tokens: number | null;
	avg_duration_ms: number | null;
}

export interface WinRateEntry {
	strategy: string;
	avg_score: number;
	count: number;
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
	strategy_distribution: Record<string, number> | null;
	score_by_strategy: Record<string, number> | null;
	task_types_by_strategy: Record<string, Record<string, number>> | null;
	secondary_strategy_distribution: Record<string, number> | null;
	tags_by_strategy: Record<string, Record<string, number>> | null;
	// Extended analytics
	score_matrix: Record<string, Record<string, ScoreMatrixEntry>> | null;
	score_variance: Record<string, ScoreVarianceEntry> | null;
	confidence_by_strategy: Record<string, number> | null;
	combo_effectiveness: Record<string, Record<string, ComboEntry>> | null;
	complexity_performance: Record<string, Record<string, ScoreMatrixEntry>> | null;
	improvement_by_strategy: Record<string, ImprovementEntry> | null;
	error_rates: Record<string, ErrorRateEntry> | null;
	trend_7d: TrendEntry | null;
	trend_30d: TrendEntry | null;
	token_economics: Record<string, TokenEntry> | null;
	win_rates: Record<string, WinRateEntry> | null;
}

/**
 * Map backend SSE event types to frontend PipelineEvent types.
 * Backend sends: stage|strategy|step_progress|analysis|optimization|validation|complete|error
 * Frontend expects: step_start|step_complete|step_progress|result|error
 */
function isString(v: unknown): v is string {
	return typeof v === 'string';
}

export function mapSSEEvent(eventType: string, data: Record<string, unknown>): PipelineEvent | null {
	switch (eventType) {
		case 'stage': {
			const stage = isString(data.stage) ? data.stage : '';
			const stepMap: Record<string, string> = {
				analyzing: 'analyze',
				strategizing: 'strategy',
				optimizing: 'optimize',
				validating: 'validate'
			};
			return {
				type: 'step_start',
				step: stepMap[stage] || stage,
				message: isString(data.message) ? data.message : undefined
			};
		}
		case 'strategy': {
			return {
				type: 'strategy_selected',
				data: data
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
		case 'iteration': {
			return {
				type: 'iteration',
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
				error: isString(data.error) ? data.error : 'Unknown error',
				errorType: isString(data.error_type) ? data.error_type : undefined,
				retryAfter: typeof data.retry_after === 'number' ? data.retry_after : undefined,
			};
		}
		default:
			return null;
	}
}

/** Maximum time (ms) to wait for an SSE event before aborting. */
const SSE_READ_TIMEOUT_MS = 120_000;

function processSSELines(
	lines: string[],
	currentEventType: string,
	onEvent: (event: PipelineEvent) => void,
): string {
	let eventType = currentEventType;
	for (const line of lines) {
		const trimmed = line.trim();
		if (trimmed.startsWith('event: ')) {
			eventType = trimmed.slice(7).trim();
		} else if (trimmed.startsWith('data: ')) {
			try {
				const data = JSON.parse(trimmed.slice(6));
				const mapped = mapSSEEvent(eventType || 'unknown', data);
				if (mapped) {
					onEvent(mapped);
				}
			} catch {
				console.warn('[PromptForge] Malformed SSE data, skipping:', trimmed.slice(6, 200));
			}
			eventType = '';
		} else if (trimmed === '') {
			eventType = '';
		}
	}
	return eventType;
}

function openSSEStream(
	url: string,
	init: RequestInit,
	onEvent: (event: PipelineEvent) => void,
	onError?: (error: Error) => void
): AbortController {
	const controller = new AbortController();
	let readTimer: ReturnType<typeof setTimeout> | undefined;

	fetch(url, { ...init, signal: controller.signal, headers: { ...buildAuthHeaders(), ...init.headers } })
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

			const resetReadTimer = () => {
				clearTimeout(readTimer);
				readTimer = setTimeout(() => {
					controller.abort();
					onError?.(new Error('SSE read timeout: no events received for 120s'));
				}, SSE_READ_TIMEOUT_MS);
			};

			resetReadTimer();

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				resetReadTimer();
				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';
				currentEventType = processSSELines(lines, currentEventType, onEvent);
			}

			clearTimeout(readTimer);

			// Flush any remaining buffered content after stream ends
			if (buffer.trim()) {
				processSSELines([buffer], currentEventType, onEvent);
			}
		})
		.catch((err) => {
			clearTimeout(readTimer);
			if (!(err instanceof DOMException && err.name === 'AbortError')) {
				onError?.(err);
			}
		});

	return controller;
}

/**
 * Build HTTP headers for LLM runtime overrides (API key, model, provider)
 * and optional authentication. Keys are sent via headers to keep them out
 * of request bodies and logs.
 */
function buildLLMHeaders(llm?: LLMHeaders): Record<string, string> {
	const headers: Record<string, string> = {};
	if (llm?.apiKey) headers['X-LLM-API-Key'] = llm.apiKey;
	if (llm?.model) headers['X-LLM-Model'] = llm.model;
	if (llm?.provider) headers['X-LLM-Provider'] = llm.provider;
	return headers;
}

/**
 * Return an Authorization header if AUTH_TOKEN is configured.
 * The token is read from the VITE_AUTH_TOKEN env var at build time.
 */
function buildAuthHeaders(): Record<string, string> {
	const token = import.meta.env.VITE_AUTH_TOKEN;
	if (token) return { Authorization: `Bearer ${token}` };
	return {};
}

/**
 * Opens an SSE connection to the optimization endpoint.
 */
export function fetchOptimize(
	prompt: string,
	onEvent: (event: PipelineEvent) => void,
	onError?: (error: Error) => void,
	metadata?: OptimizeMetadata,
	llmHeaders?: LLMHeaders
): AbortController {
	return openSSEStream(
		`${BASE_URL}/optimize`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...buildLLMHeaders(llmHeaders) },
			body: JSON.stringify({ prompt, ...metadata })
		},
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
	onError?: (error: Error) => void,
	llmHeaders?: LLMHeaders
): AbortController {
	return openSSEStream(
		`${BASE_URL}/optimize/${id}/retry`,
		{ method: 'POST', headers: { ...buildLLMHeaders(llmHeaders) } },
		onEvent,
		onError
	);
}

// ---------------------------------------------------------------------------
// Modular Orchestration API
// ---------------------------------------------------------------------------

export interface AnalyzeRequest {
	prompt: string;
	codebase_context?: CodebaseContext | null;
}

export interface StrategyRequest {
	prompt: string;
	analysis: Record<string, unknown>;
	codebase_context?: CodebaseContext | null;
}

export interface OptimizeGenerateRequest {
	prompt: string;
	analysis: Record<string, unknown>;
	strategy: string;
	secondary_frameworks?: string[];
	codebase_context?: CodebaseContext | null;
}

export interface ValidateRequest {
	original_prompt: string;
	optimized_prompt: string;
	codebase_context?: CodebaseContext | null;
}

export interface AnalyzeResponse {
	task_type: string;
	complexity: string;
	weaknesses: string[];
	strengths: string[];
	step_duration_ms?: number;
}

export interface StrategyResponse {
	strategy: string;
	reasoning: string;
	confidence: number;
	task_type: string;
	is_override: boolean;
	secondary_frameworks: string[];
	step_duration_ms?: number;
}

export interface OptimizeResponse {
	optimized_prompt: string;
	framework_applied: string;
	changes_made: string[];
	optimization_notes: string;
	step_duration_ms?: number;
}

export interface ValidateResponse {
	clarity_score: number;
	specificity_score: number;
	structure_score: number;
	faithfulness_score: number;
	overall_score: number;
	is_improvement: boolean;
	verdict: string;
	step_duration_ms?: number;
}

export async function orchestrateAnalyze(req: AnalyzeRequest, llmHeaders?: LLMHeaders): Promise<AnalyzeResponse> {
	return apiFetchOrThrow<AnalyzeResponse>(`${BASE_URL}/orchestrate/analyze`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...buildLLMHeaders(llmHeaders) },
		body: JSON.stringify(req)
	});
}

export async function orchestrateStrategy(req: StrategyRequest, llmHeaders?: LLMHeaders): Promise<StrategyResponse> {
	return apiFetchOrThrow<StrategyResponse>(`${BASE_URL}/orchestrate/strategy`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...buildLLMHeaders(llmHeaders) },
		body: JSON.stringify(req)
	});
}

export async function orchestrateOptimize(req: OptimizeGenerateRequest, llmHeaders?: LLMHeaders): Promise<OptimizeResponse> {
	return apiFetchOrThrow<OptimizeResponse>(`${BASE_URL}/orchestrate/optimize`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...buildLLMHeaders(llmHeaders) },
		body: JSON.stringify(req)
	});
}

export async function orchestrateValidate(req: ValidateRequest, llmHeaders?: LLMHeaders): Promise<ValidateResponse> {
	return apiFetchOrThrow<ValidateResponse>(`${BASE_URL}/orchestrate/validate`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...buildLLMHeaders(llmHeaders) },
		body: JSON.stringify(req)
	});
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
		const headers = { ...buildAuthHeaders(), ...(init.headers as Record<string, string>) };
		const response = await fetchFn(url, { ...init, headers, signal });
		if (!response.ok) return fallback;
		return await response.json();
	} catch (err) {
		if (err instanceof DOMException && err.name === 'AbortError') return fallback;
		console.warn('[PromptForge] API request failed:', url, err);
		return fallback;
	}
}

/** Throwing variant for POST endpoints where failure should be an error (not silent null). */
async function apiFetchOrThrow<T>(url: string, options?: RequestInit): Promise<T> {
	const headers = { ...buildAuthHeaders(), ...(options?.headers as Record<string, string>) };
	const response = await fetch(url, { ...options, headers });
	if (!response.ok) {
		let detail = `HTTP ${response.status}`;
		try {
			const body = await response.json();
			if (body.detail) detail = body.detail;
		} catch { /* use status code */ }
		throw new Error(detail);
	}
	return await response.json();
}

async function apiFetchOk(url: string, options?: RequestInit): Promise<boolean> {
	try {
		const headers = { ...buildAuthHeaders(), ...(options?.headers as Record<string, string>) };
		const response = await fetch(url, { ...options, headers });
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
		project_id?: string;
		include_archived?: boolean;
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
	if (params?.project_id) searchParams.set('project_id', params.project_id);
	if (params?.include_archived !== undefined) searchParams.set('include_archived', String(params.include_archived));

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
	return apiFetchOk(`${BASE_URL}/history/all`, {
		method: 'DELETE',
		headers: { 'X-Confirm-Delete': 'yes' },
	});
}

/** Fetch usage statistics. */
export async function fetchStats(project?: string): Promise<StatsResponse | null> {
	const params = project ? `?project=${encodeURIComponent(project)}` : '';
	return apiFetch(`${BASE_URL}/history/stats${params}`, null);
}

export interface TokenBudgetStatus {
	input_tokens_used: number;
	output_tokens_used: number;
	total_tokens_used: number;
	request_count: number;
	daily_limit: number | null;
	remaining: number | null;
}

export interface HealthResponse {
	status: string;
	claude_available: boolean;
	llm_available: boolean;
	llm_provider: string;
	llm_model: string;
	db_connected: boolean;
	mcp_connected: boolean;
	version: string;
	token_budgets?: Record<string, TokenBudgetStatus>;
}

/** Fetch API health status. */
export async function fetchHealth(): Promise<HealthResponse | null> {
	return apiFetch(`${BASE_URL}/health`, null);
}

export interface ModelInfo {
	id: string;
	name: string;
	description: string;
	context_window: number;
	tier: string;
}

export interface ProviderInfo {
	name: string;
	display_name: string;
	model: string;
	available: boolean;
	is_default: boolean;
	requires_api_key: boolean;
	models: ModelInfo[];
}

export interface LLMHeaders {
	apiKey?: string;
	model?: string;
	provider?: string;
}

/** Fetch all registered LLM providers with availability status. */
export async function fetchProviders(): Promise<ProviderInfo[]> {
	return apiFetch(`${BASE_URL}/providers`, []);
}

export interface ValidateKeyResponse {
	valid: boolean;
	error: string | null;
	provider_name: string | null;
	model: string | null;
}

/** Validate an API key by testing actual provider connectivity. */
export async function validateApiKey(provider: string, apiKey: string): Promise<ValidateKeyResponse> {
	return apiFetch(`${BASE_URL}/providers/validate-key`, { valid: false, error: 'Request failed', provider_name: null, model: null }, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ provider, api_key: apiKey }),
	});
}

// ---------------------------------------------------------------------------
// Projects API
// ---------------------------------------------------------------------------

export interface LatestForgeInfo {
	id: string;
	title: string | null;
	task_type: string | null;
	complexity: string | null;
	framework_applied: string | null;
	overall_score: number | null;
	is_improvement: boolean | null;
	tags: string[];
	version: string | null;
}

export interface ProjectPrompt {
	id: string;
	content: string;
	version: number;
	project_id: string;
	order_index: number;
	created_at: string;
	updated_at: string;
	forge_count: number;
	latest_forge: LatestForgeInfo | null;
}

export interface ProjectSummary {
	id: string;
	name: string;
	description: string | null;
	status: string;
	prompt_count: number;
	has_context: boolean;
	created_at: string;
	updated_at: string;
}

export interface ProjectDetail {
	id: string;
	name: string;
	description: string | null;
	context_profile: CodebaseContext | null;
	status: string;
	created_at: string;
	updated_at: string;
	prompts: ProjectPrompt[];
}

export interface ProjectListResponse {
	items: ProjectSummary[];
	total: number;
	page: number;
	per_page: number;
}

export async function fetchProjects(params?: {
	page?: number;
	per_page?: number;
	search?: string;
	status?: string;
	sort?: string;
	order?: string;
	signal?: AbortSignal;
}): Promise<ProjectListResponse> {
	const searchParams = new URLSearchParams();
	if (params?.page) searchParams.set('page', String(params.page));
	if (params?.per_page) searchParams.set('per_page', String(params.per_page));
	if (params?.search) searchParams.set('search', params.search);
	if (params?.status) searchParams.set('status', params.status);
	if (params?.sort) searchParams.set('sort', params.sort);
	if (params?.order) searchParams.set('order', params.order);

	const qs = searchParams.toString();
	return apiFetch(
		`${BASE_URL}/projects${qs ? '?' + qs : ''}`,
		{ items: [], total: 0, page: 1, per_page: 20 },
		{ signal: params?.signal },
	);
}

export async function fetchProject(id: string, fetchFn: typeof fetch = fetch): Promise<ProjectDetail | null> {
	return apiFetch(`${BASE_URL}/projects/${id}`, null, { fetchFn });
}

export async function createProject(data: {
	name: string;
	description?: string;
	context_profile?: CodebaseContext | null;
}): Promise<ProjectDetail | null> {
	return apiFetch(`${BASE_URL}/projects`, null, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
	});
}

export async function updateProject(
	id: string,
	data: { name?: string; description?: string; context_profile?: CodebaseContext | null },
	updatedAt?: string,
): Promise<ProjectDetail | null> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (updatedAt) {
		// Ensure UTC interpretation — timestamps without timezone suffix are UTC from the server
		const ts = updatedAt.endsWith('Z') || updatedAt.includes('+') ? updatedAt : updatedAt + 'Z';
		headers['If-Unmodified-Since'] = new Date(ts).toUTCString();
	}
	return apiFetch(`${BASE_URL}/projects/${id}`, null, {
		method: 'PUT',
		headers,
		body: JSON.stringify(data),
	});
}

export async function deleteProject(id: string): Promise<boolean> {
	return apiFetchOk(`${BASE_URL}/projects/${id}`, { method: 'DELETE' });
}

export interface ArchiveResponse {
	message: string;
	id: string;
	status: string;
	updated_at: string;
}

export async function archiveProject(id: string): Promise<ArchiveResponse | null> {
	return apiFetch(`${BASE_URL}/projects/${id}/archive`, null, { method: 'POST' });
}

export async function unarchiveProject(id: string): Promise<ArchiveResponse | null> {
	return apiFetch(`${BASE_URL}/projects/${id}/unarchive`, null, { method: 'POST' });
}

export async function addProjectPrompt(projectId: string, content: string): Promise<ProjectPrompt | null> {
	return apiFetch(`${BASE_URL}/projects/${projectId}/prompts`, null, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ content }),
	});
}

export async function updateProjectPrompt(
	projectId: string,
	promptId: string,
	content: string,
): Promise<ProjectPrompt | null> {
	return apiFetch(`${BASE_URL}/projects/${projectId}/prompts/${promptId}`, null, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ content }),
	});
}

export async function deleteProjectPrompt(projectId: string, promptId: string): Promise<boolean> {
	return apiFetchOk(`${BASE_URL}/projects/${projectId}/prompts/${promptId}`, { method: 'DELETE' });
}

export async function reorderProjectPrompts(projectId: string, promptIds: string[]): Promise<boolean> {
	return apiFetchOk(`${BASE_URL}/projects/${projectId}/prompts/reorder`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ prompt_ids: promptIds }),
	});
}

// ---------------------------------------------------------------------------
// Prompt Version History & Forge Results
// ---------------------------------------------------------------------------

export interface PromptVersionItem {
	id: string;
	prompt_id: string;
	version: number;
	content: string;
	created_at: string;
	optimization_id: string | null;
}

export interface PromptVersionListResponse {
	items: PromptVersionItem[];
	total: number;
}

export interface ForgeResultSummary {
	id: string;
	created_at: string;
	overall_score: number | null;
	framework_applied: string | null;
	is_improvement: boolean | null;
	status: string;
	title: string | null;
	task_type: string | null;
	complexity: string | null;
	tags: string[];
	version: string | null;
}

export interface ForgeResultListResponse {
	items: ForgeResultSummary[];
	total: number;
}

export async function fetchPromptVersions(
	projectId: string,
	promptId: string,
	params?: { limit?: number; offset?: number },
): Promise<PromptVersionListResponse> {
	const searchParams = new URLSearchParams();
	if (params?.limit) searchParams.set('limit', String(params.limit));
	if (params?.offset) searchParams.set('offset', String(params.offset));
	const qs = searchParams.toString();
	return apiFetch(
		`${BASE_URL}/projects/${projectId}/prompts/${promptId}/versions${qs ? '?' + qs : ''}`,
		{ items: [], total: 0 },
	);
}

/** Check if an optimization with the given title already exists in the project. */
export async function checkDuplicateTitle(title: string, project?: string): Promise<boolean> {
	const params = new URLSearchParams({ title });
	if (project) params.set('project', project);
	const result = await apiFetch<{ duplicate: boolean }>(
		`${BASE_URL}/optimize/check-duplicate?${params}`,
		{ duplicate: false },
	);
	return result.duplicate;
}

/** Cancel a running optimization. Sets status to CANCELLED for bookkeeping. */
export async function cancelOptimization(id: string): Promise<boolean> {
	return apiFetchOk(`${BASE_URL}/optimize/${id}/cancel`, { method: 'POST' });
}

/** Batch optimize multiple prompts sequentially. */
export async function batchOptimize(
	prompts: string[],
	options?: { strategy?: string; project?: string; tags?: string[] },
): Promise<{
	total: number;
	completed: number;
	failed: number;
	results: { index: number; optimization_id: string | null; overall_score: number | null; status: string; error: string | null }[];
}> {
	const res = await fetch(`${BASE_URL}/optimize/batch`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			prompts,
			strategy: options?.strategy || null,
			project: options?.project || null,
			tags: options?.tags || null,
		}),
	});
	if (!res.ok) {
		throw new Error(`Batch optimize failed: ${res.status}`);
	}
	return res.json();
}

export async function fetchPromptForges(
	projectId: string,
	promptId: string,
	params?: { limit?: number; offset?: number },
): Promise<ForgeResultListResponse> {
	const searchParams = new URLSearchParams();
	if (params?.limit) searchParams.set('limit', String(params.limit));
	if (params?.offset) searchParams.set('offset', String(params.offset));
	const qs = searchParams.toString();
	return apiFetch(
		`${BASE_URL}/projects/${projectId}/prompts/${promptId}/forges${qs ? '?' + qs : ''}`,
		{ items: [], total: 0 },
	);
}
