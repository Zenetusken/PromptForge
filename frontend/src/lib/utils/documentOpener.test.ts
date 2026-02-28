import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ProjectDetail } from '$lib/api/client';

// Mock all dependencies
vi.mock('$lib/api/client', () => ({
	fetchProject: vi.fn(),
	fetchOptimization: vi.fn(),
}));

vi.mock('$lib/stores/optimization.svelte', () => ({
	optimizationState: {
		forgeResult: null,
	},
	mapToResultState: vi.fn((source: Record<string, unknown>, original: string) => ({
		id: source.id,
		original,
		optimized: source.optimized_prompt,
		scores: { overall: source.overall_score ?? 0 },
	})),
}));

vi.mock('$lib/stores/forgeSession.svelte', () => ({
	forgeSession: {
		loadRequest: vi.fn(),
		activeTab: { document: null, resultId: null },
		findTabByDocument: vi.fn(() => null),
		tabs: [],
		activeTabId: '',
		isActive: false,
	},
}));

vi.mock('$lib/stores/forgeMachine.svelte', () => ({
	forgeMachine: {
		restore: vi.fn(),
		enterReview: vi.fn(),
	},
}));

vi.mock('$lib/stores/windowManager.svelte', () => ({
	windowManager: {
		openIDE: vi.fn(),
		closeIDE: vi.fn(),
	},
}));

vi.mock('$lib/stores/tabCoherence', () => ({
	saveActiveTabState: vi.fn(),
	restoreTabState: vi.fn(),
}));

vi.mock('$lib/stores/toast.svelte', () => ({
	toastState: {
		show: vi.fn(),
	},
}));

vi.mock('$lib/utils/fileTypes', () => ({
	toArtifactName: vi.fn((title?: string, score?: number) =>
		title || `Forge Result (${Math.round((score ?? 0) * 10)}/10)`
	),
}));

import { openDocument } from './documentOpener';
import { fetchProject, fetchOptimization } from '$lib/api/client';
import { optimizationState } from '$lib/stores/optimization.svelte';
import { forgeSession } from '$lib/stores/forgeSession.svelte';
import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
import { windowManager } from '$lib/stores/windowManager.svelte';
import { saveActiveTabState, restoreTabState } from '$lib/stores/tabCoherence';
import { toastState } from '$lib/stores/toast.svelte';
import type { PromptDescriptor, ArtifactDescriptor, SubArtifactDescriptor } from './fileDescriptor';

function makeProject(prompts: any[] = []): ProjectDetail {
	return {
		id: 'proj-1',
		name: 'Test Project',
		description: null,
		context_profile: null,
		status: 'active',
		parent_id: null,
		depth: 0,
		created_at: '2026-01-01T00:00:00Z',
		updated_at: '2026-01-01T00:00:00Z',
		prompts,
	};
}

