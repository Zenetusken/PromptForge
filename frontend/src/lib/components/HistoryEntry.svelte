<script lang="ts">
	import { goto } from '$app/navigation';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { truncateText, formatRelativeTime, normalizeScore, getScoreColorClass } from '$lib/utils/format';
	import type { HistorySummaryItem } from '$lib/api/client';
	import Icon from './Icon.svelte';

	let { item }: { item: HistorySummaryItem } = $props();

	let confirmDeleteId: string | null = $state(null);

	function getScoreClass(score: number | null): string {
		if (score === null) return 'bg-text-dim/10 text-text-dim';
		const color = getScoreColorClass(score);
		switch (color) {
			case 'neon-green': return 'bg-neon-green/10 text-neon-green';
			case 'neon-yellow': return 'bg-neon-yellow/10 text-neon-yellow';
			case 'neon-red': return 'bg-neon-red/10 text-neon-red';
			default: return 'bg-text-dim/10 text-text-dim';
		}
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
	class="group relative mb-0.5 w-full cursor-pointer rounded-xl border border-transparent p-3 text-left
		transition-[background-color,border-color,box-shadow] duration-200
		hover:border-border-glow hover:bg-bg-hover/40"
	onclick={loadEntry}
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadEntry(); } }}
	role="button"
	tabindex="0"
	data-testid="history-entry"
>
	<div class="mb-1 flex items-start justify-between gap-1">
		<span class="flex items-center gap-1.5 text-sm leading-snug {item.status === 'error' ? 'text-text-dim' : 'text-text-primary'}" data-testid="history-entry-text">
			{#if item.status === 'error'}
				<span class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-red shadow-[0_0_4px_var(--color-neon-red)]" title="Failed"></span>
			{:else if item.status === 'running'}
				<span class="mt-0.5 h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-neon-yellow shadow-[0_0_4px_var(--color-neon-yellow)]" title="Running"></span>
			{/if}
			{truncateText(item.title || item.raw_prompt, 55)}
		</span>
		<button
			class="mt-0.5 shrink-0 rounded-lg p-0.5 text-text-dim
				opacity-0 transition-[opacity,background-color,color] duration-150
				hover:bg-neon-red/10 hover:text-neon-red group-hover:opacity-100"
			onclick={(e) => requestDelete(e)}
			aria-label="Delete entry"
			data-testid="delete-entry-btn"
		>
			<Icon name="x" size={12} />
		</button>
	</div>
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-2">
			<span class="text-[11px] text-text-dim" data-testid="history-entry-time">
				{formatRelativeTime(item.created_at)}
			</span>
			{#if item.task_type}
				<span class="badge rounded-full bg-neon-cyan/10 text-neon-cyan" data-testid="history-entry-task-type">
					{item.task_type}
				</span>
			{/if}
			{#if item.project}
				<span class="badge rounded-full bg-neon-yellow/10 text-neon-yellow" data-testid="history-entry-project">
					{item.project}
				</span>
			{/if}
		</div>
		{#if item.status !== 'error' && item.overall_score !== null && item.overall_score !== undefined}
			<span class="rounded-full px-1.5 py-0.5 font-mono text-[11px] font-medium tabular-nums transition-opacity duration-150 group-hover:opacity-0 {getScoreClass(item.overall_score)}" data-testid="history-entry-score">
				{normalizeScore(item.overall_score)}
			</span>
		{/if}
	</div>

	{#if item.tags && item.tags.length > 0}
		<div class="mt-1.5 flex items-center gap-1 overflow-hidden">
			{#each item.tags.slice(0, 3) as tag}
				<span class="badge shrink-0 rounded-full bg-neon-purple/10 text-neon-purple">
					#{tag}
				</span>
			{/each}
			{#if item.tags.length > 3}
				<span class="badge shrink-0 rounded-full bg-text-dim/10 text-text-dim">+{item.tags.length - 3}</span>
			{/if}
		</div>
	{/if}

	<!-- Action buttons overlay (no layout shift) -->
	<div class="absolute inset-x-0 bottom-0 z-10 flex items-center gap-1 rounded-b-xl
		bg-bg-card px-3 py-2
		pointer-events-none opacity-0 transition-opacity duration-150
		group-hover:pointer-events-auto group-hover:opacity-100">
		<button
			class="btn-ghost py-0.5 text-[10px] text-neon-cyan bg-neon-cyan/8 hover:bg-neon-cyan/15 transition-colors"
			onclick={(e) => handleReforge(e)}
			data-testid="reforge-btn"
		>
			Re-forge
		</button>
		<button
			class="btn-ghost py-0.5 text-[10px] text-neon-green bg-neon-green/8 hover:bg-neon-green/15 transition-colors"
			onclick={(e) => handleEditReforge(e)}
			data-testid="edit-reforge-btn"
		>
			Edit & Re-forge
		</button>
		{#if item.status !== 'error' && item.overall_score !== null && item.overall_score !== undefined}
			<span class="ml-auto rounded-full px-1.5 py-0.5 font-mono text-[11px] font-medium tabular-nums {getScoreClass(item.overall_score)}">
				{normalizeScore(item.overall_score)}
			</span>
		{/if}
	</div>

	<!-- Delete confirmation overlay -->
	{#if confirmDeleteId === item.id}
		<div class="absolute inset-x-0 bottom-0 z-20 flex items-center justify-between
			rounded-b-xl bg-bg-card px-3 py-2
			border-t border-neon-red/15 animate-fade-in">
			<span class="text-[10px] font-medium text-neon-red">Delete this entry?</span>
			<div class="flex items-center gap-1">
				<button
					class="rounded-lg px-1.5 py-0.5 text-[10px] bg-neon-red/15 text-neon-red hover:bg-neon-red/25 transition-colors"
					onclick={(e) => confirmDelete(e)}
					data-testid="confirm-delete-btn"
				>
					Delete
				</button>
				<button
					class="rounded-lg px-1.5 py-0.5 text-[10px] bg-bg-hover text-text-dim hover:bg-bg-hover/80 transition-colors"
					onclick={(e) => cancelDelete(e)}
					data-testid="cancel-delete-btn"
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}
</div>
