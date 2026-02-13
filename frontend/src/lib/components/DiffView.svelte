<script lang="ts">
	import { computeDiff, computeLineDiff, type DiffSegment } from '$lib/utils/diff';

	let {
		original,
		optimized
	}: {
		original: string;
		optimized: string;
	} = $props();

	let viewMode = $state<'unified' | 'side-by-side'>('side-by-side');
	let segments = $derived(computeDiff(original, optimized));
	let lineDiff = $derived(computeLineDiff(original, optimized));

	// Refs for synchronized scrolling
	let leftPanel: HTMLDivElement | undefined = $state(undefined);
	let rightPanel: HTMLDivElement | undefined = $state(undefined);
	let isSyncing = false;

	function syncScroll(source: 'left' | 'right') {
		if (isSyncing) return;
		isSyncing = true;
		const from = source === 'left' ? leftPanel : rightPanel;
		const to = source === 'left' ? rightPanel : leftPanel;
		if (from && to) {
			to.scrollTop = from.scrollTop;
		}
		requestAnimationFrame(() => {
			isSyncing = false;
		});
	}
</script>

<div data-testid="diff-view">
	<div class="mb-3 flex items-center gap-2" data-testid="diff-toggle">
		<button
			class="rounded-md px-3 py-1 font-mono text-xs transition-colors {viewMode === 'side-by-side' ? 'bg-neon-purple/20 text-neon-purple' : 'text-text-dim hover:text-text-secondary'}"
			onclick={() => (viewMode = 'side-by-side')}
			data-testid="diff-side-by-side-btn"
		>
			Side by Side
		</button>
		<button
			class="rounded-md px-3 py-1 font-mono text-xs transition-colors {viewMode === 'unified' ? 'bg-neon-purple/20 text-neon-purple' : 'text-text-dim hover:text-text-secondary'}"
			onclick={() => (viewMode = 'unified')}
			data-testid="diff-inline-btn"
		>
			Inline
		</button>
	</div>

	{#if viewMode === 'unified'}
		<div class="whitespace-pre-wrap rounded-lg bg-bg-input p-4 font-mono text-sm" data-testid="diff-inline">
			{#each segments as segment}
				{#if segment.type === 'removed'}
					<span class="bg-neon-red/15 text-neon-red line-through">{segment.value}</span>
				{:else if segment.type === 'added'}
					<span class="bg-neon-green/15 text-neon-green">{segment.value}</span>
				{:else}
					<span class="text-text-secondary">{segment.value}</span>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="grid grid-cols-2 gap-3" data-testid="diff-side-by-side">
			<div>
				<div class="mb-1 font-mono text-xs text-text-dim">Original</div>
				<div
					bind:this={leftPanel}
					onscroll={() => syncScroll('left')}
					class="rounded-lg bg-bg-input p-4 font-mono text-sm overflow-y-auto"
					style="max-height: 460px;"
					data-testid="diff-left-panel"
				>
					{#each lineDiff.left as line}
						<div class="flex {line.type === 'removed' ? 'bg-neon-red/10' : ''}">
							<span class="mr-3 inline-block w-6 shrink-0 select-none text-right text-text-dim/50 text-xs leading-relaxed" data-testid="line-number">{line.lineNumber}</span>
							{#if line.type === 'removed'}
								<span class="flex-1 text-neon-red leading-relaxed">{line.text || '\u00A0'}</span>
							{:else}
								<span class="flex-1 text-text-secondary leading-relaxed">{line.text || '\u00A0'}</span>
							{/if}
						</div>
					{/each}
				</div>
			</div>
			<div>
				<div class="mb-1 font-mono text-xs text-text-dim">Optimized</div>
				<div
					bind:this={rightPanel}
					onscroll={() => syncScroll('right')}
					class="rounded-lg bg-bg-input p-4 font-mono text-sm overflow-y-auto"
					style="max-height: 460px;"
					data-testid="diff-right-panel"
				>
					{#each lineDiff.right as line}
						<div class="flex {line.type === 'added' ? 'bg-neon-green/10' : ''}">
							<span class="mr-3 inline-block w-6 shrink-0 select-none text-right text-text-dim/50 text-xs leading-relaxed" data-testid="line-number">{line.lineNumber}</span>
							{#if line.type === 'added'}
								<span class="flex-1 text-neon-green leading-relaxed">{line.text || '\u00A0'}</span>
							{:else}
								<span class="flex-1 text-text-secondary leading-relaxed">{line.text || '\u00A0'}</span>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>
