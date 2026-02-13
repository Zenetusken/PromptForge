<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';
	import { optimizationState, setHistoryRefreshCallback } from '$lib/stores/optimization.svelte';
	import { truncateText, formatRelativeTime } from '$lib/utils/format';
	import type { HistoryItem } from '$lib/api/client';

	let { open = $bindable(true) }: { open: boolean } = $props();

	let searchQuery = $state('');
	let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	let confirmDeleteId: string | null = $state(null);
	let showClearConfirm = $state(false);

	let filteredItems = $derived(
		searchQuery
			? historyState.items.filter((item) =>
					item.raw_prompt.toLowerCase().includes(searchQuery.toLowerCase()) ||
					(item.title && item.title.toLowerCase().includes(searchQuery.toLowerCase()))
				)
			: historyState.items
	);

	function normalizeScore(score: number | null): number | null {
		if (score === null || score === undefined) return null;
		if (score <= 1) return Math.round(score * 100);
		return Math.round(score);
	}

	function getScoreClass(score: number | null): string {
		if (score === null) return 'bg-text-dim/10 text-text-dim';
		const pct = score <= 1 ? score * 100 : score;
		if (pct >= 70) return 'bg-neon-green/10 text-neon-green';
		if (pct >= 40) return 'bg-neon-yellow/10 text-neon-yellow';
		return 'bg-neon-red/10 text-neon-red';
	}

	function handleSearch() {
		if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		searchDebounceTimer = setTimeout(() => {
			historyState.loadHistory({ search: searchQuery || undefined });
		}, 300);
	}

	function loadEntry(item: HistoryItem) {
		optimizationState.loadFromHistory(item);
	}

	function requestDelete(e: Event, id: string) {
		e.stopPropagation();
		confirmDeleteId = id;
	}

	async function confirmDelete(e: Event, id: string) {
		e.stopPropagation();
		confirmDeleteId = null;
		await historyState.removeEntry(id);
	}

	function cancelDelete(e: Event) {
		e.stopPropagation();
		confirmDeleteId = null;
	}

	function handleReforge(e: Event, item: HistoryItem) {
		e.stopPropagation();
		optimizationState.startOptimization(item.raw_prompt);
	}

	function handleEditReforge(e: Event, item: HistoryItem) {
		e.stopPropagation();
		const textarea = document.querySelector('[data-testid="prompt-textarea"]') as HTMLTextAreaElement | null;
		if (textarea) {
			const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
			if (nativeInputValueSetter) {
				nativeInputValueSetter.call(textarea, item.raw_prompt);
				textarea.dispatchEvent(new Event('input', { bubbles: true }));
			}
			textarea.focus();
		}
	}

	function handleSortChange(e: Event) {
		const select = e.target as HTMLSelectElement;
		historyState.setSortBy(select.value);
	}

	function requestClearHistory() {
		showClearConfirm = true;
	}

	async function confirmClearHistory() {
		showClearConfirm = false;
		await historyState.clearAll();
	}

	function cancelClearHistory() {
		showClearConfirm = false;
	}

	// Register history refresh callback so optimization store can trigger reloads
	setHistoryRefreshCallback(() => {
		historyState.loadHistory();
	});

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

	<div class="p-3 space-y-2">
		<input
			type="text"
			bind:value={searchQuery}
			oninput={handleSearch}
			placeholder="Search history..."
			aria-label="Search optimization history"
			data-testid="history-search"
			class="search-input w-full rounded-lg border border-text-dim/20 bg-bg-input px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-dim focus:border-neon-cyan/60"
		/>
		<div class="flex items-center gap-2">
			<select
				value={historyState.sortBy}
				onchange={handleSortChange}
				aria-label="Sort history by"
				class="flex-1 rounded-lg border border-text-dim/20 bg-bg-input px-2 py-1.5 font-mono text-xs text-text-secondary outline-none focus:border-neon-cyan/40"
				data-testid="history-sort"
			>
				<option value="created_at">Date</option>
				<option value="overall_score">Score</option>
				<option value="task_type">Task Type</option>
			</select>
			<button
				class="rounded-lg border border-neon-red/20 px-2 py-1.5 font-mono text-xs text-neon-red transition-colors hover:bg-neon-red/10"
				onclick={requestClearHistory}
				aria-label="Clear all history"
				data-testid="clear-history-btn"
			>
				Clear
			</button>
		</div>
	</div>

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
			<div class="flex flex-col items-center justify-center py-10 text-center" data-testid="empty-state">
				<div class="mb-3 text-text-dim">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="32"
						height="32"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.5"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						{#if searchQuery}
							<circle cx="11" cy="11" r="8" />
							<line x1="21" y1="21" x2="16.65" y2="16.65" />
						{:else}
							<path d="M12 2L2 7l10 5 10-5-10-5z" />
							<path d="M2 17l10 5 10-5" />
							<path d="M2 12l10 5 10-5" />
						{/if}
					</svg>
				</div>
				{#if searchQuery}
					<p class="text-sm font-semibold text-text-secondary">No matching entries</p>
					<p class="mt-1 text-xs text-text-dim">Try a different search term</p>
				{:else}
					<p class="text-sm font-semibold text-text-secondary">No optimizations yet</p>
					<p class="mt-1 px-4 text-xs text-text-dim">Get started by pasting a prompt and clicking Forge It!</p>
				{/if}
			</div>
		{:else}
			{#each filteredItems as item (item.id)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="group mb-1 w-full cursor-pointer rounded-lg p-3 text-left transition-colors hover:bg-bg-hover"
					onclick={() => loadEntry(item)}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadEntry(item); } }}
					role="button"
					tabindex="0"
					data-testid="history-entry"
				>
					<div class="mb-1 flex items-start justify-between gap-1">
						<span class="text-sm text-text-primary" data-testid="history-entry-text">
							{truncateText(item.title || item.raw_prompt, 55)}
						</span>
						<div class="flex shrink-0 items-center gap-1">
							{#if confirmDeleteId === item.id}
								<button
									class="rounded px-1.5 py-0.5 text-[10px] bg-neon-red/20 text-neon-red hover:bg-neon-red/30"
									onclick={(e) => confirmDelete(e, item.id)}
									data-testid="confirm-delete-btn"
								>
									Delete?
								</button>
								<button
									class="rounded px-1.5 py-0.5 text-[10px] bg-text-dim/10 text-text-dim hover:bg-text-dim/20"
									onclick={(e) => cancelDelete(e)}
									data-testid="cancel-delete-btn"
								>
									Cancel
								</button>
							{:else}
								<button
									class="mt-0.5 hidden shrink-0 rounded p-0.5 text-text-dim transition-colors hover:bg-neon-red/10 hover:text-neon-red group-hover:block"
									onclick={(e) => requestDelete(e, item.id)}
									aria-label="Delete entry"
									data-testid="delete-entry-btn"
								>
									<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
										<line x1="18" y1="6" x2="6" y2="18" />
										<line x1="6" y1="6" x2="18" y2="18" />
									</svg>
								</button>
							{/if}
						</div>
					</div>
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2">
							<span class="text-xs text-text-dim" data-testid="history-entry-time">
								{formatRelativeTime(item.created_at)}
							</span>
							{#if item.task_type}
								<span class="rounded bg-bg-card px-1 py-0.5 font-mono text-[10px] text-text-dim" data-testid="history-entry-task-type">
									{item.task_type}
								</span>
							{/if}
						</div>
						{#if item.overall_score !== null && item.overall_score !== undefined}
							<span class="rounded-full px-1.5 py-0.5 font-mono text-xs {getScoreClass(item.overall_score)}" data-testid="history-entry-score">
								{normalizeScore(item.overall_score)}
							</span>
						{/if}
					</div>

					<!-- Action buttons (re-forge, edit & re-forge) -->
					<div class="mt-2 hidden items-center gap-1 group-hover:flex">
						<button
							class="rounded px-2 py-0.5 font-mono text-[10px] text-neon-cyan bg-neon-cyan/10 hover:bg-neon-cyan/20 transition-colors"
							onclick={(e) => handleReforge(e, item)}
							data-testid="reforge-btn"
						>
							Re-forge
						</button>
						<button
							class="rounded px-2 py-0.5 font-mono text-[10px] text-neon-purple bg-neon-purple/10 hover:bg-neon-purple/20 transition-colors"
							onclick={(e) => handleEditReforge(e, item)}
							data-testid="edit-reforge-btn"
						>
							Edit & Re-forge
						</button>
					</div>
				</div>
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

<style>
	.search-input:focus {
		box-shadow: 0 0 8px rgba(0, 240, 255, 0.3), 0 0 16px rgba(0, 240, 255, 0.1);
		border-color: rgba(0, 240, 255, 0.6);
	}
</style>
