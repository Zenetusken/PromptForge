import { fetchOptimize, type PipelineEvent, type HistoryItem } from '$lib/api/client';

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
						? { ...s, status: 'running' as const, startTime: Date.now(), streamingContent: '' }
						: s
				);
				break;
			}

			case 'step_progress': {
				const stepName = event.step || '';
				const content = (event.data?.content as string) || '';
				this.currentRun.steps = this.currentRun.steps.map((s) =>
					s.name === stepName
						? { ...s, streamingContent: (s.streamingContent || '') + '\n' + content }
						: s
				);
				break;
			}

			case 'step_complete': {
				const stepName = event.step || '';
				const stepDurationMs = (event.data?.step_duration_ms as number) || 0;
				this.currentRun.steps = this.currentRun.steps.map((s) => {
					if (s.name === stepName) {
						const durationMs = stepDurationMs || (s.startTime ? Date.now() - s.startTime : 0);
						return { ...s, status: 'complete' as const, data: event.data, durationMs, streamingContent: undefined };
					}
					return s;
				});
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

// Toast system using direct DOM manipulation for guaranteed cross-component reactivity
function getToastStyles(toastType: string): string {
	switch (toastType) {
		case 'success': return 'border-color: rgba(0,255,136,0.3); background: rgba(0,255,136,0.1);';
		case 'error': return 'border-color: rgba(255,0,85,0.3); background: rgba(255,0,85,0.1);';
		default: return 'border-color: rgba(0,240,255,0.3); background: rgba(0,240,255,0.1);';
	}
}

function getToastIcon(toastType: string): string {
	if (toastType === 'success') return '<svg class="h-5 w-5" style="color:#00ff88" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
	if (toastType === 'error') return '<svg class="h-5 w-5" style="color:#ff0055" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
	return '<svg class="h-5 w-5" style="color:#00f0ff" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
}

const toastActions = {
	message: '',
	type: 'info' as 'success' | 'error' | 'info',
	show(msg: string, toastType: 'success' | 'error' | 'info' = 'info', duration = 4000) {
		if (typeof document === 'undefined') return;
		// Remove any existing toast
		const existing = document.getElementById('app-toast');
		if (existing) existing.remove();

		toastActions.message = msg;
		toastActions.type = toastType;

		// Append directly to document.body with fixed positioning
		// (avoids Svelte DOM reconciliation removing manually-added children)
		const toast = document.createElement('div');
		toast.id = 'app-toast';
		toast.setAttribute('role', 'alert');
		toast.setAttribute('data-testid', 'toast-notification');
		toast.style.cssText = `
			position: fixed; bottom: 24px; right: 24px; z-index: 9999;
			display: flex; align-items: center; gap: 12px;
			padding: 12px 20px; border-radius: 12px; border: 1px solid;
			box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
			transition: all 300ms; font-size: 14px; color: #e0e0f0;
			${getToastStyles(toastType)}
		`;
		toast.innerHTML = `${getToastIcon(toastType)}<span>${msg}</span>`;

		// Add dismiss button
		const dismissBtn = document.createElement('button');
		dismissBtn.style.cssText = 'margin-left: 8px; color: #555577; cursor: pointer; background: none; border: none; padding: 2px;';
		dismissBtn.setAttribute('aria-label', 'Dismiss notification');
		dismissBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
		dismissBtn.onclick = () => toast.remove();
		toast.appendChild(dismissBtn);

		document.body.appendChild(toast);

		// Auto-dismiss after duration
		setTimeout(() => {
			if (toast.parentElement) toast.remove();
		}, duration);
	},
	dismiss() {
		if (typeof document === 'undefined') return;
		const existing = document.getElementById('app-toast');
		if (existing) existing.remove();
		this.message = '';
	}
};

// Callback for history refresh after optimization
let historyRefreshCallback: (() => void) | null = null;
export function setHistoryRefreshCallback(cb: () => void) {
	historyRefreshCallback = cb;
}

export const optimizationState = new OptimizationState();
export const toastState = toastActions;
