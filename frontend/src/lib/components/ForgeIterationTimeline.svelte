<script lang="ts">
	import { optimizationState, type OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { normalizeScore, getScoreColorClass } from '$lib/utils/format';
	import { Tooltip } from './ui';

	let {
		currentId,
		onselect,
	}: {
		currentId?: string;
		onselect?: (result: OptimizationResultState) => void;
	} = $props();

	let items = $derived(optimizationState.resultHistory);
	let hasItems = $derived(items.length > 1);
</script>

{#if hasItems}
	<div class="px-2.5 py-1.5">
		<span class="text-[8px] uppercase tracking-wider text-text-dim/50 font-bold">Iterations</span>
		<div class="flex items-center gap-1 mt-1 overflow-x-auto">
			{#each items as item, i}
				{@const score = normalizeScore(item.scores.overall)}
				{@const colorClass = getScoreColorClass(item.scores.overall)}
				{@const isCurrent = item.id === currentId}
				<!-- Connector line (not for first item) -->
				{#if i > 0}
					<div class="w-3 h-px bg-text-dim/20 shrink-0"></div>
				{/if}
				<Tooltip text="{item.strategy || 'auto'}: {score ?? '?'}/100">
					<button
						onclick={() => onselect?.(item)}
						class="relative shrink-0 flex items-center justify-center rounded-full transition-all duration-150
							{isCurrent ? 'ring-1 ring-neon-cyan/50 scale-110' : 'hover:scale-110'}"
						style="width: 18px; height: 18px; background-color: color-mix(in srgb, var(--color-{colorClass}) 20%, transparent); border: 1px solid var(--color-{colorClass})"
						aria-label="Iteration {items.length - i}: score {score}"
					>
						<span class="text-[7px] font-mono font-bold" style="color: var(--color-{colorClass})">
							{score ?? '?'}
						</span>
					</button>
				</Tooltip>
			{/each}
		</div>
	</div>
{/if}
