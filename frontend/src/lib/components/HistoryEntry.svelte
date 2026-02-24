<script lang="ts">
	import { goto } from "$app/navigation";
	import { optimizationState } from "$lib/stores/optimization.svelte";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { historyState } from "$lib/stores/history.svelte";
	import {
		truncateText,
		formatRelativeTime,
		formatExactTime,
		normalizeScore,
		getScoreBadgeClass,
	} from "$lib/utils/format";
	import type { HistorySummaryItem } from "$lib/api/client";
	import Icon from "./Icon.svelte";
	import { EntryTitle, Tooltip, MetaBadge } from "./ui";

	let { item }: { item: HistorySummaryItem } = $props();

	let isProjectArchived = $derived(item.project_status === "archived");

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
		forgeSession.activate();
	}

	function handleEditReforge(e: Event) {
		e.stopPropagation();
		forgeSession.loadRequest({
			text: item.raw_prompt,
			project: isProjectArchived ? "" : (item.project ?? ""),
			promptId: isProjectArchived ? "" : (item.prompt_id ?? ""),
			title: item.title ?? "",
			tags: (item.tags ?? []).join(", "),
			version: item.version ?? "",
			sourceAction: "optimize",
		});
		forgeSession.activate();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === "Escape" && confirmDeleteId) {
			e.stopPropagation();
			confirmDeleteId = null;
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="sidebar-card group relative mb-0.5 w-full cursor-pointer rounded-lg
		border border-transparent p-1.5 text-left
		transition-[background-color,border-color,border-left-color] duration-200
		hover:border-[var(--sidebar-accent)] hover:bg-bg-hover/40
		has-[:focus-visible]:border-neon-cyan/40 has-[:focus-visible]:bg-bg-hover/20
		active:bg-bg-hover/60
		{confirmDeleteId ? 'z-[2]' : ''}"
	style="--sidebar-accent: var(--color-neon-cyan)"
	onkeydown={handleKeydown}
	data-testid="history-entry"
>
	<!-- Stretched link: primary click target covering the whole card -->
	<a
		href="/optimize/{item.id}"
		class="absolute inset-0 z-0 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-neon-cyan/40"
		aria-label={item.title || truncateText(item.raw_prompt, 55)}
	></a>
	<div class="mb-0.5">
		<span
			class="flex items-center gap-1.5 text-[12px] leading-snug {item.status ===
			'error'
				? 'text-text-dim'
				: isProjectArchived
					? 'text-text-secondary/70'
					: 'text-text-primary'}"
			data-testid="history-entry-text"
		>
			{#if item.status === "error"}
				<Tooltip text="Failed"
					><span
						class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-red"
					></span></Tooltip
				>
			{:else if item.status === "running"}
				<Tooltip text="Running"
					><span
						class="mt-0.5 h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-neon-yellow"
					></span></Tooltip
				>
			{/if}
			<EntryTitle title={item.title} maxLength={55} class="truncate" />
			{#if isProjectArchived}
				<Tooltip text="{item.project} (archived)"
					><span
						class="shrink-0 rounded bg-neon-yellow/8 px-1 py-px text-[9px] font-medium text-neon-yellow/50"
						>archived</span
					></Tooltip
				>
			{/if}
		</span>
	</div>
	<div class="flex items-center justify-between gap-2">
		<div class="flex min-w-0 items-center gap-0 overflow-hidden">
			<Tooltip text={formatExactTime(item.created_at)}
				><span
					class="shrink-0 text-[11px] text-text-dim"
					data-testid="history-entry-time"
				>
					{formatRelativeTime(item.created_at)}
				</span></Tooltip
			>
			{#if item.task_type}
				<span class="metadata-separator" aria-hidden="true"></span>
				<MetaBadge type="task" value={item.task_type} size="xs" />
			{/if}
			{#if item.framework_applied}
				<span class="metadata-separator" aria-hidden="true"></span>
				<MetaBadge
					type="strategy"
					value={item.framework_applied}
					size="xs"
				/>
			{/if}
		</div>
		{#if item.status !== "error" && item.overall_score !== null && item.overall_score !== undefined}
			<Tooltip
				text="Overall score: {normalizeScore(item.overall_score)}/10"
				class="shrink-0"
			>
				<span
					class="score-circle score-circle-sm {getScoreBadgeClass(
						item.overall_score,
					)}"
					data-testid="history-entry-score"
				>
					{normalizeScore(item.overall_score)}
				</span>
			</Tooltip>
		{/if}
	</div>

	{#if item.project || (item.tags && item.tags.length > 0)}
		<div class="mt-0.5 flex items-center gap-2 overflow-hidden text-[11px]">
			{#if item.project}
				{#if item.project_id}
					<Tooltip
						text={isProjectArchived
							? `${item.project} (archived)`
							: item.project}
					>
						<a
							href="/projects/{item.project_id}"
							onclick={(e) => e.stopPropagation()}
							class="relative z-[1] max-w-[12ch] truncate font-medium transition-colors hover:underline
							{isProjectArchived ? 'text-neon-yellow/50' : 'text-neon-yellow'}"
							data-testid="history-entry-project"
						>
							{item.project}
						</a>
					</Tooltip>
				{:else}
					<Tooltip text={item.project}>
						<span
							class="max-w-[12ch] truncate font-medium text-neon-yellow"
							data-testid="history-entry-project"
						>
							{item.project}
						</span>
					</Tooltip>
				{/if}
			{/if}
			{#if item.tags && item.tags.length > 0}
				{#each item.tags.slice(0, 2) as tag}
					<MetaBadge
						type="tag"
						value={tag}
						variant="pill"
						showTooltip={false}
						size="xs"
					/>
				{/each}
				{#if item.tags.length > 2}
					<Tooltip text="{item.tags.length - 2} more tags">
						<span class="shrink-0 text-text-dim"
							>+{item.tags.length - 2}</span
						>
					</Tooltip>
				{/if}
			{/if}
		</div>
	{:else}
		<div class="mt-0.5 truncate text-[11px] text-text-dim">
			{truncateText(item.raw_prompt, 60)}
		</div>
	{/if}

	<!-- Floating action pill overlay -->
	{#if confirmDeleteId !== item.id}
		<div
			class="sidebar-card-overlay absolute right-1.5 top-1.5 z-10 flex items-center gap-0.5 rounded-lg border border-border-subtle bg-bg-card/90 p-0.5 backdrop-blur-md"
		>
			<Tooltip text="Re-forge" side="top" interactive>
				<button
					class="flex h-5 w-5 items-center justify-center rounded-md text-neon-cyan bg-neon-cyan/5 hover:bg-neon-cyan/15 active:bg-neon-cyan/25 transition-colors focus-visible:outline-offset-0 focus-visible:ring-1 focus-visible:ring-neon-cyan"
					onclick={(e) => handleReforge(e)}
					aria-label="Re-forge"
					data-testid="reforge-btn"
				>
					<Icon name="refresh" size={12} />
				</button>
			</Tooltip>
			<Tooltip text="Edit & Iterate" side="top" interactive>
				<button
					class="flex h-5 w-5 items-center justify-center rounded-md text-neon-purple bg-neon-purple/5 hover:bg-neon-purple/15 active:bg-neon-purple/25 transition-colors focus-visible:outline-offset-0 focus-visible:ring-1 focus-visible:ring-neon-purple"
					onclick={(e) => handleEditReforge(e)}
					aria-label="Edit"
					data-testid="iterate-btn"
				>
					<Icon name="edit" size={12} />
				</button>
			</Tooltip>
			<Tooltip text="Delete" side="top" interactive>
				<button
					class="flex h-5 w-5 items-center justify-center rounded-md text-neon-red bg-neon-red/5 hover:bg-neon-red/15 active:bg-neon-red/25 transition-colors focus-visible:outline-offset-0 focus-visible:ring-1 focus-visible:ring-neon-red"
					onclick={(e) => requestDelete(e)}
					aria-label="Delete"
					data-testid="delete-entry-btn"
				>
					<Icon name="x" size={12} />
				</button>
			</Tooltip>
		</div>
	{/if}

	<!-- Delete confirmation overlay -->
	{#if confirmDeleteId === item.id}
		<div
			class="delete-confirm-bar absolute inset-x-0 bottom-0 z-20 flex items-center justify-between
			rounded-b-xl px-2 py-0.5 animate-slide-up-in"
		>
			<span class="text-[11px] font-medium text-neon-red"
				>Delete this entry?</span
			>
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
