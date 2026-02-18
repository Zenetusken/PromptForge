import { fetchHistory, deleteOptimization, clearAllHistory, type HistorySummaryItem, type HistoryResponse } from '$lib/api/client';

const HIDE_ARCHIVED_KEY = 'promptforge:hideArchived';

function loadHideArchived(): boolean {
	if (typeof window === 'undefined') return false;
	try {
		return localStorage.getItem(HIDE_ARCHIVED_KEY) === 'true';
	} catch {
		return false;
	}
}

function persistHideArchived(value: boolean): void {
	if (typeof window === 'undefined') return;
	try {
		if (value) {
			localStorage.setItem(HIDE_ARCHIVED_KEY, 'true');
		} else {
			localStorage.removeItem(HIDE_ARCHIVED_KEY);
		}
	} catch {
		// Ignore storage errors
	}
}

class HistoryState {
	items: HistorySummaryItem[] = $state([]);
	total: number = $state(0);
	page: number = $state(1);
	perPage: number = $state(20);
	isLoading: boolean = $state(false);
	hasLoaded: boolean = $state(false);
	sortBy: string = $state('created_at');
	sortOrder: string = $state('desc');
	searchQuery: string = $state('');
	filterTaskType: string = $state('');
	filterProject: string = $state('');
	filterProjectId: string = $state('');
	hideArchived: boolean = $state(loadHideArchived());
	availableTaskTypes: string[] = $state([]);

	private controller: AbortController | null = null;

	async loadHistory(params?: { page?: number; sort?: string; order?: string }) {
		// Abort any in-flight request before starting a new one
		this.controller?.abort();
		this.controller = new AbortController();
		const { signal } = this.controller;

		this.isLoading = true;
		const requestedPage = params?.page ?? 1;

		try {
			const response: HistoryResponse = await fetchHistory({
				page: requestedPage,
				per_page: this.perPage,
				search: this.searchQuery || undefined,
				sort: params?.sort ?? this.sortBy,
				order: params?.order ?? this.sortOrder,
				task_type: this.filterTaskType || undefined,
				project: this.filterProject || undefined,
				project_id: this.filterProjectId || undefined,
				include_archived: this.hideArchived ? false : undefined,
				signal
			});

			if (requestedPage > 1) {
				// Deduplicate when appending pages
				const existingIds = new Set(this.items.map(item => item.id));
				const newItems = response.items.filter(item => !existingIds.has(item.id));
				this.items = [...this.items, ...newItems];
			} else {
				this.items = response.items;
			}

			this.total = response.total;
			this.page = response.page;
			this.perPage = response.per_page;
			this.hasLoaded = true;
			this.updateAvailableFilters();
		} catch (e: unknown) {
			// Silently ignore aborted requests; other errors keep items empty
			if (e instanceof DOMException && e.name === 'AbortError') return;
		} finally {
			this.isLoading = false;
			this.controller = null;
		}
	}

	async removeEntry(id: string) {
		const success = await deleteOptimization(id);
		if (success) {
			this.items = this.items.filter((e) => e.id !== id);
			this.total = Math.max(0, this.total - 1);
		}
		return success;
	}

	async clearAll() {
		const success = await clearAllHistory();
		if (success) {
			this.items = [];
			this.total = 0;
			this.page = 1;
			this.searchQuery = '';
			this.filterTaskType = '';
			this.filterProject = '';
			this.filterProjectId = '';
			this.availableTaskTypes = [];
		}
		return success;
	}

	setSearch(query: string) {
		this.searchQuery = query;
		this.loadHistory();
	}

	setSortBy(sort: string) {
		this.sortBy = sort;
		this.sortOrder = 'desc';
		this.loadHistory({ sort, order: this.sortOrder });
	}

	setFilterTaskType(taskType: string) {
		this.filterTaskType = taskType;
		this.loadHistory();
	}

	setFilterProject(project: string) {
		this.filterProject = project;
		this.filterProjectId = '';
		this.loadHistory();
	}

	setFilterProjectId(projectId: string) {
		this.filterProjectId = projectId;
		this.filterProject = '';
		this.loadHistory();
	}

	setHideArchived(value: boolean) {
		this.hideArchived = value;
		persistHideArchived(value);
		this.loadHistory();
	}

	addEntry(item: HistorySummaryItem) {
		this.items = [item, ...this.items];
		this.total += 1;
		this.updateAvailableFilters();
	}

	private updateAvailableFilters() {
		const taskTypes = new Set<string>();
		for (const item of this.items) {
			if (item.task_type) taskTypes.add(item.task_type);
		}
		const newTaskTypes = [...taskTypes].sort();

		if (
			newTaskTypes.length !== this.availableTaskTypes.length ||
			newTaskTypes.some((v, i) => v !== this.availableTaskTypes[i])
		) {
			this.availableTaskTypes = newTaskTypes;
		}
	}
}

export const historyState = new HistoryState();
