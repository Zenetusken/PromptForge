import { fetchOptimize, fetchRetry, type PipelineEvent, type HistoryItem, type OptimizeMetadata } from '$lib/api/client';
import { historyState } from '$lib/stores/history.svelte';
import { toastState } from '$lib/stores/toast.svelte';

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
	title: string;
	project: string;
	tags: string[];
	strategy_reasoning: string;
}

const INITIAL_PIPELINE_STEPS: StepState[] = [
	{ name: 'analyze', label: 'ANALYZE', status: 'pending', description: 'Analyzing prompt structure and intent' },
	{ name: 'optimize', label: 'OPTIMIZE', status: 'pending', description: 'Rewriting for clarity and effectiveness' },
	{ name: 'validate', label: 'VALIDATE', status: 'pending', description: 'Scoring and quality assessment' }
];

// --- Safe accessors for untyped data sources ---

function safeString(value: unknown, fallback = ''): string {
	return typeof value === 'string' ? value : fallback;
}

function safeNumber(value: unknown, fallback = 0): number {
	return typeof value === 'number' ? value : fallback;
}

function safeArray(value: unknown): string[] {
	return Array.isArray(value) ? value : [];
}

/**
 * Map a data source (SSE result or HistoryItem) to an OptimizationResultState.
 * Shared by handleEvent('result') and loadFromHistory().
 */
function mapToResultState(
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
		is_improvement: typeof source.is_improvement === 'boolean' ? source.is_improvement : true,
		verdict: safeString(source.verdict),
		duration_ms: safeNumber(source.duration_ms),
		model_used: safeString(source.model_used),
		title: safeString(source.title),
		project: safeString(source.project),
		tags: safeArray(source.tags),
		strategy_reasoning: safeString(source.strategy_reasoning),
	};
}

class OptimizationState {
	currentRun: RunState | null = $state(null);
	result: OptimizationResultState | null = $state(null);
	isRunning: boolean = $state(false);
	error: string | null = $state(null);
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
		this.result = null;
		this.currentRun = {
			steps: INITIAL_PIPELINE_STEPS.map(s => ({ ...s }))
		};
	}

	private _onStreamError = (err: Error) => {
		this.error = err.message;
		this.isRunning = false;
		toastState.show(err.message, 'error');
	};

	startOptimization(prompt: string, metadata?: OptimizeMetadata) {
		this._resetRunState();

		this.abortController = fetchOptimize(
			prompt,
			(event) => this.handleEvent(event, prompt),
			this._onStreamError,
			metadata
		);
	}

	retryOptimization(id: string, originalPrompt: string) {
		this._resetRunState();

		this.abortController = fetchRetry(
			id,
			(event) => this.handleEvent(event, originalPrompt),
			this._onStreamError
		);
	}

	private updateStep(stepName: string, updater: Partial<StepState> | ((s: StepState) => Partial<StepState>)) {
		if (!this.currentRun) return;
		this.currentRun.steps = this.currentRun.steps.map((s) => {
			if (s.name !== stepName) return s;
			const patch = typeof updater === 'function' ? updater(s) : updater;
			return { ...s, ...patch };
		});
	}

	private handleEvent(event: PipelineEvent, originalPrompt: string) {
		if (!this.currentRun) return;

		switch (event.type) {
			case 'step_start':
				this.updateStep(event.step || '', { status: 'running' as const, startTime: Date.now(), streamingContent: '' });
				break;

			case 'step_progress': {
				const content = (event.data?.content as string) || '';
				this.updateStep(event.step || '', (s) => ({
					streamingContent: (s.streamingContent || '') + '\n' + content
				}));
				break;
			}

			case 'step_complete': {
				const stepDurationMs = (event.data?.step_duration_ms as number) || 0;
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
				break;
			}

			case 'error': {
				this.error = event.error || 'Unknown error';
				this.isRunning = false;
				toastState.show(this.error, 'error');
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
		this.result = mapToResultState(item as unknown as Record<string, unknown>, item.raw_prompt);
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
