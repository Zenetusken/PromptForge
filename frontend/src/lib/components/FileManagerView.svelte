<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	export interface ColumnDef {
		key: string;
		label: string;
		width?: string;
		sortable?: boolean;
		align?: 'left' | 'right' | 'center';
	}

	let {
		columns,
		sortKey,
		sortOrder,
		onsort,
		itemCount,
		itemLabel,
		isLoading,
		hasMore = false,
		onloadmore,
		emptyIcon = 'folder',
		emptyMessage = 'No items',
		onbackgroundclick,
		toolbar,
		rows,
	}: {
		columns: ColumnDef[];
		sortKey: string;
		sortOrder: 'asc' | 'desc';
		onsort: (key: string) => void;
		itemCount: number;
		itemLabel: string;
		isLoading: boolean;
		hasMore?: boolean;
		onloadmore?: () => void;
		emptyIcon?: string;
		emptyMessage?: string;
		onbackgroundclick?: () => void;
		toolbar?: Snippet;
		rows: Snippet;
	} = $props();

	function alignClass(col: ColumnDef): string {
		if (col.align === 'right') return 'text-right';
		if (col.align === 'center') return 'text-center';
		return 'text-left';
	}
</script>

<div class="flex h-full flex-col">
	<!-- Toolbar -->
	<div class="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
		<span class="text-xs text-text-secondary shrink-0">
			{itemCount} {itemLabel}{itemCount === 1 ? '' : 's'}
		</span>
		<div class="flex-1"></div>
		{#if toolbar}
			{@render toolbar()}
		{/if}
	</div>

	<!-- Column headers -->
	<div class="flex items-center gap-3 h-7 bg-bg-secondary/50 border-b border-border-subtle/30 px-3">
		{#each columns as col (col.key)}
			{@const isSortable = col.sortable !== false}
			{@const isActive = sortKey === col.key}
			<div class="{col.width ?? 'flex-1'} min-w-0 {alignClass(col)}">
				{#if isSortable}
					<button
						class="inline-flex items-center gap-0.5 text-[10px] font-medium uppercase tracking-wider transition-colors {isActive ? 'text-neon-cyan' : 'text-text-dim hover:text-text-secondary'}"
						onclick={() => onsort(col.key)}
					>
						{col.label}
						{#if isActive}
							<Icon name={sortOrder === 'asc' ? 'chevron-up' : 'chevron-down'} size={9} />
						{/if}
					</button>
				{:else}
					<span class="text-[10px] font-medium uppercase tracking-wider text-text-dim">
						{col.label}
					</span>
				{/if}
			</div>
		{/each}
	</div>

	<!-- Scrollable content -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="flex-1 overflow-y-auto py-1" onclick={onbackgroundclick}>
		{#if isLoading && itemCount === 0}
			<div class="flex flex-col items-center justify-center gap-2 pt-16 text-text-dim">
				<Icon name="loader" size={24} class="animate-spin opacity-30" />
				<span class="text-xs">Loading...</span>
			</div>
		{:else if itemCount === 0}
			<div class="flex flex-col items-center justify-center gap-2 pt-16 text-text-dim">
				<Icon name={emptyIcon as any} size={32} class="opacity-30" />
				<span class="text-xs">{emptyMessage}</span>
			</div>
		{:else}
			<div class="flex flex-col">
				{@render rows()}

				{#if hasMore && onloadmore}
					<button
						class="mx-auto mt-2 rounded px-3 py-1 text-[10px] text-text-dim transition-colors hover:bg-bg-hover hover:text-text-secondary"
						onclick={onloadmore}
						disabled={isLoading}
					>
						{isLoading ? 'Loading...' : 'Load more'}
					</button>
				{/if}
			</div>
		{/if}
	</div>
</div>
