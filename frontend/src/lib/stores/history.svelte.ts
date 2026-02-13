import { fetchHistory, deleteOptimization, clearAllHistory, type HistoryItem, type HistoryResponse } from '$lib/api/client';

class HistoryState {
	items: HistoryItem[] = $state([]);
	total: number = $state(0);
	page: number = $state(1);
	perPage: number = $state(20);
	isLoading: boolean = $state(false);
	hasLoaded: boolean = $state(false);
	sortBy: string = $state('created_at');
	sortOrder: string = $state('desc');

	async loadHistory(params?: { page?: number; search?: string; sort?: string; order?: string }) {
		if (this.isLoading) return;
		this.isLoading = true;

		try {
			const response: HistoryResponse = await fetchHistory({
				page: params?.page ?? 1,
				per_page: this.perPage,
				search: params?.search,
				sort: params?.sort ?? this.sortBy,
				order: params?.order ?? this.sortOrder
			});
			this.items = response.items;
			this.total = response.total;
			this.page = response.page;
			this.perPage = response.per_page;
			this.hasLoaded = true;
		} catch {
			// Silently fail - items stay empty
		} finally {
			this.isLoading = false;
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
		}
		return success;
	}

	setSortBy(sort: string) {
		this.sortBy = sort;
		this.sortOrder = 'desc';
		this.loadHistory({ sort, order: this.sortOrder });
	}

	addEntry(item: HistoryItem) {
		this.items = [item, ...this.items];
		this.total += 1;
	}
}

export const historyState = new HistoryState();
