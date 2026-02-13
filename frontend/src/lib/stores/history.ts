import { fetchHistory, deleteOptimization, type HistoryEntry } from '$lib/api/client';

class HistoryState {
	entries: HistoryEntry[] = $state([]);
	isLoading: boolean = $state(false);
	hasLoaded: boolean = $state(false);

	async loadHistory() {
		if (this.isLoading) return;
		this.isLoading = true;

		try {
			this.entries = await fetchHistory();
			this.hasLoaded = true;
		} catch {
			// Silently fail - entries stay empty
		} finally {
			this.isLoading = false;
		}
	}

	async removeEntry(id: string) {
		const success = await deleteOptimization(id);
		if (success) {
			this.entries = this.entries.filter((e) => e.id !== id);
		}
		return success;
	}

	addEntry(entry: HistoryEntry) {
		this.entries = [entry, ...this.entries];
	}
}

export const historyState = new HistoryState();
