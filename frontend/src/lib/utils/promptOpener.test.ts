import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ProjectDetail, ProjectPrompt } from '$lib/api/client';

// Mock all dependencies
vi.mock('$lib/api/client', () => ({
	fetchProject: vi.fn(),
}));

vi.mock('$lib/stores/optimization.svelte', () => ({
	optimizationState: {
		openInIDEFromHistory: vi.fn(),
	},
}));

vi.mock('$lib/stores/forgeSession.svelte', () => ({
	forgeSession: {
		loadRequest: vi.fn(),
	},
}));

vi.mock('$lib/stores/forgeMachine.svelte', () => ({
	forgeMachine: {
		restore: vi.fn(),
		enterReview: vi.fn(),
	},
}));

vi.mock('$lib/stores/toast.svelte', () => ({
	toastState: {
		show: vi.fn(),
	},
}));

import { openPromptInIDE } from './promptOpener';
import { fetchProject } from '$lib/api/client';
import { optimizationState } from '$lib/stores/optimization.svelte';
import { forgeSession } from '$lib/stores/forgeSession.svelte';
import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
import { toastState } from '$lib/stores/toast.svelte';

function makePrompt(overrides: Partial<ProjectPrompt> = {}): ProjectPrompt {
	return {
		id: 'prompt-1',
		content: 'Write a haiku about coding',
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

function makeProject(overrides: Partial<ProjectDetail> = {}, prompts?: ProjectPrompt[]): ProjectDetail {
	return {
		id: 'proj-1',
		name: 'Test Project',
		description: null,
		context_profile: null,
		status: 'active',
		created_at: '2026-01-01T00:00:00Z',
		updated_at: '2026-01-01T00:00:00Z',
		prompts: prompts ?? [makePrompt()],
		...overrides,
	};
}

describe('openPromptInIDE', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(optimizationState.openInIDEFromHistory).mockResolvedValue(undefined);
	});

	it('opens latest forge in IDE review mode when prompt has forges', async () => {
		const prompt = makePrompt({
			forge_count: 3,
			latest_forge: {
				id: 'forge-42',
				title: 'My Forge',
				task_type: 'coding',
				complexity: 'medium',
				framework_applied: 'chain-of-thought',
				overall_score: 0.8,
				is_improvement: true,
				tags: [],
				version: null,
			},
		});
		const project = makeProject({}, [prompt]);

		await openPromptInIDE({
			promptId: prompt.id,
			projectId: project.id,
			projectData: project,
			prompt,
		});

		expect(optimizationState.openInIDEFromHistory).toHaveBeenCalledWith('forge-42');
		expect(forgeSession.loadRequest).toHaveBeenCalledWith(
			expect.objectContaining({
				text: prompt.content,
				project: project.name,
				promptId: prompt.id,
				sourceAction: 'reiterate',
			}),
		);
		expect(forgeMachine.enterReview).toHaveBeenCalled();
	});

	it('opens in compose mode when prompt has no forges', async () => {
		const prompt = makePrompt({ forge_count: 0, latest_forge: null });
		const project = makeProject({}, [prompt]);

		await openPromptInIDE({
			promptId: prompt.id,
			projectId: project.id,
			projectData: project,
			prompt,
		});

		expect(optimizationState.openInIDEFromHistory).not.toHaveBeenCalled();
		expect(forgeMachine.restore).toHaveBeenCalled();
		expect(forgeSession.loadRequest).toHaveBeenCalledWith(
			expect.objectContaining({
				text: prompt.content,
				project: project.name,
				promptId: prompt.id,
				sourceAction: 'optimize',
			}),
		);
	});

	it('fetches project when projectData is not provided', async () => {
		const prompt = makePrompt();
		const project = makeProject({}, [prompt]);
		vi.mocked(fetchProject).mockResolvedValue(project);

		await openPromptInIDE({
			promptId: prompt.id,
			projectId: project.id,
			prompt,
		});

		expect(fetchProject).toHaveBeenCalledWith(project.id);
		expect(forgeSession.loadRequest).toHaveBeenCalled();
	});

	it('shows error toast when fetchProject returns null', async () => {
		vi.mocked(fetchProject).mockResolvedValue(null as unknown as ProjectDetail);

		await openPromptInIDE({
			promptId: 'prompt-1',
			projectId: 'proj-1',
		});

		expect(fetchProject).toHaveBeenCalledWith('proj-1');
		expect(forgeSession.loadRequest).not.toHaveBeenCalled();
		expect(optimizationState.openInIDEFromHistory).not.toHaveBeenCalled();
		expect(toastState.show).toHaveBeenCalledWith('Could not load project', 'error');
	});

	it('shows error toast when prompt is not found in project', async () => {
		const project = makeProject({}, [makePrompt({ id: 'other-prompt' })]);

		await openPromptInIDE({
			promptId: 'nonexistent-prompt',
			projectId: project.id,
			projectData: project,
		});

		expect(forgeSession.loadRequest).not.toHaveBeenCalled();
		expect(optimizationState.openInIDEFromHistory).not.toHaveBeenCalled();
		expect(toastState.show).toHaveBeenCalledWith('Prompt not found in project', 'error');
	});

	it('passes context profile through when available', async () => {
		const contextProfile = { language: 'TypeScript', framework: 'SvelteKit' };
		const prompt = makePrompt({ forge_count: 0 });
		const project = makeProject({ context_profile: contextProfile }, [prompt]);

		await openPromptInIDE({
			promptId: prompt.id,
			projectId: project.id,
			projectData: project,
			prompt,
		});

		expect(forgeSession.loadRequest).toHaveBeenCalledWith(
			expect.objectContaining({
				contextProfile,
			}),
		);
	});

	it('passes null context profile when project has none', async () => {
		const prompt = makePrompt({ forge_count: 0 });
		const project = makeProject({ context_profile: null }, [prompt]);

		await openPromptInIDE({
			promptId: prompt.id,
			projectId: project.id,
			projectData: project,
			prompt,
		});

		expect(forgeSession.loadRequest).toHaveBeenCalledWith(
			expect.objectContaining({
				contextProfile: null,
			}),
		);
	});
});
