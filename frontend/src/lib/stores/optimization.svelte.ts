import { fetchOptimize, type PipelineEvent, type HistoryItem } from '$lib/api/client';

export interface StepState {
	name: string;
	label: string;
	status: 'pending' | 'running' | 'complete' | 'error';
	description?: string;
	data?: Record<string, unknown>;
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
}

class OptimizationState {
	currentRun: RunState | null = $state(null);
	result: OptimizationResultState | null = $state(null);
	isRunning: boolean = $state(false);
	error: string | null = $state(null);

	private abortController: AbortController | null = null;

	startOptimization(prompt: string) {
		// Clean up previous run
		this.cancel();

		this.isRunning = true;
		this.error = null;
		this.result = null;
		this.currentRun = {
			steps: [
				{ name: 'analyze', label: 'ANALYZE', status: 'pending', description: 'Analyzing prompt structure and intent' },
				{ name: 'optimize', label: 'OPTIMIZE', status: 'pending', description: 'Rewriting for clarity and effectiveness' },
				{ name: 'validate', label: 'VALIDATE', status: 'pending', description: 'Scoring and quality assessment' }
			]
		};

		this.abortController = fetchOptimize(
			prompt,
			(event) => this.handleEvent(event, prompt),
			(err) => {
				this.error = err.message;
				this.isRunning = false;
				toastState.show(err.message, 'error');
			}
		);
	}

	private handleEvent(event: PipelineEvent, originalPrompt: string) {
		if (!this.currentRun) return;

		switch (event.type) {
			case 'step_start': {
				const stepName = event.step || '';
				this.currentRun.steps = this.currentRun.steps.map((s) =>
					s.name === stepName
						? { ...s, status: 'running' as const }
						: s
				);
				break;
			}

			case 'step_complete': {
				const stepName = event.step || '';
				this.currentRun.steps = this.currentRun.steps.map((s) =>
					s.name === stepName
						? { ...s, status: 'complete' as const, data: event.data }
						: s
				);
				break;
			}

			case 'step_error': {
				const stepName = event.step || '';
				this.currentRun.steps = this.currentRun.steps.map((s) =>
					s.name === stepName
						? { ...s, status: 'error' as const }
						: s
				);
				this.error = event.error || 'Step failed';
				break;
			}

			case 'result': {
				const data = event.data || {};
				this.result = {
					id: (data.id as string) || '',
					original: originalPrompt,
					optimized: (data.optimized_prompt as string) || '',
					task_type: (data.task_type as string) || '',
					complexity: (data.complexity as string) || '',
					weaknesses: (data.weaknesses as string[]) || [],
					strengths: (data.strengths as string[]) || [],
					changes_made: (data.changes_made as string[]) || [],
					framework_applied: (data.framework_applied as string) || '',
					optimization_notes: (data.optimization_notes as string) || '',
					scores: {
						clarity: (data.clarity_score as number) || 0,
						specificity: (data.specificity_score as number) || 0,
						structure: (data.structure_score as number) || 0,
						faithfulness: (data.faithfulness_score as number) || 0,
						overall: (data.overall_score as number) || 0,
					},
					is_improvement: (data.is_improvement as boolean) ?? true,
					verdict: (data.verdict as string) || '',
					duration_ms: (data.duration_ms as number) || 0,
				};
				this.isRunning = false;
				// Mark all steps as complete
				if (this.currentRun) {
					this.currentRun.steps = this.currentRun.steps.map((s) => ({
						...s,
						status: 'complete' as const
					}));
				}
				toastState.show('Optimization complete!', 'success');
				// Trigger history refresh
				historyRefreshCallback?.();
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
		this.result = {
			id: item.id,
			original: item.raw_prompt,
			optimized: item.optimized_prompt || '',
			task_type: item.task_type || '',
			complexity: item.complexity || '',
			weaknesses: item.weaknesses || [],
			strengths: item.strengths || [],
			changes_made: item.changes_made || [],
			framework_applied: item.framework_applied || '',
			optimization_notes: item.optimization_notes || '',
			scores: {
				clarity: item.clarity_score || 0,
				specificity: item.specificity_score || 0,
				structure: item.structure_score || 0,
				faithfulness: item.faithfulness_score || 0,
				overall: item.overall_score || 0,
			},
			is_improvement: item.is_improvement ?? true,
			verdict: item.verdict || '',
			duration_ms: item.duration_ms || 0,
		};
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
	}
}

class ToastState {
	message: string = $state('');
	type: 'success' | 'error' | 'info' = $state('info');

	private timeoutId: ReturnType<typeof setTimeout> | null = null;

	show(message: string, type: 'success' | 'error' | 'info' = 'info', duration = 4000) {
		if (this.timeoutId) {
			clearTimeout(this.timeoutId);
		}
		this.message = message;
		this.type = type;
		this.timeoutId = setTimeout(() => {
			this.dismiss();
		}, duration);
	}

	dismiss() {
		this.message = '';
		if (this.timeoutId) {
			clearTimeout(this.timeoutId);
			this.timeoutId = null;
		}
	}
}

// Callback for history refresh after optimization
let historyRefreshCallback: (() => void) | null = null;
export function setHistoryRefreshCallback(cb: () => void) {
	historyRefreshCallback = cb;
}

export const optimizationState = new OptimizationState();
export const toastState = new ToastState();
