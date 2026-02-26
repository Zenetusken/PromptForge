import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/api/client', () => ({
    fetchHistory: vi.fn(),
    deleteOptimization: vi.fn(),
    clearAllHistory: vi.fn(),
}));

import { historyState } from './history.svelte';
import { fetchHistory, deleteOptimization, clearAllHistory } from '$lib/api/client';

describe('HistoryState', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        // Reset state
        historyState.items = [];
        historyState.total = 0;
        historyState.page = 1;
        historyState.hasLoaded = false;
        historyState.searchQuery = '';
        historyState.filterTaskType = '';
        historyState.filterProject = '';
        historyState.filterProjectId = '';
        historyState.hideArchived = false;
    });

    describe('loadHistory', () => {
        it('fetches history and updates state', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [
                    { id: '1', created_at: '2024-01-01', raw_prompt: 'test', title: null, task_type: 'coding', complexity: null, project: null, tags: null, overall_score: 0.8, framework_applied: null, model_used: null, status: 'completed', error_message: null, prompt_id: null, project_id: null, project_status: null, strategy: null, secondary_frameworks: null, version: null },
                ],
                total: 1,
                page: 1,
                per_page: 20,
            });

            await historyState.loadHistory();

            expect(historyState.items).toHaveLength(1);
            expect(historyState.total).toBe(1);
            expect(historyState.hasLoaded).toBe(true);
            expect(historyState.isLoading).toBe(false);
        });

        it('deduplicates items when loading page > 1', async () => {
            historyState.items = [
                { id: '1', created_at: '', raw_prompt: '', title: null, task_type: null, complexity: null, project: null, tags: null, overall_score: null, framework_applied: null, model_used: null, status: 'completed', error_message: null, prompt_id: null, project_id: null, project_status: null, strategy: null, secondary_frameworks: null, version: null },
            ];

            vi.mocked(fetchHistory).mockResolvedValue({
                items: [
                    { id: '1', created_at: '', raw_prompt: '', title: null, task_type: null, complexity: null, project: null, tags: null, overall_score: null, framework_applied: null, model_used: null, status: 'completed', error_message: null, prompt_id: null, project_id: null, project_status: null, strategy: null, secondary_frameworks: null, version: null },
                    { id: '2', created_at: '', raw_prompt: '', title: null, task_type: null, complexity: null, project: null, tags: null, overall_score: null, framework_applied: null, model_used: null, status: 'completed', error_message: null, prompt_id: null, project_id: null, project_status: null, strategy: null, secondary_frameworks: null, version: null },
                ],
                total: 2,
                page: 2,
                per_page: 20,
            });

            await historyState.loadHistory({ page: 2 });

            expect(historyState.items).toHaveLength(2);
            expect(historyState.items.map(i => i.id)).toEqual(['1', '2']);
        });
    });

    describe('removeEntry', () => {
        it('removes item and decrements total on success', async () => {
            historyState.items = [
                { id: '1', created_at: '', raw_prompt: '', title: null, task_type: null, complexity: null, project: null, tags: null, overall_score: null, framework_applied: null, model_used: null, status: 'completed', error_message: null, prompt_id: null, project_id: null, project_status: null, strategy: null, secondary_frameworks: null, version: null },
                { id: '2', created_at: '', raw_prompt: '', title: null, task_type: null, complexity: null, project: null, tags: null, overall_score: null, framework_applied: null, model_used: null, status: 'completed', error_message: null, prompt_id: null, project_id: null, project_status: null, strategy: null, secondary_frameworks: null, version: null },
            ];
            historyState.total = 2;

            vi.mocked(deleteOptimization).mockResolvedValue(true);

            const result = await historyState.removeEntry('1');

            expect(result).toBe(true);
            expect(historyState.items).toHaveLength(1);
            expect(historyState.items[0].id).toBe('2');
            expect(historyState.total).toBe(1);
        });

        it('does not remove on failure', async () => {
            historyState.items = [
                { id: '1', created_at: '', raw_prompt: '', title: null, task_type: null, complexity: null, project: null, tags: null, overall_score: null, framework_applied: null, model_used: null, status: 'completed', error_message: null, prompt_id: null, project_id: null, project_status: null, strategy: null, secondary_frameworks: null, version: null },
            ];
            historyState.total = 1;

            vi.mocked(deleteOptimization).mockResolvedValue(false);

            const result = await historyState.removeEntry('1');

            expect(result).toBe(false);
            expect(historyState.items).toHaveLength(1);
            expect(historyState.total).toBe(1);
        });
    });

    describe('clearAll', () => {
        it('resets all state on success', async () => {
            historyState.items = [{ id: '1' } as any];
            historyState.total = 1;
            historyState.searchQuery = 'test';

            vi.mocked(clearAllHistory).mockResolvedValue(true);

            const result = await historyState.clearAll();

            expect(result).toBe(true);
            expect(historyState.items).toHaveLength(0);
            expect(historyState.total).toBe(0);
            expect(historyState.searchQuery).toBe('');
        });
    });

    describe('setHideArchived', () => {
        it('passes include_archived=false when hideArchived is true', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [],
                total: 0,
                page: 1,
                per_page: 20,
            });

            historyState.setHideArchived(true);
            // Wait for the loadHistory call triggered by setHideArchived
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ include_archived: false })
            );
        });

        it('passes include_archived=undefined when hideArchived is false', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [],
                total: 0,
                page: 1,
                per_page: 20,
            });

            historyState.setHideArchived(false);
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ include_archived: undefined })
            );
        });
    });

    describe('setFilterProjectId', () => {
        it('passes project_id to fetchHistory', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setFilterProjectId('proj-123');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.filterProjectId).toBe('proj-123');
            expect(historyState.filterProject).toBe('');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ project_id: 'proj-123', project: undefined })
            );
        });

        it('clears project_id filter with empty string', async () => {
            historyState.filterProjectId = 'proj-123';
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setFilterProjectId('');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.filterProjectId).toBe('');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ project_id: undefined })
            );
        });

        it('clears filterProject when setting filterProjectId', async () => {
            historyState.filterProject = 'My Project';
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setFilterProjectId('proj-456');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.filterProject).toBe('');
            expect(historyState.filterProjectId).toBe('proj-456');
        });
    });

    describe('setFilterProject', () => {
        it('passes project name to fetchHistory', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setFilterProject('My Project');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.filterProject).toBe('My Project');
            expect(historyState.filterProjectId).toBe('');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ project: 'My Project', project_id: undefined })
            );
        });

        it('clears project filter with empty string', async () => {
            historyState.filterProject = 'Old Project';
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setFilterProject('');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.filterProject).toBe('');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ project: undefined })
            );
        });
    });

    describe('setFilterTaskType', () => {
        it('passes task_type to fetchHistory', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setFilterTaskType('coding');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.filterTaskType).toBe('coding');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ task_type: 'coding' })
            );
        });

        it('clears task_type filter with empty string', async () => {
            historyState.filterTaskType = 'coding';
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setFilterTaskType('');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.filterTaskType).toBe('');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ task_type: undefined })
            );
        });
    });

    describe('setSearch', () => {
        it('passes search query to fetchHistory', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setSearch('hello world');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.searchQuery).toBe('hello world');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ search: 'hello world' })
            );
        });

        it('clears search with empty string', async () => {
            historyState.searchQuery = 'old query';
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setSearch('');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.searchQuery).toBe('');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ search: undefined })
            );
        });
    });

    describe('setSortField', () => {
        it('updates sort field and reloads, toggling order', async () => {
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setSortField('overall_score');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.sortBy).toBe('overall_score');
            expect(historyState.sortOrder).toBe('desc');
            expect(fetchHistory).toHaveBeenCalledWith(
                expect.objectContaining({ sort: 'overall_score', order: 'desc' })
            );
        });

        it('toggles to asc when same field clicked again', async () => {
            historyState.sortBy = 'overall_score';
            historyState.sortOrder = 'desc';
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setSortField('overall_score');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.sortOrder).toBe('asc');
        });

        it('resets to desc when switching to a different field', async () => {
            historyState.sortBy = 'overall_score';
            historyState.sortOrder = 'asc';
            vi.mocked(fetchHistory).mockResolvedValue({
                items: [], total: 0, page: 1, per_page: 20,
            });

            historyState.setSortField('created_at');
            await vi.waitFor(() => expect(fetchHistory).toHaveBeenCalled());

            expect(historyState.sortBy).toBe('created_at');
            expect(historyState.sortOrder).toBe('desc');
        });
    });

    describe('addEntry', () => {
        it('prepends item and increments total', () => {
            historyState.items = [{ id: '1' } as any];
            historyState.total = 1;

            historyState.addEntry({ id: '2' } as any);

            expect(historyState.items).toHaveLength(2);
            expect(historyState.items[0].id).toBe('2');
            expect(historyState.total).toBe(2);
        });
    });
});
