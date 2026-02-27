import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock documentOpener — it's the new underlying implementation
vi.mock('$lib/utils/documentOpener', () => ({
	openDocument: vi.fn(),
}));

// Mock fileTypes
vi.mock('$lib/utils/fileTypes', () => ({
	toFilename: vi.fn((content: string, title?: string) => title || content.slice(0, 20) + '.md'),
}));

// Mock fileDescriptor
vi.mock('$lib/utils/fileDescriptor', () => ({
	createPromptDescriptor: vi.fn((id: string, projectId: string, name: string) => ({
		kind: 'prompt',
		id,
		projectId,
		name,
		extension: '.md',
	})),
}));

import { openPromptInIDE } from './promptOpener';
import { openDocument } from '$lib/utils/documentOpener';
import { createPromptDescriptor } from '$lib/utils/fileDescriptor';

describe('openPromptInIDE (delegating to openDocument)', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('creates a PromptDescriptor and delegates to openDocument', async () => {
		const prompt = {
			id: 'prompt-1',
			content: 'Write a haiku',
			version: 1,
			project_id: 'proj-1',
			order_index: 0,
			created_at: '2026-01-01T00:00:00Z',
			updated_at: '2026-01-01T00:00:00Z',
			forge_count: 0,
			latest_forge: null,
		};

		await openPromptInIDE({
			promptId: 'prompt-1',
			projectId: 'proj-1',
			prompt,
		});

		expect(createPromptDescriptor).toHaveBeenCalledWith('prompt-1', 'proj-1', expect.any(String));
		expect(openDocument).toHaveBeenCalledWith(
			expect.objectContaining({ kind: 'prompt', id: 'prompt-1', projectId: 'proj-1' }),
		);
	});

	it('uses latest_forge title for the descriptor name', async () => {
		const prompt = {
			id: 'prompt-1',
			content: 'Write a haiku',
			version: 1,
			project_id: 'proj-1',
			order_index: 0,
			created_at: '2026-01-01T00:00:00Z',
			updated_at: '2026-01-01T00:00:00Z',
			forge_count: 1,
			latest_forge: {
				id: 'forge-1',
				title: 'My Forge Title',
				task_type: 'coding',
				complexity: 'medium',
				framework_applied: 'chain-of-thought',
				overall_score: 0.8,
				is_improvement: true,
				tags: [],
				version: null,
			},
		};

		await openPromptInIDE({
			promptId: 'prompt-1',
			projectId: 'proj-1',
			prompt,
		});

		expect(openDocument).toHaveBeenCalled();
	});
});
