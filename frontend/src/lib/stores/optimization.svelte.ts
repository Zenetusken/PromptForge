import { fetchOptimize, fetchRetry, type PipelineEvent, type HistoryItem, type OptimizeMetadata } from '$lib/api/client';
import { historyState } from '$lib/stores/history.svelte';
import { projectsState } from '$lib/stores/projects.svelte';
import { providerState } from '$lib/stores/provider.svelte';
import { toastState } from '$lib/stores/toast.svelte';
import { safeString, safeNumber, safeArray } from '$lib/utils/safe';

export interface AnalysisStepData {
	task_type?: string;
	complexity?: string;
	weaknesses?: string[];
	strengths?: string[];
	step_duration_ms?: number;
}

export interface OptimizationStepData {
	optimized_prompt?: string;
	framework_applied?: string;
	changes_made?: string[];
	optimization_notes?: string;
	step_duration_ms?: number;
}

export interface ValidationStepData {
	clarity_score?: number;
	specificity_score?: number;
	structure_score?: number;
	faithfulness_score?: number;
	overall_score?: number;
	is_improvement?: boolean;
	verdict?: string;
	step_duration_ms?: number;
}

export type StepData = AnalysisStepData | OptimizationStepData | ValidationStepData;

export interface StrategyData {
	strategy: string;
	reasoning: string;
	confidence: number;
	task_type: string;
	secondary_frameworks: string[];
}

export interface StepState {
	name: string;
	label: string;
	status: 'pending' | 'running' | 'complete' | 'error';
	description?: string;
	data?: Record<string, unknown>;
	streamingContent?: string;
	startTime?: number;
	durationMs?: number;
}

export interface RunState {
	steps: StepState[];
	strategyData?: StrategyData;
}

export interface OptimizationResultState {
	id: string;
	original: string;
	optimized: string;
	task_type: string;
	complexity: string;
	weaknesses: string[];
	strengths: string[];
	changes_made: string[];
	framework_applied: string;
	optimization_notes: string;
	scores: {
		clarity: number;
		specificity: number;
		structure: number;
		faithfulness: number;
		overall: number;
	};
	is_improvement: boolean;
	verdict: string;
	duration_ms: number;
	model_used: string;
	input_tokens: number;
	output_tokens: number;
	title: string;
	version: string;
	project: string;
	prompt_id: string;
	project_id: string;
	project_status: string;
	tags: string[];
	strategy: string;
	strategy_reasoning: string;
	strategy_confidence: number;
	secondary_frameworks: string[];
	created_at: string;
}

/** Translate raw error messages to user-friendly text. */
function friendlyError(msg: string): string {
	const lower = msg.toLowerCase();
	if (lower.includes('failed to fetch') || lower.includes('networkerror'))
		return 'Cannot reach the server. Check your connection and try again.';
	if (lower.includes('502') || lower.includes('bad gateway'))
		return 'The server is temporarily unavailable. Please try again in a moment.';
	if (lower.includes('503') || lower.includes('service unavailable'))
		return 'The service is under heavy load. Please try again shortly.';
	if (lower.includes('504') || lower.includes('gateway timeout'))
		return 'The request timed out. The server may be busy — try again.';
	if (lower.includes('401') || lower.includes('unauthorized'))
		return 'Authentication failed. Check your API key and try again.';
	if (lower.includes('429'))
		return 'Rate limit reached. Please wait before trying again.';
	return msg;
}

const INITIAL_PIPELINE_STEPS: StepState[] = [
	{ name: 'analyze', label: 'ANALYZE', status: 'pending', description: 'Analyzing prompt structure and intent' },
	{ name: 'strategy', label: 'STRATEGY', status: 'pending', description: 'Selecting optimization approach' },
	{ name: 'optimize', label: 'OPTIMIZE', status: 'pending', description: 'Rewriting for clarity and effectiveness' },
	{ name: 'validate', label: 'VALIDATE', status: 'pending', description: 'Scoring and quality assessment' }
];

/**
 * Map a data source (SSE result or HistoryItem) to an OptimizationResultState.
 * Used by handleEvent('result'), loadFromHistory(), and bulk project export.
 */
export function mapToResultState(
	source: Record<string, unknown>,
	originalPrompt: string
): OptimizationResultState {
	return {
		id: safeString(source.id),
		original: originalPrompt,
		optimized: safeString(source.optimized_prompt),
		task_type: safeString(source.task_type),
		complexity: safeString(source.complexity),
		weaknesses: safeArray(source.weaknesses),
		strengths: safeArray(source.strengths),
		changes_made: safeArray(source.changes_made),
		framework_applied: safeString(source.framework_applied),
		optimization_notes: safeString(source.optimization_notes),
		scores: {
			clarity: safeNumber(source.clarity_score),
			specificity: safeNumber(source.specificity_score),
			structure: safeNumber(source.structure_score),
			faithfulness: safeNumber(source.faithfulness_score),
			overall: safeNumber(source.overall_score),
		},
		is_improvement: typeof source.is_improvement === 'boolean' ? source.is_improvement : false,
		verdict: safeString(source.verdict),
		duration_ms: safeNumber(source.duration_ms),
		model_used: safeString(source.model_used),
		input_tokens: safeNumber(source.input_tokens),
		output_tokens: safeNumber(source.output_tokens),
		title: safeString(source.title),
		version: safeString(source.version),
		project: safeString(source.project),
		prompt_id: safeString(source.prompt_id),
		project_id: safeString(source.project_id),
		project_status: safeString(source.project_status),
		tags: safeArray(source.tags),
		strategy: safeString(source.strategy),
		strategy_reasoning: safeString(source.strategy_reasoning),
		strategy_confidence: safeNumber(source.strategy_confidence),
		secondary_frameworks: safeArray(source.secondary_frameworks),
		created_at: safeString(source.created_at),
	};
}

