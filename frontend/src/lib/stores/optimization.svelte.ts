import { fetchOptimize, fetchRetry, fetchOptimization, cancelOptimization, orchestrateAnalyze, orchestrateStrategy, orchestrateOptimize, orchestrateValidate, type AnalyzeRequest, type StrategyRequest, type OptimizeGenerateRequest, type ValidateRequest, type PipelineEvent, type HistoryItem, type OptimizeMetadata, type LLMHeaders } from '$lib/api/client';
import { historyState } from '$lib/stores/history.svelte';
import { projectsState } from '$lib/stores/projects.svelte';
import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
import { processScheduler } from '$lib/stores/processScheduler.svelte';
import { windowManager } from '$lib/stores/windowManager.svelte';
import { promptAnalysis } from '$lib/stores/promptAnalysis.svelte';
import { providerState } from '$lib/stores/provider.svelte';
import { systemBus } from '$lib/services/systemBus.svelte';
import { sessionContext } from '$lib/stores/sessionContext.svelte';
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
	cache_creation_input_tokens: number;
	cache_read_input_tokens: number;
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
const ERROR_MAP: [RegExp, string][] = [
	[/failed to fetch|networkerror/i, 'Cannot reach the server. Check your connection and try again.'],
	[/502|bad gateway/i, 'The server is temporarily unavailable. Please try again in a moment.'],
	[/503|service unavailable/i, 'The service is under heavy load. Please try again shortly.'],
	[/504|gateway timeout/i, 'The request timed out. The server may be busy — try again.'],
	[/401|unauthorized/i, 'Authentication failed. Check your API key and try again.'],
	[/429/i, 'Rate limit reached. Please wait before trying again.'],
];

