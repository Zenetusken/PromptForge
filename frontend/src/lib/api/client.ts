const BASE_URL = '/api';

export interface OptimizationResult {
	id: string;
	original: string;
	optimized: string;
	scores: Record<string, number>;
	explanation: string;
	createdAt: string;
}

export interface HistoryEntry {
	id: string;
	prompt: string;
	score?: number;
	createdAt: string;
}

export interface PipelineEvent {
	type: 'step_start' | 'step_complete' | 'step_error' | 'result' | 'error';
	step?: string;
	data?: unknown;
	error?: string;
}

export interface Stats {
	totalOptimizations: number;
	averageScore: number;
	topCategories: Record<string, number>;
}

/**
 * Opens an SSE connection to the optimization endpoint.
 * Calls the provided callback for each event received.
 */
export function fetchOptimize(
	prompt: string,
	onEvent: (event: PipelineEvent) => void,
	onError?: (error: Error) => void
): AbortController {
	const controller = new AbortController();

	fetch(`${BASE_URL}/optimize`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ prompt }),
		signal: controller.signal
	})
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

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';

				for (const line of lines) {
					const trimmed = line.trim();
					if (trimmed.startsWith('data: ')) {
						try {
							const data = JSON.parse(trimmed.slice(6));
							onEvent(data as PipelineEvent);
						} catch {
							// Skip malformed JSON
						}
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
 * Fetch optimization history
 */
export async function fetchHistory(): Promise<HistoryEntry[]> {
	try {
		const response = await fetch(`${BASE_URL}/history`);
		if (!response.ok) return [];
		return await response.json();
	} catch {
		return [];
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
 * Fetch usage statistics
 */
export async function fetchStats(): Promise<Stats | null> {
	try {
		const response = await fetch(`${BASE_URL}/stats`);
		if (!response.ok) return null;
		return await response.json();
	} catch {
		return null;
	}
}
