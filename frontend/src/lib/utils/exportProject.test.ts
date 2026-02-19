// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { deduplicateFilename, exportProjectAsZip, type ProjectExportProgress } from './exportProject';
import type { ProjectDetail, ProjectPrompt, HistoryItem } from '$lib/api/client';

// --- Mocks ---

vi.mock('$lib/api/client', () => ({
	fetchOptimization: vi.fn(),
	fetchPromptForges: vi.fn(),
}));

vi.mock('$lib/stores/optimization.svelte', () => ({
	mapToResultState: vi.fn((source: Record<string, unknown>, original: string) => ({
		id: source.id ?? 'test-id',
		original,
		optimized: source.optimized_prompt ?? '',
		task_type: source.task_type ?? '',
		complexity: source.complexity ?? '',
		weaknesses: [],
		strengths: [],
		changes_made: [],
		framework_applied: '',
		optimization_notes: '',
		scores: { clarity: 0.8, specificity: 0.7, structure: 0.9, faithfulness: 0.85, overall: 0.81 },
		is_improvement: true,
		verdict: '',
		duration_ms: 0,
		model_used: '',
		input_tokens: 0,
		output_tokens: 0,
		title: source.title ?? '',
		version: source.version ?? '',
		project: '',
		prompt_id: '',
		project_id: '',
		project_status: '',
		tags: [],
		strategy: '',
		strategy_reasoning: '',
		strategy_confidence: 0,
		secondary_frameworks: [],
		created_at: source.created_at ?? '',
	})),
}));

