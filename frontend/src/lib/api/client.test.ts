import { describe, it, expect, vi, afterEach } from 'vitest';
import { mapSSEEvent, fetchOptimize, type PipelineEvent, type ProjectPrompt, type LatestForgeInfo } from './client';

describe('mapSSEEvent', () => {
	it('maps "stage" to step_start with mapped step name', () => {
		const result = mapSSEEvent('stage', { stage: 'analyzing', message: 'Starting analysis' });
		expect(result).toEqual({
			type: 'step_start',
			step: 'analyze',
			message: 'Starting analysis'
		});
	});

	it('maps "stage" with unknown stage name as-is', () => {
		const result = mapSSEEvent('stage', { stage: 'unknown_stage' });
		expect(result?.step).toBe('unknown_stage');
	});

	it('maps "strategy" to strategy_selected with data', () => {
		const data = { strategy: 'chain-of-thought', reasoning: 'Best fit', confidence: 0.9 };
		const result = mapSSEEvent('strategy', data);
		expect(result).toEqual({
			type: 'strategy_selected',
			data: data
		});
	});

	it('maps "step_progress" preserving step and data', () => {
		const data = { step: 'analyze', content: 'Processing...', progress: 0.5 };
		const result = mapSSEEvent('step_progress', data);
		expect(result).toEqual({
			type: 'step_progress',
			step: 'analyze',
			data: data
		});
	});

	it('maps "analysis" to step_complete for analyze step', () => {
		const data = { task_type: 'coding', complexity: 'medium' };
		const result = mapSSEEvent('analysis', data);
		expect(result).toEqual({
			type: 'step_complete',
			step: 'analyze',
			data: data
		});
	});

	it('maps "optimization" to step_complete for optimize step', () => {
		const data = { optimized_prompt: 'Better prompt' };
		const result = mapSSEEvent('optimization', data);
		expect(result).toEqual({
			type: 'step_complete',
			step: 'optimize',
			data: data
		});
	});

	it('maps "validation" to step_complete for validate step', () => {
		const data = { overall_score: 0.85 };
		const result = mapSSEEvent('validation', data);
		expect(result).toEqual({
			type: 'step_complete',
			step: 'validate',
			data: data
		});
	});

	it('maps "complete" to result', () => {
		const data = { id: 'abc-123', status: 'completed' };
		const result = mapSSEEvent('complete', data);
		expect(result).toEqual({
			type: 'result',
			data: data
		});
	});

	it('maps "error" with error string', () => {
		const result = mapSSEEvent('error', { error: 'Something went wrong' });
		expect(result).toEqual({
			type: 'error',
			error: 'Something went wrong'
		});
	});

	it('maps "error" without error string to "Unknown error"', () => {
		const result = mapSSEEvent('error', {});
		expect(result?.error).toBe('Unknown error');
	});

	it('returns null for unknown event types', () => {
		const result = mapSSEEvent('unknown_event', {});
		expect(result).toBeNull();
	});
});

