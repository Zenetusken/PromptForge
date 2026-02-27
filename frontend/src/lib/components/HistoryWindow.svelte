<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import FileManagerView from './FileManagerView.svelte';
	import FileManagerRow from './FileManagerRow.svelte';
	import DesktopContextMenu from './DesktopContextMenu.svelte';
	import ConfirmModal from './ConfirmModal.svelte';
	import type { ColumnDef } from './FileManagerView.svelte';
	import type { ContextAction } from '$lib/stores/desktopStore.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { clipboardService } from '$lib/services/clipboardService.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { fetchOptimization, type HistoryItem, type HistorySummaryItem } from '$lib/api/client';
	import { formatRelativeTime, truncateText, normalizeScore, getScoreBadgeClass } from '$lib/utils/format';

	let searchInput = $state('');

	// ── Selection ──
	let selectedId: string | null = $state(null);

	// ── Context menu ──
	let ctxMenu = $state({ open: false, x: 0, y: 0, targetId: null as string | null, actions: [] as ContextAction[] });
	let confirmDeleteId: string | null = $state(null);

	function forgeEntryActions(item: HistorySummaryItem): ContextAction[] {
		const actions: ContextAction[] = [
			{ id: 'open', label: 'Open in IDE', icon: 'terminal' },
		];
		if (item.status !== 'error') {
			actions.push(
				{ id: 're-forge', label: 'Re-forge', icon: 'refresh', separator: true },
				{ id: 'iterate', label: 'Iterate', icon: 'bolt' },
				{ id: 'copy-result', label: 'Copy Result', icon: 'copy' },
			);
		}
		actions.push({ id: 'delete', label: 'Delete', icon: 'trash-2', separator: true, danger: true });
		return actions;
	}

	function openCtxMenu(e: MouseEvent, id: string, actions: ContextAction[]) {
		ctxMenu = { open: true, x: e.clientX, y: e.clientY, targetId: id, actions };
	}

	function closeCtxMenu() {
		ctxMenu = { open: false, x: 0, y: 0, targetId: null, actions: [] };
	}

	async function fetchAndAct(id: string, action: (item: HistoryItem) => void) {
		const item = await fetchOptimization(id);
		if (item) action(item);
		else toastState.show('Failed to load forge details', 'error');
	}

	function handleContextAction(actionId: string) {
		const targetId = ctxMenu.targetId;
		closeCtxMenu();
		if (!targetId) return;

		const summaryItem = historyState.items.find((i) => i.id === targetId);

		switch (actionId) {
			case 'open':
				optimizationState.openInIDEFromHistory(targetId);
				break;
			case 're-forge':
				if (summaryItem) {
					optimizationState.retryOptimization(targetId, summaryItem.raw_prompt);
				}
				break;
			case 'iterate':
				fetchAndAct(targetId, (item) => {
					if (item.optimized_prompt) {
						forgeSession.loadRequest({
							text: item.optimized_prompt,
							title: item.title ?? undefined,
							project: item.project ?? undefined,
							sourceAction: 'reiterate',
						});
					} else {
						toastState.show('No optimized prompt to iterate on', 'info');
					}
				});
				break;
			case 'copy-result':
				fetchAndAct(targetId, (item) => {
					if (item.optimized_prompt) {
						clipboardService.copy(item.optimized_prompt, 'Optimized prompt');
						toastState.show('Optimized prompt copied', 'success');
					} else {
						toastState.show('No optimized prompt to copy', 'info');
					}
				});
				break;
			case 'delete':
				confirmDeleteId = targetId;
				break;
		}
	}

	async function handleConfirmDelete() {
		if (confirmDeleteId) {
			const ok = await historyState.removeEntry(confirmDeleteId);
			confirmDeleteId = null;
			if (ok) toastState.show('Forge entry deleted', 'success');
			else toastState.show('Failed to delete forge entry', 'error');
		}
	}

	const columns: ColumnDef[] = [
		{ key: 'overall_score', label: 'Score', width: 'w-12', align: 'center' },
		{ key: 'title', label: 'Title', width: 'flex-1' },
		{ key: 'task_type', label: 'Type', width: 'w-20' },
		{ key: 'project', label: 'Project', width: 'w-24' },
		{ key: 'created_at', label: 'Date', width: 'w-20' },
	];

	function handleSearch(value: string) {
		searchInput = value;
		historyState.setSearch(value);
	}

	function handleSort(key: string) {
		historyState.setSortField(key);
	}

	function handleItemClick(id: string) {
		optimizationState.openInIDEFromHistory(id);
	}

	onMount(() => {
		windowManager.setBreadcrumbs('history', [
			{ label: 'Desktop', icon: 'monitor', action: () => windowManager.closeWindow('history') },
			{ label: 'History' },
		]);
		windowManager.setNavigation('history', {
			canGoBack: false,
			canGoForward: false,
			goBack: () => {},
			goForward: () => {},
		});
	});

	onDestroy(() => {
		windowManager.clearNavigation('history');
	});
