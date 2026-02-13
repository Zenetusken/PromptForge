<script lang="ts">
	import { goto } from '$app/navigation';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { truncateText, formatRelativeTime, normalizeScore, getScoreColorClass } from '$lib/utils/format';
	import type { HistoryItem } from '$lib/api/client';

	let { item }: { item: HistoryItem } = $props();

	let confirmDeleteId: string | null = $state(null);

	function getScoreClass(score: number | null): string {
		if (score === null) return 'bg-text-dim/10 text-text-dim';
		const color = getScoreColorClass(score);
		return `bg-${color}/10 text-${color}`;
	}

	function loadEntry() {
		goto(`/optimize/${item.id}`);
	}

	function requestDelete(e: Event) {
		e.stopPropagation();
		confirmDeleteId = item.id;
	}

	async function confirmDelete(e: Event) {
		e.stopPropagation();
		confirmDeleteId = null;
		await historyState.removeEntry(item.id);
	}

	function cancelDelete(e: Event) {
		e.stopPropagation();
		confirmDeleteId = null;
	}

	function handleReforge(e: Event) {
		e.stopPropagation();
		optimizationState.retryOptimization(item.id, item.raw_prompt);
		goto('/');
	}

	function handleEditReforge(e: Event) {
		e.stopPropagation();
		promptState.set(item.raw_prompt);
		goto('/');
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="group mb-1 w-full cursor-pointer rounded-lg p-3 text-left transition-colors hover:bg-bg-hover"
	onclick={loadEntry}
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadEntry(); } }}
	role="button"
	tabindex="0"
	data-testid="history-entry"
>
	<div class="mb-1 flex items-start justify-between gap-1">
		<span class="flex items-center gap-1.5 text-sm {item.status === 'error' ? 'text-text-dim' : 'text-text-primary'}" data-testid="history-entry-text">
			{#if item.status === 'error'}
				<span class="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-neon-red shadow-[0_0_4px_var(--color-neon-red)]" title="Failed"></span>
			{:else if item.status === 'running'}
				<span class="mt-0.5 h-2 w-2 shrink-0 animate-pulse rounded-full bg-neon-yellow shadow-[0_0_4px_var(--color-neon-yellow)]" title="Running"></span>
			{/if}
			{truncateText(item.title || item.raw_prompt, 55)}
		</span>
		<div class="flex shrink-0 items-center gap-1">
			{#if confirmDeleteId === item.id}
				<button
					class="rounded px-1.5 py-0.5 text-[10px] bg-neon-red/20 text-neon-red hover:bg-neon-red/30"
					onclick={(e) => confirmDelete(e)}
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
					onclick={(e) => requestDelete(e)}
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
			{#if item.project}
				<span class="rounded bg-neon-yellow/10 px-1 py-0.5 font-mono text-[10px] text-neon-yellow" data-testid="history-entry-project">
					{item.project}
				</span>
			{/if}
		</div>
		{#if item.status !== 'error' && item.overall_score !== null && item.overall_score !== undefined}
			<span class="rounded-full px-1.5 py-0.5 font-mono text-xs {getScoreClass(item.overall_score)}" data-testid="history-entry-score">
				{normalizeScore(item.overall_score)}
			</span>
		{/if}
	</div>

	{#if item.tags && item.tags.length > 0}
		<div class="mt-1 flex flex-wrap gap-1">
			{#each item.tags.slice(0, 3) as tag}
				<span class="rounded bg-neon-purple/10 px-1 py-0.5 font-mono text-[10px] text-neon-purple">
					#{tag}
				</span>
			{/each}
			{#if item.tags.length > 3}
				<span class="font-mono text-[10px] text-text-dim">+{item.tags.length - 3}</span>
			{/if}
		</div>
	{/if}

	<!-- Action buttons (re-forge, edit & re-forge) -->
	<div class="mt-2 hidden items-center gap-1 group-hover:flex">
		<button
			class="rounded px-2 py-0.5 font-mono text-[10px] text-neon-cyan bg-neon-cyan/10 hover:bg-neon-cyan/20 transition-colors"
			onclick={(e) => handleReforge(e)}
			data-testid="reforge-btn"
		>
			Re-forge
		</button>
		<button
			class="rounded px-2 py-0.5 font-mono text-[10px] text-neon-purple bg-neon-purple/10 hover:bg-neon-purple/20 transition-colors"
			onclick={(e) => handleEditReforge(e)}
			data-testid="edit-reforge-btn"
		>
			Edit & Re-forge
		</button>
	</div>
</div>
