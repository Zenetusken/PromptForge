<script lang="ts">
	import { goto } from '$app/navigation';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { truncateText, formatRelativeTime, formatExactTime, normalizeScore, getScoreBadgeClass } from '$lib/utils/format';
	import type { HistorySummaryItem } from '$lib/api/client';
	import Icon from './Icon.svelte';
	import { EntryTitle, Tooltip } from './ui';

	let { item }: { item: HistorySummaryItem } = $props();

	let isProjectArchived = $derived(item.project_status === 'archived');

	let confirmDeleteId: string | null = $state(null);

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
		promptState.set(
			item.raw_prompt,
			isProjectArchived ? '' : (item.project ?? ''),
			isProjectArchived ? '' : (item.prompt_id ?? ''),
			{
				title: item.title ?? '',
				tags: item.tags ?? [],
				version: item.version ?? '',
				sourceAction: 'optimize',
			},
		);
		goto('/');
	}

	function handleCardClick() {
		goto(`/optimize/${item.id}`);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && confirmDeleteId) {
			e.stopPropagation();
			confirmDeleteId = null;
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="sidebar-card group relative mb-0.5 w-full cursor-pointer rounded-xl
		border border-transparent p-3 text-left
		transition-[background-color,border-color,border-left-color,box-shadow] duration-200
		hover:border-border-glow hover:bg-bg-hover/40
		has-[:focus-visible]:border-neon-cyan/40 has-[:focus-visible]:bg-bg-hover/20 has-[:focus-visible]:shadow-[0_0_12px_rgba(0,229,255,0.08)]
		active:bg-bg-hover/60"
	style="--sidebar-accent: var(--color-neon-cyan)"
	onclick={handleCardClick}
	onkeydown={handleKeydown}
	data-testid="history-entry"
>
	<!-- Stretched link: primary click target covering the whole card -->
	<a
		href="/optimize/{item.id}"
		class="absolute inset-0 z-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-neon-cyan/40"
		aria-label={item.title || truncateText(item.raw_prompt, 55)}
	></a>
	<div class="mb-0.5">
		<span class="flex items-center gap-1.5 text-sm leading-snug {item.status === 'error' ? 'text-text-dim' : isProjectArchived ? 'text-text-secondary/70' : 'text-text-primary'}" data-testid="history-entry-text">
			{#if item.status === 'error'}
				<Tooltip text="Failed"><span class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-red shadow-[0_0_4px_var(--color-neon-red)]"></span></Tooltip>
			{:else if item.status === 'running'}
				<Tooltip text="Running"><span class="mt-0.5 h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-neon-yellow shadow-[0_0_4px_var(--color-neon-yellow)]"></span></Tooltip>
			{/if}
			<EntryTitle title={item.title} maxLength={55} class="truncate" />
			{#if isProjectArchived}
				<Tooltip text="{item.project} (archived)"><span class="shrink-0 rounded bg-neon-yellow/8 px-1 py-px text-[9px] font-medium text-neon-yellow/50">archived</span></Tooltip>
			{/if}
		</span>
	</div>
	<div class="flex items-center justify-between gap-2">
		<div class="flex min-w-0 items-center gap-0 overflow-hidden">
			<Tooltip text={formatExactTime(item.created_at)}><span class="shrink-0 text-[11px] text-text-dim" data-testid="history-entry-time">
				{formatRelativeTime(item.created_at)}
			</span></Tooltip>
			{#if item.task_type}
				<span class="metadata-separator" aria-hidden="true"></span>
				<Tooltip text="Task type"><span class="shrink-0 font-mono text-[11px] font-semibold text-neon-cyan" data-testid="history-entry-task-type">
					{item.task_type}
				</span></Tooltip>
			{/if}
			{#if item.framework_applied}
				<span class="metadata-separator" aria-hidden="true"></span>
				<Tooltip text="Strategy applied"><span class="shrink-0 text-[11px] text-neon-purple" data-testid="history-entry-strategy">
					{item.framework_applied}
				</span></Tooltip>
			{/if}
		</div>
		{#if item.status !== 'error' && item.overall_score !== null && item.overall_score !== undefined}
			<Tooltip text="Overall score: {normalizeScore(item.overall_score)}/10" class="shrink-0">
				<span class="score-circle score-circle-sm {getScoreBadgeClass(item.overall_score)}" data-testid="history-entry-score">
					{normalizeScore(item.overall_score)}
				</span>
			</Tooltip>
		{/if}
	</div>

	{#if item.project || (item.tags && item.tags.length > 0)}
		<div class="mt-0.5 flex items-center gap-2 overflow-hidden text-[11px]">
			{#if item.project}
				{#if item.project_id}
					<Tooltip text={isProjectArchived ? `${item.project} (archived)` : item.project}>
					<a
						href="/projects/{item.project_id}"
						onclick={(e) => e.stopPropagation()}
						class="relative z-[1] shrink-0 font-medium transition-colors hover:underline
							{isProjectArchived ? 'text-neon-yellow/50' : 'text-neon-yellow'}"
						data-testid="history-entry-project"
					>
						{item.project}
					</a>
					</Tooltip>
				{:else}
					<span class="shrink-0 font-medium text-neon-yellow" data-testid="history-entry-project">
						{item.project}
					</span>
				{/if}
			{/if}
			{#if item.tags && item.tags.length > 0}
				{#each item.tags.slice(0, 2) as tag}
					<span class="tag-chip shrink-0">#{tag}</span>
				{/each}
				{#if item.tags.length > 2}
					<Tooltip text="{item.tags.length - 2} more tags">
						<span class="shrink-0 text-text-dim">+{item.tags.length - 2}</span>
					</Tooltip>
				{/if}
			{/if}
		</div>
	{:else}
		<div class="mt-0.5 truncate text-[11px] text-text-dim">
			{truncateText(item.raw_prompt, 60)}
		</div>
	{/if}

	<!-- Action buttons overlay (contained to card via inset-0 + overflow:hidden) -->
	{#if confirmDeleteId !== item.id}
		<div class="sidebar-card-overlay absolute inset-0 z-10 flex flex-col justify-between rounded-xl bg-bg-card px-3 pt-2 pb-2.5">
			<div class="min-h-0 overflow-hidden">
				<div class="flex items-start justify-between gap-1 text-text-primary">
					<EntryTitle title={item.title} class="min-w-0 truncate text-sm leading-snug" />
					{#if item.status !== 'error' && item.overall_score !== null && item.overall_score !== undefined}
						<span class="score-circle score-circle-sm shrink-0 {getScoreBadgeClass(item.overall_score)}">
							{normalizeScore(item.overall_score)}
						</span>
					{/if}
				</div>
			</div>
			<div class="flex items-center gap-1">
				<Tooltip text="Optimize the original prompt again">
				<button
					class="sidebar-action-btn text-neon-cyan bg-neon-cyan/8
						hover:bg-neon-cyan/15 active:bg-neon-cyan/22 transition-colors"
					onclick={(e) => handleReforge(e)}
					data-testid="reforge-btn"
				>
					<Icon name="refresh" size={12} />
					Re-forge
				</button>
				</Tooltip>
				<Tooltip text="Edit prompt and re-optimize">
				<button
					class="sidebar-action-btn text-neon-purple bg-neon-purple/8
						hover:bg-neon-purple/15 active:bg-neon-purple/22 transition-colors"
					onclick={(e) => handleEditReforge(e)}
					aria-label="Iterate"
					data-testid="iterate-btn"
				>
					<Icon name="edit" size={12} />
					Edit
				</button>
				</Tooltip>
				<Tooltip text="Remove from history" class="ml-auto">
				<button
					class="sidebar-action-btn text-neon-red bg-neon-red/8
						hover:bg-neon-red/15 active:bg-neon-red/22 transition-colors"
					onclick={(e) => requestDelete(e)}
					aria-label="Delete entry"
					data-testid="delete-entry-btn"
				>
					<Icon name="x" size={12} />
					Delete
				</button>
				</Tooltip>
			</div>
		</div>
	{/if}

	<!-- Delete confirmation overlay -->
	{#if confirmDeleteId === item.id}
		<div class="delete-confirm-bar absolute inset-x-0 bottom-0 z-20 flex items-center justify-between
			rounded-b-xl px-2.5 py-1 animate-slide-up-in">
			<span class="text-[11px] font-medium text-neon-red">Delete this entry?</span>
			<div class="flex items-center gap-1">
				<button
					class="rounded-lg px-2 py-0.5 text-[11px] bg-neon-red/15 text-neon-red
						hover:bg-neon-red/25 active:bg-neon-red/35 transition-colors
						focus-visible:outline-offset-0"
					onclick={(e) => confirmDelete(e)}
					data-testid="confirm-delete-btn"
				>
					Delete
				</button>
				<button
					class="rounded-lg px-2 py-0.5 text-[11px] bg-bg-hover text-text-dim
						hover:bg-bg-hover/80 active:bg-bg-hover/60 transition-colors
						focus-visible:outline-offset-0"
					onclick={(e) => cancelDelete(e)}
					data-testid="cancel-delete-btn"
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}
</div>