function friendlyError(msg: string): string {
	for (const [pattern, friendly] of ERROR_MAP) {
		if (pattern.test(msg)) return friendly;
	}
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
		cache_creation_input_tokens: safeNumber(source.cache_creation_input_tokens),
		cache_read_input_tokens: safeNumber(source.cache_read_input_tokens),
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
	/** Result from the active forge pipeline (SSE stream). */
	forgeResult: OptimizationResultState | null = $state(null);
	/** Result loaded from history/detail page (no pipeline). */
	viewResult: OptimizationResultState | null = $state(null);
	/** Compatibility getter — returns forge result if available, else view result. */
	get result(): OptimizationResultState | null {
		return this.forgeResult ?? this.viewResult;
	}
	isRunning: boolean = $state(false);
	currentIteration: number = $state(0);
	error: string | null = $state(null);
	errorType: string | null = $state(null);
	retryAfter: number | null = $state(null);
	/** Rolling window of last 10 results for comparison workflow. */
	resultHistory: OptimizationResultState[] = $state([]);

	private abortController: AbortController | null = null;
	private _reloadTimerId: ReturnType<typeof setTimeout> | null = null;
	private _activeProcessId: string | null = null;

	/** Analysis result from a standalone "Analyze Only" call. Null when a full forge result exists. */
	get analysisResult(): AnalysisStepData | null {
		if (!this.currentRun || this.forgeResult) return null;
		const step = this.currentRun.steps.find(s => s.name === 'analyze');
		if (!step || step.status !== 'complete' || !step.data) return null;
		return step.data as AnalysisStepData;
	}

	/** True while a standalone analyze call is in progress. */
	get isAnalyzing(): boolean {
		if (!this.currentRun || this.forgeResult) return false;
		const step = this.currentRun.steps.find(s => s.name === 'analyze');
		return step?.status === 'running';
	}

	/** Dismiss a standalone analysis preview (clears currentRun when no full result exists). */
	clearAnalysis(): void {
		if (this.currentRun && !this.forgeResult) {
			this.currentRun = null;
		}
	}

	private _resetRunState() {
		this.cancel();
		this.isRunning = true;
		this.error = null;
		this.errorType = null;
		this.retryAfter = null;
		this.currentIteration = 0;
		this.forgeResult = null;
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
		if (this._activeProcessId) {
			processScheduler.fail(this._activeProcessId, err.message);
		}
	};

	startOptimization(prompt: string, metadata?: OptimizeMetadata) {
		const proc = processScheduler.spawn({
			title: metadata?.title || prompt.slice(0, 60),
			metadata,
			onExecute: () => {
				this._resetRunState();

				this.abortController = fetchOptimize(
					prompt,
					(event) => this.handleEvent(event, prompt),
					this._onStreamError,
					metadata,
					providerState.getLLMHeaders()
				);
			}
		});
		this._activeProcessId = proc.id;
	}

	retryOptimization(id: string, originalPrompt: string) {
		const proc = processScheduler.spawn({
			title: `Retry: ${originalPrompt.slice(0, 50)}`,
			onExecute: () => {
				this._resetRunState();

				this.abortController = fetchRetry(
					id,
					(event) => this.handleEvent(event, originalPrompt),
					this._onStreamError,
					providerState.getLLMHeaders()
				);
			}
		});
		this._activeProcessId = proc.id;
	}

	/**
	 * Generic orchestration node runner — shared by all 4 pipeline stages.
	 * Handles step status updates, error handling, and toast notifications.
	 */
	private async _runNode<T extends { step_duration_ms?: number }>(
		stepName: string,
		fn: () => Promise<T>,
		toast: string,
		reset = false,
	): Promise<T | null> {
		if (reset) this._resetRunState();
		this.updateStep(stepName, { status: 'running', startTime: Date.now() });
		this.isRunning = true;
		try {
			const result = await fn();
			this.updateStep(stepName, { status: 'complete', data: result, durationMs: result.step_duration_ms });
			this.isRunning = false;
			toastState.show(toast, 'success');
			return result;
		} catch (e: any) {
			this._failWithError(e.message);
			return null;
		}
	}

	async runNodeAnalyze(req: AnalyzeRequest, llmHeaders?: LLMHeaders) {
		const result = await this._runNode('analyze', () => orchestrateAnalyze(req, llmHeaders), 'Analysis complete', true);
		if (result?.task_type) {
			promptAnalysis.updateFromPipeline(result.task_type, result.complexity);
		}
		return result;
	}

	async runNodeStrategy(req: StrategyRequest, llmHeaders?: LLMHeaders) {
		return this._runNode('strategy', () => orchestrateStrategy(req, llmHeaders), 'Strategy ready');
	}

	async runNodeOptimize(req: OptimizeGenerateRequest, llmHeaders?: LLMHeaders) {
		return this._runNode('optimize', () => orchestrateOptimize(req, llmHeaders), 'Optimization ready');
	}

	async runNodeValidate(req: ValidateRequest, llmHeaders?: LLMHeaders) {
		return this._runNode('validate', () => orchestrateValidate(req, llmHeaders), 'Validation complete');
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
			case 'step_start': {
				this.updateStep(event.step || '', (s) => ({
					status: 'running' as const,
					startTime: Date.now(),
					streamingContent: s.streamingContent || '',
				}));
				// Update process scheduler with stage progress
				if (this._activeProcessId && event.step) {
					const stageProgress: Record<string, number> = { analyze: 0.1, strategy: 0.3, optimize: 0.5, validate: 0.8 };
					processScheduler.updateProgress(this._activeProcessId, event.step, stageProgress[event.step] ?? 0);
				}
				break;
			}

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

			case 'iteration': {
				const iterData = event.data || {};
				this.currentIteration = (iterData.iteration as number) ?? 0;
				// Reset optimize+validate steps to pending for re-run
				this.updateStep('optimize', { status: 'pending' as const, streamingContent: undefined });
				this.updateStep('validate', { status: 'pending' as const, streamingContent: undefined });
				toastState.show(
					`Iteration ${iterData.iteration}: score ${Math.round(((iterData.score as number) || 0) * 10)}/10, re-optimizing...`,
					'info'
				);
				break;
			}

			case 'result': {
				this.forgeResult = mapToResultState(event.data || {}, originalPrompt);
				this.isRunning = false;
				sessionContext.record(this.forgeResult);
				// Mark all steps as complete
				if (this.currentRun) {
					this.currentRun.steps = this.currentRun.steps.map((s) => ({
						...s,
						status: 'complete' as const
					}));
				}
				toastState.show('Optimization complete!', 'success');
				// Push to rolling history for comparison (keep last 10)
				if (this.forgeResult.id) {
					this.resultHistory = [this.forgeResult, ...this.resultHistory].slice(0, 10);
				}
				// Complete the tracked process
				if (this._activeProcessId) {
					processScheduler.complete(this._activeProcessId, {
						score: this.forgeResult.scores.overall,
						strategy: this.forgeResult.strategy,
						optimizationId: this.forgeResult.id,
						result: this.forgeResult,
					});
				}
				// Debounce: give the server time to commit and coalesce reloads
				this._reloadTimerId = setTimeout(() => {
					this._reloadTimerId = null;
					historyState.loadHistory();
					if (this.forgeResult?.project) {
						projectsState.loadProjects();
					}
				}, 500);
				break;
			}

			case 'error': {
				this._failWithError(event.error || 'Unknown error', event.errorType, event.retryAfter);
				if (this._activeProcessId) {
					processScheduler.fail(this._activeProcessId, event.error || 'Unknown error');
				}
				break;
			}
		}
	}

	/**
	 * Load a result by ID from the resultHistory cache or server.
	 * Sets forgeResult without triggering enterReview or openIDE.
	 */
	async restoreResult(id: string): Promise<boolean> {
		const cached = this.resultHistory.find(r => r.id === id);
		if (cached) {
			this.forgeResult = cached;
			return true;
		}
		const item = await fetchOptimization(id);
		if (item) {
			this.forgeResult = mapToResultState({ ...item }, item.raw_prompt);
			return true;
		}
		return false;
	}

	/**
	 * Open a result in the IDE in review mode.
	 * Sets forgeResult directly and opens the IDE window.
	 */
	openInIDE(result: OptimizationResultState) {
		this.forgeResult = result;
		forgeMachine.enterReview();
		windowManager.openIDE();
	}

	/**
	 * Fetch an optimization by ID and open it in the IDE.
	 * Convenience method combining fetch + openInIDE.
	 */
	async openInIDEFromHistory(id: string): Promise<void> {
		const item = await fetchOptimization(id);
		if (item) {
			this.openInIDE(mapToResultState({ ...item }, item.raw_prompt));
		}
	}

	/**
	 * Load a result from history (no pipeline animation).
	 * Only touches viewResult — does not clobber an active forge.
	 */
	loadFromHistory(item: HistoryItem) {
		this.cancel();
		this.currentRun = null;
		this.viewResult = mapToResultState({ ...item }, item.raw_prompt);
	}

	cancel() {
		if (this.abortController) {
			this.abortController.abort();
			this.abortController = null;
		}
		if (this._reloadTimerId !== null) {
			clearTimeout(this._reloadTimerId);
			this._reloadTimerId = null;
		}
		this.isRunning = false;
	}

	reset() {
		this.cancel();
		this.currentRun = null;
		this.forgeResult = null;
		this.viewResult = null;
		this.error = null;
	}

	/**
	 * Run a multi-strategy tournament — parallel forges with different strategies, auto-compare best two.
	 */
	startTournament(prompt: string, strategies: string[], metadata?: OptimizeMetadata) {
		const tournamentId = crypto.randomUUID();
		const tournamentResults: { strategy: string; score: number; id: string; result: OptimizationResultState }[] = [];
		const totalStrategies = strategies.length;

		for (const strategy of strategies) {
			const tourneyMeta: OptimizeMetadata = { ...metadata, strategy };

			const proc = processScheduler.spawn({
				title: `${strategy}: ${prompt.slice(0, 40)}`,
				priority: 'interactive',
				promptHash: tournamentId,
				metadata: tourneyMeta,
				onExecute: () => {
					fetchOptimize(
						prompt,
						(event) => {
							if (event.type === 'step_start' && event.step) {
								const stageProgress: Record<string, number> = { analyze: 0.1, strategy: 0.3, optimize: 0.5, validate: 0.8 };
								processScheduler.updateProgress(proc.id, event.step, stageProgress[event.step] ?? 0);
							}
							if (event.type === 'result') {
								const resultState = mapToResultState(event.data || {}, prompt);
								processScheduler.complete(proc.id, {
									score: resultState.scores.overall,
									strategy,
									optimizationId: resultState.id,
									result: resultState,
								});
								// Push to rolling history
								if (resultState.id) {
									this.resultHistory = [resultState, ...this.resultHistory].slice(0, 10);
								}
								tournamentResults.push({
									strategy,
									score: resultState.scores.overall,
									id: resultState.id,
									result: resultState,
								});
								// If all tournament entries complete, auto-compare best two
								if (tournamentResults.length === totalStrategies) {
									this._onTournamentComplete(tournamentResults);
								}
							} else if (event.type === 'error') {
								processScheduler.fail(proc.id, event.error || 'Failed');
								tournamentResults.push({ strategy, score: 0, id: '', result: null as any });
								if (tournamentResults.length === totalStrategies) {
									this._onTournamentComplete(tournamentResults);
								}
							}
						},
						(err) => {
							processScheduler.fail(proc.id, err.message);
							tournamentResults.push({ strategy, score: 0, id: '', result: null as any });
							if (tournamentResults.length === totalStrategies) {
								this._onTournamentComplete(tournamentResults);
							}
						},
						tourneyMeta,
						providerState.getLLMHeaders()
					);
				},
			});
		}
	}

	private _onTournamentComplete(results: { strategy: string; score: number; id: string; result: OptimizationResultState }[]) {
		const valid = results.filter(r => r.id && r.score > 0).sort((a, b) => b.score - a.score);
		if (valid.length >= 2) {
			// Load best result and auto-enter compare mode
			this.forgeResult = valid[0].result;
			forgeMachine.compare(valid[0].id, valid[1].id);
			windowManager.openIDE();
		} else if (valid.length === 1) {
			this.forgeResult = valid[0].result;
			forgeMachine.enterReview();
			windowManager.openIDE();
		}
		systemBus.emit('tournament:completed', 'optimization', {
			results: valid.map(r => ({ strategy: r.strategy, score: r.score, id: r.id })),
		});
		toastState.show(`Tournament complete! ${valid.length} results.`, 'success');
		// Reload history
		setTimeout(() => {
			historyState.loadHistory();
		}, 500);
	}

	/**
	 * Chain a new forge from an existing result — use the optimized prompt as input.
	 */
	chainForge(result: OptimizationResultState, metadata?: OptimizeMetadata) {
		const chainMeta: OptimizeMetadata = {
			...metadata,
			title: `Chain: ${result.title || result.optimized.slice(0, 30)}`,
			tags: [...(metadata?.tags || []), 'chained'],
		};
		this.startOptimization(result.optimized, chainMeta);
	}

	/** Clear only forge-side state, preserving viewResult for detail pages. */
	resetForge() {
		this.cancel();
		this.currentRun = null;
		this.forgeResult = null;
		this.error = null;
	}

	/** Initialize bus subscriptions. Call once from +layout.svelte onMount. */
	init(): () => void {
		const unsubCancel = systemBus.on('forge:cancelled', (event) => {
			const payload = event.payload as { id?: string; optimizationId?: string } | undefined;
			if (!payload) return;
			// If the cancelled process matches our active process, abort the stream
			if (payload.id && payload.id === this._activeProcessId) {
				this.cancel();
				this.isRunning = false;
				if (this.currentRun) {
					this.currentRun.steps = this.currentRun.steps.map(s => ({
						...s,
						status: s.status === 'running' ? ('error' as const) : s.status,
					}));
				}
			}
			// Also cancel on the backend if we have an optimization ID
			if (payload.optimizationId) {
				cancelOptimization(payload.optimizationId);
			}
		});

		return () => {
			unsubCancel();
		};
	}
}

export const optimizationState = new OptimizationState();
