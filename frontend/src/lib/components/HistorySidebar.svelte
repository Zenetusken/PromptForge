<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';
	import HistorySearch from './HistorySearch.svelte';
	import HistoryEntry from './HistoryEntry.svelte';
	import HistoryEmptyState from './HistoryEmptyState.svelte';

	let { open = $bindable(true) }: { open: boolean } = $props();

	let searchQuery = $state('');
	let showClearConfirm = $state(false);

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
	class="flex h-full shrink-0 flex-col border-r border-border-subtle bg-bg-secondary transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]"
	class:w-72={open}
	class:w-0={!open}
	class:overflow-hidden={!open}
	data-testid="history-sidebar"
>
	<div class="flex h-14 items-center justify-between border-b border-border-subtle px-4">
		<span class="section-heading-dim">History</span>
		<span class="rounded-full bg-bg-card px-2 py-0.5 font-mono text-[10px] tabular-nums text-text-dim" data-testid="history-count">
			{historyState.total}
		</span>
	</div>

	<HistorySearch bind:searchQuery bind:showClearConfirm />

	<!-- Clear History Confirmation Dialog -->
	{#if showClearConfirm}
		<div class="animate-fade-in mx-3 mb-2 rounded-xl border border-neon-red/20 bg-neon-red/5 p-3" data-testid="clear-confirm-dialog">
			<p class="mb-1.5 text-xs font-medium text-neon-red">Clear all history?</p>
			<p class="mb-3 text-[11px] leading-relaxed text-text-dim">This will permanently delete all optimization records.</p>
			<div class="flex gap-2">
				<button
					class="flex-1 rounded-lg bg-neon-red/15 py-1.5 text-xs font-medium text-neon-red transition-colors hover:bg-neon-red/25"
					onclick={confirmClearHistory}
					data-testid="confirm-clear-btn"
				>
					Confirm
				</button>
				<button
					class="flex-1 rounded-lg bg-bg-hover py-1.5 text-xs text-text-dim transition-colors hover:bg-bg-hover/80"
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
			<div class="space-y-1.5 p-2" data-testid="history-skeleton">
				{#each [1, 2, 3, 4, 5] as _}
					<div class="rounded-xl p-3">
						<div class="skeleton mb-2 h-4 w-4/5"></div>
						<div class="flex items-center justify-between">
							<div class="skeleton h-3 w-16"></div>
							<div class="skeleton h-5 w-8 rounded-full"></div>
						</div>
					</div>
				{/each}
			</div>
		{:else if historyState.items.length === 0}
			<HistoryEmptyState {searchQuery} />
		{:else}
			{#each historyState.items as item (item.id)}
				<HistoryEntry {item} />
			{/each}

			<!-- Load More button -->
			{#if historyState.total > historyState.items.length}
				<div class="py-3 text-center">
					<button
						class="text-xs text-text-dim transition-colors hover:text-neon-cyan"
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
