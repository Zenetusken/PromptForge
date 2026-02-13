<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';
	import HistorySearch from './HistorySearch.svelte';
	import HistoryEntry from './HistoryEntry.svelte';
	import HistoryEmptyState from './HistoryEmptyState.svelte';

	let { open = $bindable(true) }: { open: boolean } = $props();

	let searchQuery = $state('');
	let showClearConfirm = $state(false);

	let filteredItems = $derived(
		searchQuery
			? historyState.items.filter((item) =>
					item.raw_prompt.toLowerCase().includes(searchQuery.toLowerCase()) ||
					(item.title && item.title.toLowerCase().includes(searchQuery.toLowerCase()))
				)
			: historyState.items
	);

	async function confirmClearHistory() {
		showClearConfirm = false;
		await historyState.clearAll();
		searchQuery = '';
	}

	function cancelClearHistory() {
		showClearConfirm = false;
	}

	$effect(() => {
		if (open && !historyState.hasLoaded) {
			historyState.loadHistory();
		}
	});
</script>

<aside
	class="flex h-full shrink-0 flex-col border-r border-text-dim/20 bg-bg-secondary transition-all duration-300"
	class:w-72={open}
	class:w-0={!open}
	class:overflow-hidden={!open}
	data-testid="history-sidebar"
>
	<div class="flex h-14 items-center justify-between border-b border-text-dim/20 px-4">
		<span class="font-mono text-sm font-semibold text-text-secondary">History</span>
		<span class="rounded-full bg-bg-card px-2 py-0.5 font-mono text-xs text-text-dim" data-testid="history-count">
			{historyState.total}
		</span>
	</div>

	<HistorySearch bind:searchQuery bind:showClearConfirm />

	<!-- Clear History Confirmation Dialog -->
	{#if showClearConfirm}
		<div class="mx-3 mb-2 rounded-lg border border-neon-red/30 bg-neon-red/5 p-3" data-testid="clear-confirm-dialog">
			<p class="mb-2 text-xs text-neon-red font-semibold">Clear all history?</p>
			<p class="mb-3 text-xs text-text-dim">This will permanently delete all optimization records. This action cannot be undone.</p>
			<div class="flex gap-2">
				<button
					class="flex-1 rounded-md bg-neon-red/20 py-1.5 font-mono text-xs text-neon-red transition-colors hover:bg-neon-red/30"
					onclick={confirmClearHistory}
					data-testid="confirm-clear-btn"
				>
					Confirm
				</button>
				<button
					class="flex-1 rounded-md bg-text-dim/10 py-1.5 font-mono text-xs text-text-dim transition-colors hover:bg-text-dim/20"
					onclick={cancelClearHistory}
					data-testid="cancel-clear-btn"
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}

	<div class="flex-1 overflow-y-auto px-2 pb-2" data-testid="history-list">
		{#if historyState.isLoading && !historyState.hasLoaded}
			<div class="space-y-2 p-2" data-testid="history-skeleton">
				{#each [1, 2, 3, 4, 5] as _}
					<div class="rounded-lg p-3">
						<div class="skeleton mb-2 h-4 w-4/5"></div>
						<div class="flex items-center justify-between">
							<div class="skeleton h-3 w-16"></div>
							<div class="skeleton h-5 w-8 rounded-full"></div>
						</div>
					</div>
				{/each}
			</div>
		{:else if filteredItems.length === 0}
			<HistoryEmptyState {searchQuery} />
		{:else}
			{#each filteredItems as item (item.id)}
				<HistoryEntry {item} />
			{/each}

			<!-- Load More button -->
			{#if historyState.total > historyState.items.length}
				<div class="py-2 text-center">
					<button
						class="font-mono text-xs text-text-dim transition-colors hover:text-neon-cyan"
						onclick={() => historyState.loadHistory({ page: historyState.page + 1 })}
						data-testid="load-more-btn"
					>
						Load more ({historyState.total - historyState.items.length} remaining)
					</button>
				</div>
			{/if}
		{/if}
	</div>
</aside>
