import { fetchOptimize, type PipelineEvent, type OptimizationResult } from '$lib/api/client';

export interface StepState {
	name: string;
	status: 'pending' | 'running' | 'complete' | 'error';
	description?: string;
}

export interface RunState {
	steps: StepState[];
}

interface OptimizationResultState {
	original: string;
	optimized: string;
	scores: Record<string, number>;
	explanation: string;
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
				{ name: 'Analyze', status: 'pending', description: 'Analyzing prompt structure and intent' },
				{ name: 'Optimize', status: 'pending', description: 'Rewriting for clarity and effectiveness' },
				{ name: 'Validate', status: 'pending', description: 'Scoring and quality assessment' }
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
					s.name.toLowerCase() === stepName.toLowerCase()
						? { ...s, status: 'running' as const }
						: s
				);
				break;
			}

			case 'step_complete': {
				const stepName = event.step || '';
				this.currentRun.steps = this.currentRun.steps.map((s) =>
					s.name.toLowerCase() === stepName.toLowerCase()
						? { ...s, status: 'complete' as const }
						: s
				);
				break;
			}

			case 'step_error': {
				const stepName = event.step || '';
				this.currentRun.steps = this.currentRun.steps.map((s) =>
					s.name.toLowerCase() === stepName.toLowerCase()
						? { ...s, status: 'error' as const }
						: s
				);
				this.error = event.error || 'Step failed';
				break;
			}

			case 'result': {
				const data = event.data as OptimizationResult;
				this.result = {
					original: originalPrompt,
					optimized: data?.optimized || '',
					scores: data?.scores || {},
					explanation: data?.explanation || ''
				};
				this.isRunning = false;
				this.currentRun = null;
				toastState.show('Optimization complete!', 'success');
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

export const optimizationState = new OptimizationState();
export const toastState = new ToastState();
