import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/api/client', () => ({
	fetchProjects: vi.fn(),
	fetchProject: vi.fn(),
	createProject: vi.fn(),
	updateProject: vi.fn(),
	deleteProject: vi.fn(),
	archiveProject: vi.fn(),
	unarchiveProject: vi.fn(),
	addProjectPrompt: vi.fn(),
	updateProjectPrompt: vi.fn(),
	deleteProjectPrompt: vi.fn(),
	reorderProjectPrompts: vi.fn(),
}));

vi.mock('$lib/stores/history.svelte', () => ({
	historyState: { loadHistory: vi.fn() },
}));

import { projectsState } from './projects.svelte';
import {
	fetchProjects,
	fetchProject,
	createProject,
	updateProject,
	deleteProject,
	archiveProject,
	unarchiveProject,
	addProjectPrompt,
	updateProjectPrompt,
	deleteProjectPrompt,
	reorderProjectPrompts,
} from '$lib/api/client';
import { historyState } from '$lib/stores/history.svelte';

const mockProject = (overrides = {}) => ({
	id: 'p1',
	name: 'Test Project',
	description: null,
	status: 'active',
	prompt_count: 0,
	has_context: false,
	created_at: '2024-01-01T00:00:00Z',
	updated_at: '2024-01-01T00:00:00Z',
	...overrides,
});

const mockDetail = (overrides = {}) => ({
	...mockProject(),
	context_profile: null,
	prompts: [],
	...overrides,
});

const mockPrompt = (overrides = {}) => ({
	id: 'prm-1',
	content: 'test prompt',
	version: 1,
	project_id: 'p1',
	order_index: 0,
	created_at: '2024-01-01T00:00:00Z',
	updated_at: '2024-01-01T00:00:00Z',
	forge_count: 0,
	latest_forge: null,
	...overrides,
});

