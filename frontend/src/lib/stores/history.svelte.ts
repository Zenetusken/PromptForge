import { fetchHistory, deleteOptimization, type HistoryItem, type HistoryResponse } from '$lib/api/client';

class HistoryState {
	items: HistoryItem[] = $state([]);
	total: number = $state(0);
	page: number = $state(1);
	perPage: number = $state(20);
	isLoading: boolean = $state(false);
	hasLoaded: boolean = $state(false);

	async loadHistory(params?: { page?: number; search?: string }) {
		if (this.isLoading) return;
		this.isLoading = true;

		try {
			const response: HistoryResponse = await fetchHistory({
				page: params?.page ?? 1,
				per_page: this.perPage,
				search: params?.search
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

	addEntry(item: HistoryItem) {
		this.items = [item, ...this.items];
		this.total += 1;
	}
}

export const historyState = new HistoryState();
