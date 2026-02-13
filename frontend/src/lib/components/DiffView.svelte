<script lang="ts">
	import { computeDiff, type DiffSegment } from '$lib/utils/diff';

	let {
		original,
		optimized
	}: {
		original: string;
		optimized: string;
	} = $props();

	let viewMode = $state<'unified' | 'side-by-side'>('unified');
	let segments = $derived(computeDiff(original, optimized));
</script>

<div>
	<div class="mb-3 flex items-center gap-2">
		<button
			class="rounded-md px-3 py-1 font-mono text-xs transition-colors {viewMode === 'unified' ? 'bg-neon-purple/20 text-neon-purple' : 'text-text-dim'}"
			onclick={() => (viewMode = 'unified')}
		>
			Unified
		</button>
		<button
			class="rounded-md px-3 py-1 font-mono text-xs transition-colors {viewMode === 'side-by-side' ? 'bg-neon-purple/20 text-neon-purple' : 'text-text-dim'}"
			onclick={() => (viewMode = 'side-by-side')}
		>
			Side by Side
		</button>
	</div>

	{#if viewMode === 'unified'}
		<div class="rounded-lg bg-bg-input p-4 font-mono text-sm">
			{#each segments as segment}
				{#if segment.type === 'removed'}
					<span class="bg-neon-red/10 text-neon-red line-through">{segment.value}</span>
				{:else if segment.type === 'added'}
					<span class="bg-neon-green/10 text-neon-green">{segment.value}</span>
				{:else}
					<span class="text-text-secondary">{segment.value}</span>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="grid grid-cols-2 gap-3">
			<div>
				<div class="mb-1 font-mono text-xs text-text-dim">Original</div>
				<div class="rounded-lg bg-bg-input p-4 font-mono text-sm">
					{#each segments as segment}
						{#if segment.type === 'removed'}
							<span class="bg-neon-red/10 text-neon-red">{segment.value}</span>
						{:else if segment.type === 'equal'}
							<span class="text-text-secondary">{segment.value}</span>
						{/if}
					{/each}
				</div>
			</div>
			<div>
				<div class="mb-1 font-mono text-xs text-text-dim">Optimized</div>
				<div class="rounded-lg bg-bg-input p-4 font-mono text-sm">
					{#each segments as segment}
						{#if segment.type === 'added'}
							<span class="bg-neon-green/10 text-neon-green">{segment.value}</span>
						{:else if segment.type === 'equal'}
							<span class="text-text-secondary">{segment.value}</span>
						{/if}
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>