describe('openDocument', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		(forgeSession.activeTab as any).document = null;
		(forgeSession.activeTab as any).resultId = null;
		(optimizationState as any).forgeResult = null;
	});

	describe('prompt descriptor', () => {
		const descriptor: PromptDescriptor = {
			kind: 'prompt',
			id: 'prompt-1',
			projectId: 'proj-1',
			name: 'Test.md',
			extension: '.md',
		};

		it('opens prompt in compose mode when no forges exist', async () => {
			const prompt = {
				id: 'prompt-1', content: 'Write a haiku', version: 1,
				project_id: 'proj-1', order_index: 0,
				created_at: '2026-01-01', updated_at: '2026-01-01',
				forge_count: 0, latest_forge: null,
			};
			vi.mocked(fetchProject).mockResolvedValue(makeProject([prompt]));

			await openDocument(descriptor);

			expect(forgeMachine.restore).toHaveBeenCalled();
			expect(forgeSession.loadRequest).toHaveBeenCalledWith(
				expect.objectContaining({
					text: 'Write a haiku',
					sourceAction: 'optimize',
				}),
			);
			expect(forgeSession.activeTab.document).toBe(descriptor);
			expect(forgeMachine.enterReview).not.toHaveBeenCalled();
		});

		it('opens prompt in review mode when forges exist', async () => {
			const prompt = {
				id: 'prompt-1', content: 'Write a haiku', version: 1,
				project_id: 'proj-1', order_index: 0,
				created_at: '2026-01-01', updated_at: '2026-01-01',
				forge_count: 2,
				latest_forge: {
					id: 'forge-1', title: 'My Forge', task_type: 'coding',
					complexity: 'medium', framework_applied: 'cot',
					overall_score: 0.8, is_improvement: true, tags: [], version: null,
				},
			};
			vi.mocked(fetchProject).mockResolvedValue(makeProject([prompt]));
			vi.mocked(fetchOptimization).mockResolvedValue({
				id: 'forge-1', raw_prompt: 'Write a haiku',
				optimized_prompt: 'better haiku', overall_score: 0.8,
			} as any);

			await openDocument(descriptor);

			expect(fetchOptimization).toHaveBeenCalledWith('forge-1');
			expect(forgeMachine.enterReview).toHaveBeenCalled();
			expect(forgeSession.loadRequest).toHaveBeenCalledWith(
				expect.objectContaining({
					text: 'Write a haiku',
					sourceAction: 'reiterate',
				}),
			);
			expect(forgeSession.activeTab.document).toBe(descriptor);
		});

		it('opens in review even if fetchOptimization returns null (graceful)', async () => {
			const prompt = {
				id: 'prompt-1', content: 'Write a haiku', version: 1,
				project_id: 'proj-1', order_index: 0,
				created_at: '2026-01-01', updated_at: '2026-01-01',
				forge_count: 1,
				latest_forge: {
					id: 'forge-1', title: 'My Forge', task_type: 'coding',
					complexity: 'medium', framework_applied: 'cot',
					overall_score: 0.8, is_improvement: true, tags: [], version: null,
				},
			};
			vi.mocked(fetchProject).mockResolvedValue(makeProject([prompt]));
			vi.mocked(fetchOptimization).mockResolvedValue(null as any);

			await openDocument(descriptor);

			// Should still create tab and enter review (result will be null but tab is valid)
			expect(forgeSession.loadRequest).toHaveBeenCalled();
			expect(forgeMachine.enterReview).toHaveBeenCalled();
			expect(forgeSession.activeTab.document).toBe(descriptor);
		});

		it('shows error toast when project not found', async () => {
			vi.mocked(fetchProject).mockResolvedValue(null as any);

			await openDocument(descriptor);

			expect(toastState.show).toHaveBeenCalledWith('Could not load project', 'error');
			expect(forgeSession.loadRequest).not.toHaveBeenCalled();
		});

		it('shows error toast when prompt not in project', async () => {
			vi.mocked(fetchProject).mockResolvedValue(makeProject([{
				id: 'other', content: 'x', version: 1, project_id: 'proj-1',
				order_index: 0, created_at: '', updated_at: '', forge_count: 0, latest_forge: null,
			}]));

			await openDocument(descriptor);

			expect(toastState.show).toHaveBeenCalledWith('Prompt not found in project', 'error');
		});

		it('passes context profile from project to loadRequest', async () => {
			const ctx = { language: 'TypeScript', framework: 'SvelteKit' };
			const prompt = {
				id: 'prompt-1', content: 'test', version: 1, project_id: 'proj-1',
				order_index: 0, created_at: '', updated_at: '',
				forge_count: 0, latest_forge: null,
			};
			vi.mocked(fetchProject).mockResolvedValue(makeProject([prompt]));
			(vi.mocked(fetchProject).mock.results[0] as any) = undefined;
			vi.mocked(fetchProject).mockResolvedValue({ ...makeProject([prompt]), context_profile: ctx });

			await openDocument(descriptor);

			expect(forgeSession.loadRequest).toHaveBeenCalledWith(
				expect.objectContaining({ contextProfile: ctx }),
			);
		});
	});

	describe('artifact descriptor', () => {
		const descriptor: ArtifactDescriptor = {
			kind: 'artifact',
			id: 'opt-1',
			artifactKind: 'forge-result',
			name: 'Test Result',
			sourcePromptId: null,
			sourceProjectId: null,
		};

		it('opens artifact in review mode with a proper tab', async () => {
			vi.mocked(fetchOptimization).mockResolvedValue({
				id: 'opt-1', raw_prompt: 'original', optimized_prompt: 'better',
				title: 'Test Result', overall_score: 0.8,
				project: 'proj-1', prompt_id: null,
			} as any);

			await openDocument(descriptor);

			expect(forgeSession.loadRequest).toHaveBeenCalledWith(
				expect.objectContaining({ text: 'original' }),
			);
			expect(forgeMachine.enterReview).toHaveBeenCalled();
			expect(forgeSession.activeTab.document).toBe(descriptor);
			expect(forgeSession.activeTab.resultId).toBe('opt-1');
		});

		it('shows error toast when optimization not found', async () => {
			vi.mocked(fetchOptimization).mockResolvedValue(null as any);

			await openDocument(descriptor);

			expect(toastState.show).toHaveBeenCalledWith('Could not load forge result', 'error');
			expect(forgeSession.loadRequest).not.toHaveBeenCalled();
		});
	});

	describe('sub-artifact descriptor', () => {
		const descriptor: SubArtifactDescriptor = {
			kind: 'sub-artifact',
			id: 'opt-1',
			artifactKind: 'forge-analysis',
			name: 'analysis.scan',
			parentForgeId: 'opt-1',
			extension: '.scan',
		};

		it('opens sub-artifact in review mode via parent forge', async () => {
			vi.mocked(fetchOptimization).mockResolvedValue({
				id: 'opt-1', raw_prompt: 'original', optimized_prompt: 'better',
				title: 'Test Result', overall_score: 0.8,
				project: 'proj-1', prompt_id: null,
			} as any);

			await openDocument(descriptor);

			expect(fetchOptimization).toHaveBeenCalledWith('opt-1');
			expect(forgeSession.loadRequest).toHaveBeenCalledWith(
				expect.objectContaining({ text: 'original' }),
			);
			expect(forgeMachine.enterReview).toHaveBeenCalled();
			expect(forgeSession.activeTab.document).toBe(descriptor);
			expect(forgeSession.activeTab.resultId).toBe('opt-1');
		});

		it('shows error toast when parent forge not found', async () => {
			vi.mocked(fetchOptimization).mockResolvedValue(null as any);

			await openDocument(descriptor);

			expect(toastState.show).toHaveBeenCalledWith('Could not load forge result', 'error');
			expect(forgeSession.loadRequest).not.toHaveBeenCalled();
		});
	});

	describe('template descriptor', () => {
		it('does nothing (future extensibility)', async () => {
			await openDocument({
				kind: 'template',
				id: 't-1',
				name: 'Template',
				extension: '.tmpl',
				category: 'coding',
			});

			expect(forgeSession.loadRequest).not.toHaveBeenCalled();
			expect(forgeMachine.enterReview).not.toHaveBeenCalled();
		});
	});

	describe('deduplication', () => {
		const descriptor: PromptDescriptor = {
			kind: 'prompt',
			id: 'prompt-1',
			projectId: 'proj-1',
			name: 'Test.md',
			extension: '.md',
		};

		it('focuses existing tab instead of creating a new one', async () => {
			const existingTab = {
				id: 'tab-existing',
				name: 'Test.md',
				draft: { text: 'content' },
				resultId: null,
				mode: 'compose' as const,
				document: descriptor,
			};
			vi.mocked(forgeSession.findTabByDocument).mockReturnValue(existingTab as any);

			await openDocument(descriptor);

			expect(saveActiveTabState).toHaveBeenCalled();
			expect(restoreTabState).toHaveBeenCalledWith(existingTab);
			expect(windowManager.openIDE).toHaveBeenCalled();
			expect(forgeSession.loadRequest).not.toHaveBeenCalled();
		});

		it('proceeds normally when no existing tab found', async () => {
			vi.mocked(forgeSession.findTabByDocument).mockReturnValue(null);
			const prompt = {
				id: 'prompt-1', content: 'Write a haiku', version: 1,
				project_id: 'proj-1', order_index: 0,
				created_at: '2026-01-01', updated_at: '2026-01-01',
				forge_count: 0, latest_forge: null,
			};
			vi.mocked(fetchProject).mockResolvedValue(makeProject([prompt]));

			await openDocument(descriptor);

			expect(forgeSession.loadRequest).toHaveBeenCalled();
		});
	});
});