vi.mock('$lib/utils/export', () => ({
	generateExportMarkdown: vi.fn(() => '# Mock Markdown\n\nContent here'),
	slugifyTitle: vi.fn((s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')),
	downloadBlob: vi.fn(),
}));

// Mock JSZip
const mockFile = vi.fn();
const mockFolder = vi.fn(() => ({ file: mockFile }));
const mockGenerateAsync = vi.fn(() => Promise.resolve(new Blob(['zip-content'])));

vi.mock('jszip', () => ({
	default: vi.fn(() => ({
		folder: mockFolder,
		generateAsync: mockGenerateAsync,
	})),
}));

import { fetchOptimization, fetchPromptForges } from '$lib/api/client';
import { mapToResultState } from '$lib/stores/optimization.svelte';
import { downloadBlob } from '$lib/utils/export';

function makePrompt(overrides: Partial<ProjectPrompt> = {}): ProjectPrompt {
	return {
		id: 'prompt-1',
		content: 'Test prompt content',
		version: 1,
		project_id: 'proj-1',
		order_index: 0,
		created_at: '2026-01-01T00:00:00Z',
		updated_at: '2026-01-01T00:00:00Z',
		forge_count: 0,
		latest_forge: null,
		...overrides,
	};
}

function makeProject(prompts: ProjectPrompt[]): ProjectDetail {
	return {
		id: 'proj-1',
		name: 'Test Project',
		description: null,
		status: 'active',
		created_at: '2026-01-01T00:00:00Z',
		updated_at: '2026-01-01T00:00:00Z',
		prompts,
	};
}

function makeHistoryItem(overrides: Partial<HistoryItem> = {}): HistoryItem {
	return {
		id: 'forge-1',
		created_at: '2026-01-01T00:00:00Z',
		raw_prompt: 'raw prompt text',
		optimized_prompt: 'optimized',
		task_type: 'coding',
		complexity: 'medium',
		weaknesses: [],
		strengths: [],
		changes_made: [],
		framework_applied: 'role-based',
		optimization_notes: null,
		strategy: null,
		strategy_reasoning: null,
		strategy_confidence: null,
		clarity_score: 0.8,
		specificity_score: 0.7,
		structure_score: 0.9,
		faithfulness_score: 0.85,
		overall_score: 0.81,
		is_improvement: true,
		verdict: 'Good',
		duration_ms: 1500,
		model_used: 'claude-opus-4-6',
		input_tokens: 100,
		output_tokens: 50,
		status: 'completed',
		error_message: null,
		project: 'Test Project',
		tags: [],
		title: 'Test Forge',
		version: null,
		prompt_id: 'prompt-1',
		project_id: 'proj-1',
		project_status: 'active',
		secondary_frameworks: null,
		...overrides,
	};
}

describe('deduplicateFilename', () => {
	it('returns slugified title for unique name', () => {
		const used = new Set<string>();
		const name = deduplicateFilename('My Great Prompt', 'fallback-id', used);
		expect(name).toBe('my-great-prompt');
		expect(used.has('my-great-prompt')).toBe(true);
	});

	it('falls back to ID when title is empty', () => {
		const used = new Set<string>();
		const name = deduplicateFilename('', 'abc123', used);
		expect(name).toBe('abc123');
	});

	it('falls back to ID when title is all special characters', () => {
		const used = new Set<string>();
		const name = deduplicateFilename('!!!@@@###', 'fallback-id', used);
		expect(name).toBe('fallback-id');
	});

	it('appends -2, -3 for collisions', () => {
		const used = new Set<string>();
		const name1 = deduplicateFilename('Same Title', 'id1', used);
		const name2 = deduplicateFilename('Same Title', 'id2', used);
		const name3 = deduplicateFilename('Same Title', 'id3', used);
		expect(name1).toBe('same-title');
		expect(name2).toBe('same-title-2');
		expect(name3).toBe('same-title-3');
	});
});

describe('exportProjectAsZip', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('returns 0 with no zip for project with 0 forges', async () => {
		const project = makeProject([makePrompt({ forge_count: 0 })]);

		const count = await exportProjectAsZip(project);

		expect(count).toBe(0);
		expect(mockFolder).not.toHaveBeenCalled();
		expect(mockGenerateAsync).not.toHaveBeenCalled();
	});

	it('exports project with 2 prompts and 3 total forges', async () => {
		const prompt1 = makePrompt({
			id: 'p1',
			content: 'Prompt one',
			forge_count: 1,
			latest_forge: {
				id: 'forge-1', title: 'Forge One', task_type: 'coding',
				complexity: 'simple', framework_applied: 'role-based',
				overall_score: 0.9, is_improvement: true, tags: [], version: null,
			},
		});
		const prompt2 = makePrompt({
			id: 'p2',
			content: 'Prompt two',
			forge_count: 2,
			latest_forge: {
				id: 'forge-2', title: 'Forge Two', task_type: 'writing',
				complexity: 'moderate', framework_applied: 'few-shot',
				overall_score: 0.8, is_improvement: true, tags: [], version: null,
			},
		});

		const project = makeProject([prompt1, prompt2]);

		vi.mocked(fetchPromptForges).mockResolvedValue({
			items: [
				{ id: 'forge-2', created_at: '2026-01-02T00:00:00Z', overall_score: 0.8, framework_applied: 'few-shot', is_improvement: true, status: 'completed', title: 'Forge Two', task_type: 'writing', complexity: 'moderate', tags: [], version: null },
				{ id: 'forge-3', created_at: '2026-01-01T00:00:00Z', overall_score: 0.7, framework_applied: 'role-based', is_improvement: false, status: 'completed', title: 'Forge Three', task_type: 'writing', complexity: 'simple', tags: [], version: null },
			],
			total: 2,
		});

		vi.mocked(fetchOptimization)
			.mockResolvedValueOnce(makeHistoryItem({ id: 'forge-1', title: 'Forge One', raw_prompt: 'Prompt one' }))
			.mockResolvedValueOnce(makeHistoryItem({ id: 'forge-2', title: 'Forge Two', raw_prompt: 'Prompt two' }))
			.mockResolvedValueOnce(makeHistoryItem({ id: 'forge-3', title: 'Forge Three', raw_prompt: 'Prompt two' }));

		const count = await exportProjectAsZip(project);

		expect(count).toBe(3);
		expect(fetchOptimization).toHaveBeenCalledTimes(3);
		expect(mockFolder).toHaveBeenCalledWith('test-project');
		expect(mockFile).toHaveBeenCalledTimes(3);
		expect(mockGenerateAsync).toHaveBeenCalledWith({ type: 'blob' });
		expect(downloadBlob).toHaveBeenCalledTimes(1);
	});

	it('uses item.raw_prompt as original prompt, not prompt.content', async () => {
		const prompt = makePrompt({
			id: 'p1',
			content: 'Current content (edited after forge)',
			forge_count: 1,
			latest_forge: {
				id: 'forge-1', title: 'F1', task_type: 'coding',
				complexity: 'simple', framework_applied: 'cot',
				overall_score: 0.9, is_improvement: true, tags: [], version: null,
			},
		});

		const project = makeProject([prompt]);
		vi.mocked(fetchOptimization).mockResolvedValueOnce(
			makeHistoryItem({ id: 'forge-1', raw_prompt: 'Original prompt at forge time' }),
		);

		await exportProjectAsZip(project);

		// mapToResultState should receive the raw_prompt from the fetched item, not prompt.content
		expect(mapToResultState).toHaveBeenCalledWith(
			expect.objectContaining({ id: 'forge-1' }),
			'Original prompt at forge time',
		);
	});

	it('handles partial fetch failure gracefully', async () => {
		const prompt = makePrompt({
			id: 'p1',
			content: 'Test',
			forge_count: 2,
			latest_forge: {
				id: 'forge-1', title: 'F1', task_type: 'coding',
				complexity: 'simple', framework_applied: 'cot',
				overall_score: 0.9, is_improvement: true, tags: [], version: null,
			},
		});

		const project = makeProject([prompt]);

		vi.mocked(fetchPromptForges).mockResolvedValue({
			items: [
				{ id: 'forge-1', created_at: '2026-01-01', overall_score: 0.9, framework_applied: 'cot', is_improvement: true, status: 'completed', title: 'F1', task_type: 'coding', complexity: 'simple', tags: [], version: null },
				{ id: 'forge-2', created_at: '2026-01-01', overall_score: 0.8, framework_applied: 'cot', is_improvement: true, status: 'completed', title: 'F2', task_type: 'coding', complexity: 'simple', tags: [], version: null },
			],
			total: 2,
		});

		vi.mocked(fetchOptimization)
			.mockResolvedValueOnce(makeHistoryItem({ id: 'forge-1', title: 'F1' }))
			.mockResolvedValueOnce(null);

		const count = await exportProjectAsZip(project);

		expect(count).toBe(1);
		expect(mockFile).toHaveBeenCalledTimes(1);
		expect(mockGenerateAsync).toHaveBeenCalled();
	});

	it('throws when all fetches fail', async () => {
		const prompt = makePrompt({
			id: 'p1',
			content: 'Test',
			forge_count: 1,
			latest_forge: {
				id: 'forge-1', title: 'F1', task_type: 'coding',
				complexity: 'simple', framework_applied: 'cot',
				overall_score: 0.9, is_improvement: true, tags: [], version: null,
			},
		});

		const project = makeProject([prompt]);

		vi.mocked(fetchOptimization).mockResolvedValueOnce(null);

		await expect(exportProjectAsZip(project)).rejects.toThrow('All forge results failed to load');
	});

	it('reports progress correctly', async () => {
		const prompt = makePrompt({
			id: 'p1',
			content: 'Test',
			forge_count: 1,
			latest_forge: {
				id: 'forge-1', title: 'F1', task_type: 'coding',
				complexity: 'simple', framework_applied: 'cot',
				overall_score: 0.9, is_improvement: true, tags: [], version: null,
			},
		});

		const project = makeProject([prompt]);
		vi.mocked(fetchOptimization).mockResolvedValueOnce(makeHistoryItem({ id: 'forge-1', title: 'F1' }));

		const progress: ProjectExportProgress[] = [];
		await exportProjectAsZip(project, (p) => progress.push({ ...p }));

		expect(progress.length).toBeGreaterThanOrEqual(3);
		expect(progress[0]).toEqual({ total: 1, fetched: 0, status: 'fetching' });
		expect(progress.find(p => p.fetched === 1 && p.status === 'fetching')).toBeTruthy();
		expect(progress.find(p => p.status === 'generating')).toBeTruthy();
		expect(progress[progress.length - 1].status).toBe('done');
	});
});