describe('ProjectsState', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		projectsState.items = [];
		projectsState.total = 0;
		projectsState.page = 1;
		projectsState.hasLoaded = false;
		projectsState.isLoading = false;
		projectsState.searchQuery = '';
		projectsState.activeProject = null;
		projectsState.activeProjectLoading = false;
		projectsState.allItems = [];
		projectsState.allItemsLoaded = false;
	});

	describe('loadProjects', () => {
		it('fetches projects and updates state', async () => {
			vi.mocked(fetchProjects).mockResolvedValue({
				items: [mockProject()],
				total: 1,
				page: 1,
				per_page: 20,
			});

			await projectsState.loadProjects();

			expect(projectsState.items).toHaveLength(1);
			expect(projectsState.total).toBe(1);
			expect(projectsState.hasLoaded).toBe(true);
			expect(projectsState.isLoading).toBe(false);
		});

		it('replaces items on page 1', async () => {
			projectsState.items = [mockProject({ id: 'old' })];

			vi.mocked(fetchProjects).mockResolvedValue({
				items: [mockProject({ id: 'new' })],
				total: 1,
				page: 1,
				per_page: 20,
			});

			await projectsState.loadProjects();

			expect(projectsState.items).toHaveLength(1);
			expect(projectsState.items[0].id).toBe('new');
		});

		it('appends and deduplicates on page > 1', async () => {
			projectsState.items = [mockProject({ id: 'p1' })];

			vi.mocked(fetchProjects).mockResolvedValue({
				items: [mockProject({ id: 'p1' }), mockProject({ id: 'p2' })],
				total: 2,
				page: 2,
				per_page: 20,
			});

			await projectsState.loadProjects({ page: 2 });

			expect(projectsState.items).toHaveLength(2);
			expect(projectsState.items.map((p) => p.id)).toEqual(['p1', 'p2']);
		});

		it('ignores abort errors', async () => {
			const abortError = new DOMException('Aborted', 'AbortError');
			vi.mocked(fetchProjects).mockRejectedValue(abortError);

			await projectsState.loadProjects();

			expect(projectsState.isLoading).toBe(false);
			expect(projectsState.hasLoaded).toBe(false);
		});

		it('passes status filter and search to API', async () => {
			projectsState.searchQuery = 'test';
			projectsState.statusFilter = 'archived';

			vi.mocked(fetchProjects).mockResolvedValue({
				items: [],
				total: 0,
				page: 1,
				per_page: 20,
			});

			await projectsState.loadProjects();

			expect(fetchProjects).toHaveBeenCalledWith(
				expect.objectContaining({
					search: 'test',
					status: 'archived',
				}),
			);
		});
	});

	describe('loadAllProjects', () => {
		it('fetches active and archived projects', async () => {
			vi.mocked(fetchProjects)
				.mockResolvedValueOnce({
					items: [mockProject({ id: 'a1' })],
					total: 1,
					page: 1,
					per_page: 100,
				})
				.mockResolvedValueOnce({
					items: [mockProject({ id: 'a2', status: 'archived' })],
					total: 1,
					page: 1,
					per_page: 100,
				});

			await projectsState.loadAllProjects();

			expect(projectsState.allItems).toHaveLength(2);
			expect(projectsState.allItemsLoaded).toBe(true);
		});

		it('skips if already loaded', async () => {
			projectsState.allItemsLoaded = true;

			await projectsState.loadAllProjects();

			expect(fetchProjects).not.toHaveBeenCalled();
		});
	});

	describe('setSearch', () => {
		it('updates searchQuery and triggers load', async () => {
			vi.mocked(fetchProjects).mockResolvedValue({
				items: [],
				total: 0,
				page: 1,
				per_page: 20,
			});

			projectsState.setSearch('hello');

			expect(projectsState.searchQuery).toBe('hello');
			await vi.waitFor(() => expect(fetchProjects).toHaveBeenCalled());
		});
	});

	describe('setStatusFilter', () => {
		it('updates filter, resets state, and triggers load', async () => {
			projectsState.items = [mockProject()];
			projectsState.total = 5;
			projectsState.hasLoaded = true;

			vi.mocked(fetchProjects).mockResolvedValue({
				items: [],
				total: 0,
				page: 1,
				per_page: 20,
			});

			projectsState.setStatusFilter('archived');

			expect(projectsState.statusFilter).toBe('archived');
			expect(projectsState.items).toHaveLength(0);
			expect(projectsState.total).toBe(0);
			expect(projectsState.hasLoaded).toBe(false);
		});
	});

	describe('setSortField', () => {
		it('updates sort state and triggers load', async () => {
			vi.mocked(fetchProjects).mockResolvedValue({
				items: [], total: 0, page: 1, per_page: 20,
			});

			projectsState.setSortField('name');
			await vi.waitFor(() => expect(fetchProjects).toHaveBeenCalled());

			expect(projectsState.sortBy).toBe('name');
			expect(projectsState.sortOrder).toBe('desc');
			expect(fetchProjects).toHaveBeenCalledWith(
				expect.objectContaining({ sort: 'name', order: 'desc' })
			);
		});

		it('toggles to asc when same field clicked again', async () => {
			projectsState.sortBy = 'name';
			projectsState.sortOrder = 'desc';
			vi.mocked(fetchProjects).mockResolvedValue({
				items: [], total: 0, page: 1, per_page: 20,
			});

			projectsState.setSortField('name');
			await vi.waitFor(() => expect(fetchProjects).toHaveBeenCalled());

			expect(projectsState.sortOrder).toBe('asc');
		});
	});

	describe('loadProject', () => {
		it('fetches and sets activeProject', async () => {
			const detail = mockDetail({ id: 'p1', name: 'Loaded' });
			vi.mocked(fetchProject).mockResolvedValue(detail);

			await projectsState.loadProject('p1');

			expect(projectsState.activeProject).toEqual(detail);
			expect(projectsState.activeProjectLoading).toBe(false);
		});

		it('sets loading state during fetch', async () => {
			let resolve: (v: any) => void;
			vi.mocked(fetchProject).mockReturnValue(
				new Promise((r) => {
					resolve = r;
				}),
			);

			const promise = projectsState.loadProject('p1');
			expect(projectsState.activeProjectLoading).toBe(true);

			resolve!(mockDetail());
			await promise;
			expect(projectsState.activeProjectLoading).toBe(false);
		});
	});

	describe('create', () => {
		it('creates project and reloads list', async () => {
			const detail = mockDetail({ id: 'new', name: 'New' });
			vi.mocked(createProject).mockResolvedValue(detail);
			vi.mocked(fetchProjects).mockResolvedValue({
				items: [mockProject({ id: 'new' })],
				total: 1,
				page: 1,
				per_page: 20,
			});

			const result = await projectsState.create('New');

			expect(createProject).toHaveBeenCalledWith({ name: 'New', description: undefined });
			expect(result).toEqual(detail);
			expect(projectsState.allItemsLoaded).toBe(false);
		});

		it('returns null when API fails', async () => {
			vi.mocked(createProject).mockResolvedValue(null);

			const result = await projectsState.create('Fail');

			expect(result).toBeNull();
		});
	});

	describe('update', () => {
		it('updates project and sets activeProject', async () => {
			projectsState.activeProject = mockDetail({ id: 'p1', updated_at: '2024-01-01T00:00:00Z' });
			const updated = mockDetail({ id: 'p1', name: 'Updated' });
			vi.mocked(updateProject).mockResolvedValue(updated);
			vi.mocked(fetchProjects).mockResolvedValue({
				items: [],
				total: 0,
				page: 1,
				per_page: 20,
			});

			const result = await projectsState.update('p1', { name: 'Updated' });

			expect(result).toEqual(updated);
			expect(projectsState.activeProject).toEqual(updated);
			expect(updateProject).toHaveBeenCalledWith('p1', { name: 'Updated' }, '2024-01-01T00:00:00Z');
		});

		it('invalidates allItems when name changes', async () => {
			projectsState.allItemsLoaded = true;
			projectsState.activeProject = mockDetail({ id: 'p1' });
			vi.mocked(updateProject).mockResolvedValue(mockDetail({ id: 'p1', name: 'Renamed' }));
			vi.mocked(fetchProjects).mockResolvedValue({ items: [], total: 0, page: 1, per_page: 20 });

			await projectsState.update('p1', { name: 'Renamed' });

			expect(projectsState.allItemsLoaded).toBe(false);
		});
	});

	describe('remove', () => {
		it('removes project from items and decrements total', async () => {
			projectsState.items = [mockProject({ id: 'p1' }), mockProject({ id: 'p2' })];
			projectsState.total = 2;

			vi.mocked(deleteProject).mockResolvedValue(true);

			const result = await projectsState.remove('p1');

			expect(result).toBe(true);
			expect(projectsState.items).toHaveLength(1);
			expect(projectsState.items[0].id).toBe('p2');
			expect(projectsState.total).toBe(1);
		});

		it('clears activeProject if it was the deleted one', async () => {
			projectsState.activeProject = mockDetail({ id: 'p1' });
			projectsState.items = [mockProject({ id: 'p1' })];
			projectsState.total = 1;
			vi.mocked(deleteProject).mockResolvedValue(true);

			await projectsState.remove('p1');

			expect(projectsState.activeProject).toBeNull();
		});

		it('refreshes history after successful deletion', async () => {
			projectsState.items = [mockProject({ id: 'p1' })];
			projectsState.total = 1;
			vi.mocked(deleteProject).mockResolvedValue(true);

			await projectsState.remove('p1');

			expect(historyState.loadHistory).toHaveBeenCalled();
		});

		it('does not modify state on failure', async () => {
			projectsState.items = [mockProject({ id: 'p1' })];
			projectsState.total = 1;
			vi.mocked(deleteProject).mockResolvedValue(false);

			const result = await projectsState.remove('p1');

			expect(result).toBe(false);
			expect(projectsState.items).toHaveLength(1);
			expect(projectsState.total).toBe(1);
			expect(historyState.loadHistory).not.toHaveBeenCalled();
		});
	});

	describe('archive', () => {
		it('removes from active list and updates activeProject status', async () => {
			projectsState.statusFilter = 'active';
			projectsState.items = [mockProject({ id: 'p1' }), mockProject({ id: 'p2' })];
			projectsState.total = 2;
			projectsState.activeProject = mockDetail({ id: 'p1' });

			vi.mocked(archiveProject).mockResolvedValue({
				message: 'Project archived',
				id: 'p1',
				status: 'archived',
				updated_at: '2024-06-01T00:00:00Z',
			});

			const result = await projectsState.archive('p1');

			expect(result).toBeTruthy();
			expect(projectsState.items).toHaveLength(1);
			expect(projectsState.items[0].id).toBe('p2');
			expect(projectsState.total).toBe(1);
			expect(projectsState.activeProject?.status).toBe('archived');
			expect(projectsState.allItemsLoaded).toBe(false);
		});

		it('reloads list when viewing archived tab', async () => {
			projectsState.statusFilter = 'archived';
			projectsState.items = [];
			projectsState.total = 0;

			vi.mocked(archiveProject).mockResolvedValue({
				message: 'Project archived',
				id: 'p1',
				status: 'archived',
				updated_at: '2024-06-01T00:00:00Z',
			});
			vi.mocked(fetchProjects).mockResolvedValue({ items: [], total: 0, page: 1, per_page: 20 });

			await projectsState.archive('p1');

			expect(fetchProjects).toHaveBeenCalled();
		});
	});

	describe('unarchive', () => {
		it('removes from archived list and updates activeProject status', async () => {
			projectsState.statusFilter = 'archived';
			projectsState.items = [mockProject({ id: 'p1', status: 'archived' })];
			projectsState.total = 1;
			projectsState.activeProject = mockDetail({ id: 'p1', status: 'archived' });

			vi.mocked(unarchiveProject).mockResolvedValue({
				message: 'Project unarchived',
				id: 'p1',
				status: 'active',
				updated_at: '2024-06-01T00:00:00Z',
			});

			const result = await projectsState.unarchive('p1');

			expect(result).toBeTruthy();
			expect(projectsState.items).toHaveLength(0);
			expect(projectsState.total).toBe(0);
			expect(projectsState.activeProject?.status).toBe('active');
		});
	});

	describe('addPrompt', () => {
		it('appends prompt to activeProject and increments count', async () => {
			projectsState.activeProject = mockDetail({ id: 'p1', prompts: [] });
			projectsState.items = [mockProject({ id: 'p1', prompt_count: 0 })];

			const newPrompt = mockPrompt({ id: 'prm-new' });
			vi.mocked(addProjectPrompt).mockResolvedValue(newPrompt);

			const result = await projectsState.addPrompt('p1', 'new content');

			expect(result).toEqual(newPrompt);
			expect(projectsState.activeProject?.prompts).toHaveLength(1);
			expect(projectsState.items[0].prompt_count).toBe(1);
		});

		it('does not modify state when API returns null', async () => {
			projectsState.activeProject = mockDetail({ id: 'p1', prompts: [] });
			vi.mocked(addProjectPrompt).mockResolvedValue(null);

			await projectsState.addPrompt('p1', 'content');

			expect(projectsState.activeProject?.prompts).toHaveLength(0);
		});

		it('does not modify state when project mismatch', async () => {
			projectsState.activeProject = mockDetail({ id: 'p2', prompts: [] });
			projectsState.items = [mockProject({ id: 'p1', prompt_count: 0 })];

			vi.mocked(addProjectPrompt).mockResolvedValue(mockPrompt());

			await projectsState.addPrompt('p1', 'content');

			// activeProject is p2, so no prompts added there
			expect(projectsState.activeProject?.prompts).toHaveLength(0);
		});
	});

	describe('updatePrompt', () => {
		it('replaces prompt in activeProject', async () => {
			const original = mockPrompt({ id: 'prm-1', content: 'old' });
			projectsState.activeProject = mockDetail({ id: 'p1', prompts: [original] });

			const updated = mockPrompt({ id: 'prm-1', content: 'new', version: 2 });
			vi.mocked(updateProjectPrompt).mockResolvedValue(updated);

			const result = await projectsState.updatePrompt('p1', 'prm-1', 'new');

			expect(result).toEqual(updated);
			expect(projectsState.activeProject?.prompts[0].content).toBe('new');
			expect(projectsState.activeProject?.prompts[0].version).toBe(2);
		});
	});

	describe('removePrompt', () => {
		it('removes prompt from activeProject and decrements count', async () => {
			projectsState.activeProject = mockDetail({
				id: 'p1',
				prompts: [mockPrompt({ id: 'prm-1' }), mockPrompt({ id: 'prm-2' })],
			});
			projectsState.items = [mockProject({ id: 'p1', prompt_count: 2 })];

			vi.mocked(deleteProjectPrompt).mockResolvedValue(true);

			const result = await projectsState.removePrompt('p1', 'prm-1');

			expect(result).toBe(true);
			expect(projectsState.activeProject?.prompts).toHaveLength(1);
			expect(projectsState.activeProject?.prompts[0].id).toBe('prm-2');
			expect(projectsState.items[0].prompt_count).toBe(1);
		});
	});

	describe('reorderPrompts', () => {
		it('reorders prompts in activeProject', async () => {
			projectsState.activeProject = mockDetail({
				id: 'p1',
				prompts: [
					mockPrompt({ id: 'a', order_index: 0 }),
					mockPrompt({ id: 'b', order_index: 1 }),
				],
			});

			vi.mocked(reorderProjectPrompts).mockResolvedValue(true);

			const result = await projectsState.reorderPrompts('p1', ['b', 'a']);

			expect(result).toBe(true);
			expect(projectsState.activeProject?.prompts[0].id).toBe('b');
			expect(projectsState.activeProject?.prompts[0].order_index).toBe(0);
			expect(projectsState.activeProject?.prompts[1].id).toBe('a');
			expect(projectsState.activeProject?.prompts[1].order_index).toBe(1);
		});

		it('does not modify state on failure', async () => {
			projectsState.activeProject = mockDetail({
				id: 'p1',
				prompts: [
					mockPrompt({ id: 'a', order_index: 0 }),
					mockPrompt({ id: 'b', order_index: 1 }),
				],
			});

			vi.mocked(reorderProjectPrompts).mockResolvedValue(false);

			await projectsState.reorderPrompts('p1', ['b', 'a']);

			expect(projectsState.activeProject?.prompts[0].id).toBe('a');
		});
	});
});