</script>

<FileManagerView
	{columns}
	sortKey={historyState.sortBy}
	sortOrder={historyState.sortOrder}
	onsort={handleSort}
	itemCount={historyState.total}
	itemLabel="forge"
	isLoading={historyState.isLoading && !historyState.hasLoaded}
	hasMore={historyState.items.length < historyState.total}
	onloadmore={() => historyState.loadHistory({ page: historyState.page + 1 })}
	onbackgroundclick={() => selectedId = null}
	emptyIcon="clock"
	emptyMessage={historyState.searchQuery ? 'No matching forges' : 'No forges yet'}
>
	{#snippet toolbar()}
		<div class="relative">
			<input
				type="text"
				placeholder="Search..."
				class="h-6 w-32 rounded border border-border-subtle bg-bg-input px-2 text-[10px] text-text-primary placeholder:text-text-dim/40 focus:border-neon-cyan/30 focus:outline-none"
				value={searchInput}
				oninput={(e) => handleSearch(e.currentTarget.value)}
			/>
		</div>
	{/snippet}

	{#snippet rows()}
		{#each historyState.items as item (item.id)}
			<FileManagerRow onselect={() => selectedId = item.id} onopen={() => handleItemClick(item.id)} oncontextmenu={(e) => openCtxMenu(e, item.id, forgeEntryActions(item))} active={selectedId === item.id} testId="history-row-{item.id}">
				<div class="w-12 flex justify-center">
					{#if item.overall_score != null}
						<span class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums {getScoreBadgeClass(item.overall_score)}">
							{normalizeScore(item.overall_score)}
						</span>
					{:else if item.status === 'error'}
						<span class="shrink-0 rounded bg-neon-red/10 px-1.5 py-0.5 text-[10px] font-bold text-neon-red">
							ERR
						</span>
					{:else}
						<span class="text-text-dim/30">—</span>
					{/if}
				</div>
				<div class="flex-1 min-w-0">
					<span class="text-xs text-text-primary truncate block">
						{item.title || truncateText(item.raw_prompt, 60)}
					</span>
				</div>
				<div class="w-20 text-[10px] text-text-dim truncate">
					{item.task_type ?? '—'}
				</div>
				<div class="w-24 text-[10px] text-text-dim truncate">
					{item.project ?? '—'}
				</div>
				<div class="w-20 text-[10px] text-text-dim">
					{formatRelativeTime(item.created_at)}
				</div>
			</FileManagerRow>
		{/each}
	{/snippet}
</FileManagerView>

<DesktopContextMenu
	open={ctxMenu.open}
	x={ctxMenu.x}
	y={ctxMenu.y}
	actions={ctxMenu.actions}
	onaction={handleContextAction}
	onclose={closeCtxMenu}
/>

<ConfirmModal
	open={confirmDeleteId !== null}
	title="Delete Forge"
	message="Permanently delete this forge entry? This cannot be undone."
	confirmLabel="Delete"
	onconfirm={handleConfirmDelete}
	oncancel={() => confirmDeleteId = null}
/>