describe('fetchOptimize (SSE streaming)', () => {
	const originalFetch = globalThis.fetch;

	afterEach(() => {
		globalThis.fetch = originalFetch;
		vi.restoreAllMocks();
	});

	function mockSSEFetch(chunks: string[], status = 200) {
		const encoder = new TextEncoder();
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: status >= 200 && status < 300,
			status,
			statusText: status === 200 ? 'OK' : 'Error',
			body: new ReadableStream({
				start(controller) {
					for (const chunk of chunks) {
						controller.enqueue(encoder.encode(chunk));
					}
					controller.close();
				}
			})
		});
	}

	it('parses complete SSE events and calls onEvent', async () => {
		const chunks = [
			'event: stage\ndata: {"stage":"analyzing","message":"Starting"}\n\n',
			'event: complete\ndata: {"id":"123","status":"completed"}\n\n'
		];
		mockSSEFetch(chunks);

		const events: PipelineEvent[] = [];
		fetchOptimize('test prompt', (e) => events.push(e));

		await vi.waitFor(() => expect(events.length).toBe(2), { timeout: 1000 });

		expect(events[0]).toEqual({
			type: 'step_start',
			step: 'analyze',
			message: 'Starting'
		});
		expect(events[1]).toEqual({
			type: 'result',
			data: { id: '123', status: 'completed' }
		});
	});

	it('handles chunked SSE data split across reads', async () => {
		const chunks = ['event: stage\nda', 'ta: {"stage":"analyzing"}\n\n'];
		mockSSEFetch(chunks);

		const events: PipelineEvent[] = [];
		fetchOptimize('test', (e) => events.push(e));

		await vi.waitFor(() => expect(events.length).toBe(1), { timeout: 1000 });
		expect(events[0].type).toBe('step_start');
	});

	it('calls onError for non-200 responses', async () => {
		mockSSEFetch([], 500);

		const errors: Error[] = [];
		fetchOptimize('test', () => {}, (e) => errors.push(e));

		await vi.waitFor(() => expect(errors.length).toBe(1), { timeout: 1000 });
		expect(errors[0].message).toContain('500');
	});

	it('skips malformed JSON data lines', async () => {
		const chunks = [
			'event: stage\ndata: not-json\n\n',
			'event: complete\ndata: {"id":"ok"}\n\n'
		];
		mockSSEFetch(chunks);

		const events: PipelineEvent[] = [];
		const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
		fetchOptimize('test', (e) => events.push(e));

		await vi.waitFor(() => expect(events.length).toBe(1), { timeout: 1000 });
		expect(events[0].type).toBe('result');
		expect(warnSpy).toHaveBeenCalled();
		warnSpy.mockRestore();
	});

	it('returns an AbortController that can cancel the stream', () => {
		mockSSEFetch([]);
		const controller = fetchOptimize('test', () => {});
		expect(controller).toBeInstanceOf(AbortController);
		controller.abort();
		expect(controller.signal.aborted).toBe(true);
	});

	it('does not call onError when aborted', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			status: 200,
			statusText: 'OK',
			body: new ReadableStream({
				start() {
					// Never enqueue or close — simulates a hanging stream
				}
			})
		});

		const errors: Error[] = [];
		const controller = fetchOptimize('test', () => {}, (e) => errors.push(e));
		controller.abort();

		await new Promise((r) => setTimeout(r, 100));
		expect(errors.length).toBe(0);
	});

	it('sends correct headers and body', async () => {
		mockSSEFetch([]);
		fetchOptimize('my prompt', () => {}, undefined, { title: 'Test', project: 'proj' });

		await new Promise((r) => setTimeout(r, 50));

		const fetchCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
		expect(fetchCall[0]).toContain('/optimize');
		const init = fetchCall[1];
		expect(init.method).toBe('POST');
		expect(init.headers['Content-Type']).toBe('application/json');
		const body = JSON.parse(init.body);
		expect(body.prompt).toBe('my prompt');
		expect(body.title).toBe('Test');
	});

	it('ignores unknown SSE event types', async () => {
		const chunks = ['event: unknown_event\ndata: {"foo":"bar"}\n\n'];
		mockSSEFetch(chunks);

		const events: PipelineEvent[] = [];
		fetchOptimize('test', (e) => events.push(e));

		await new Promise((r) => setTimeout(r, 100));
		expect(events.length).toBe(0);
	});
});

describe('ProjectPrompt type', () => {
	it('includes latest_forge field with correct shape', () => {
		const forge: LatestForgeInfo = {
			id: 'forge-1',
			title: 'Test Title',
			task_type: 'coding',
			complexity: 'moderate',
			framework_applied: 'chain-of-thought',
			overall_score: 0.85,
			is_improvement: true,
			tags: ['tag1', 'tag2'],
		};
		const prompt: ProjectPrompt = {
			id: 'p-1',
			content: 'test',
			version: 1,
			project_id: 'proj-1',
			order_index: 0,
			created_at: '2025-01-01',
			updated_at: '2025-01-01',
			forge_count: 1,
			latest_forge: forge,
		};
		expect(prompt.latest_forge).not.toBeNull();
		expect(prompt.latest_forge?.task_type).toBe('coding');
		expect(prompt.latest_forge?.tags).toEqual(['tag1', 'tag2']);
	});

	it('allows null latest_forge', () => {
		const prompt: ProjectPrompt = {
			id: 'p-2',
			content: 'test',
			version: 1,
			project_id: 'proj-1',
			order_index: 0,
			created_at: '2025-01-01',
			updated_at: '2025-01-01',
			forge_count: 0,
			latest_forge: null,
		};
		expect(prompt.latest_forge).toBeNull();
	});
});