class OptimizationState {
	currentRun: RunState | null = $state(null);
	result: OptimizationResultState | null = $state(null);
	isRunning: boolean = $state(false);
	error: string | null = $state(null);
	errorType: string | null = $state(null);
	retryAfter: number | null = $state(null);
	pendingNavigation: string | null = $state(null);

	private abortController: AbortController | null = null;

	consumeNavigation(): string | null {
		const nav = this.pendingNavigation;
		this.pendingNavigation = null;
		return nav;
	}

	private _resetRunState() {
		this.cancel();
		this.isRunning = true;
		this.error = null;
		this.errorType = null;
		this.retryAfter = null;
		this.result = null;
		this.currentRun = {
			steps: INITIAL_PIPELINE_STEPS.map(s => ({ ...s }))
		};
	}

	private _failWithError(message: string, errorType?: string, retryAfter?: number) {
		this.error = friendlyError(message);
		this.errorType = errorType ?? null;
		this.retryAfter = retryAfter ?? null;
		this.isRunning = false;
		if (this.currentRun) {
			this.currentRun.steps = this.currentRun.steps.map((s) => ({
				...s,
				status: s.status === 'running' ? ('error' as const) : s.status
			}));
		}
		toastState.show(this.error, 'error');
	}

	private _onStreamError = (err: Error) => {
		this._failWithError(err.message);
	};

	startOptimization(prompt: string, metadata?: OptimizeMetadata) {
		this._resetRunState();

		this.abortController = fetchOptimize(
			prompt,
			(event) => this.handleEvent(event, prompt),
			this._onStreamError,
			metadata,
			providerState.getLLMHeaders()
		);
	}

	retryOptimization(id: string, originalPrompt: string) {
		this._resetRunState();

		this.abortController = fetchRetry(
			id,
			(event) => this.handleEvent(event, originalPrompt),
			this._onStreamError,
			providerState.getLLMHeaders()
		);
	}

	private updateStep(stepName: string, updater: Partial<StepState> | ((s: StepState) => Partial<StepState>)) {
		if (!this.currentRun) return;
		const steps = this.currentRun.steps;
		const idx = steps.findIndex((s) => s.name === stepName);
		if (idx === -1) return;
		const patch = typeof updater === 'function' ? updater(steps[idx]) : updater;
		Object.assign(steps[idx], patch);
		this.currentRun.steps = steps; // single reassignment triggers reactivity
	}

	private handleEvent(event: PipelineEvent, originalPrompt: string) {
		if (!this.currentRun) return;

		switch (event.type) {
			case 'step_start':
				this.updateStep(event.step || '', (s) => ({
					status: 'running' as const,
					startTime: Date.now(),
					streamingContent: s.streamingContent || '',
				}));
				break;

			case 'step_progress': {
				const content = safeString(event.data?.content);
				this.updateStep(event.step || '', (s) => ({
					streamingContent: s.streamingContent ? s.streamingContent + '\n' + content : content
				}));
				break;
			}

			case 'strategy_selected': {
				const data = event.data || {};
				const strategyData: StrategyData = {
					strategy: safeString(data.strategy),
					reasoning: safeString(data.reasoning),
					confidence: safeNumber(data.confidence),
					task_type: safeString(data.task_type),
					secondary_frameworks: safeArray(data.secondary_frameworks),
				};
				this.currentRun.strategyData = strategyData;
				this.updateStep('strategy', {
					status: 'complete' as const,
					data: data,
					durationMs: safeNumber(data.step_duration_ms),
					streamingContent: undefined,
				});
				break;
			}

			case 'step_complete': {
				const stepDurationMs = safeNumber(event.data?.step_duration_ms);
				this.updateStep(event.step || '', (s) => {
					const durationMs = stepDurationMs || (s.startTime ? Date.now() - s.startTime : 0);
					return { status: 'complete' as const, data: event.data, durationMs, streamingContent: undefined };
				});
				break;
			}

			case 'step_error':
				this.updateStep(event.step || '', { status: 'error' as const });
				this.error = event.error || 'Step failed';
				break;

			case 'result': {
				this.result = mapToResultState(event.data || {}, originalPrompt);
				this.isRunning = false;
				// Mark all steps as complete
				if (this.currentRun) {
					this.currentRun.steps = this.currentRun.steps.map((s) => ({
						...s,
						status: 'complete' as const
					}));
				}
				toastState.show('Optimization complete!', 'success');
				if (this.result.id) {
					this.pendingNavigation = `/optimize/${this.result.id}`;
				}
				historyState.loadHistory();
				if (this.result?.project) {
					projectsState.loadProjects();
				}
				break;
			}

			case 'error': {
				this._failWithError(event.error || 'Unknown error', event.errorType, event.retryAfter);
				break;
			}
		}
	}

	/**
	 * Load a result from history (no pipeline animation)
	 */
	loadFromHistory(item: HistoryItem) {
		this.cancel();
		this.currentRun = null;
		this.result = null;
		this.result = mapToResultState({ ...item }, item.raw_prompt);
	}

	cancel() {
		if (this.abortController) {
			this.abortController.abort();
			this.abortController = null;
		}
		this.isRunning = false;
	}

	reset() {
		this.cancel();
		this.currentRun = null;
		this.result = null;
		this.error = null;
		if (typeof window !== 'undefined' && window.location.pathname.startsWith('/optimize/')) {
			this.pendingNavigation = '/';
		}
	}
}

export const optimizationState = new OptimizationState();
