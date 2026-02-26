<script lang="ts">
	import { onMount } from 'svelte';
	import { computeDiff, computeLineDiff } from '$lib/utils/diff';

	let {
		original,
		optimized
	}: {
		original: string;
		optimized: string;
	} = $props();

	let viewMode = $state<'unified' | 'side-by-side'>('side-by-side');

	// Memoize diff computations — only recompute when input strings actually change
	let _prevOriginal = '';
	let _prevOptimized = '';
	let _cachedSegments: ReturnType<typeof computeDiff> = [];
	let _cachedLineDiff: ReturnType<typeof computeLineDiff> = { left: [], right: [] };

	let segments = $derived.by(() => {
		if (original === _prevOriginal && optimized === _prevOptimized && _cachedSegments.length > 0) {
			return _cachedSegments;
		}
		_prevOriginal = original;
		_prevOptimized = optimized;
		_cachedSegments = computeDiff(original, optimized);
		_cachedLineDiff = computeLineDiff(original, optimized);
		return _cachedSegments;
	});

	let lineDiff = $derived.by(() => {
		// Trigger segments first to ensure cache is populated
		void segments;
		return _cachedLineDiff;
	});

	// Default to unified on mobile after hydration to avoid SSR mismatch
	onMount(() => {
		if (window.innerWidth < 640) viewMode = 'unified';
	});

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
	<div class="mb-3 flex items-center gap-1" data-testid="diff-toggle">
		<button
			class="rounded-lg px-3 py-1.5 text-xs transition-[background-color,color] duration-200 {viewMode === 'side-by-side' ? 'bg-neon-purple/15 text-neon-purple' : 'text-text-dim hover:text-text-secondary'}"
			onclick={() => (viewMode = 'side-by-side')}
			data-testid="diff-side-by-side-btn"
		>
			Side by Side
		</button>
		<button
			class="rounded-lg px-3 py-1.5 text-xs transition-[background-color,color] duration-200 {viewMode === 'unified' ? 'bg-neon-purple/15 text-neon-purple' : 'text-text-dim hover:text-text-secondary'}"
			onclick={() => (viewMode = 'unified')}
			data-testid="diff-inline-btn"
		>
			Inline
		</button>
	</div>

	{#if viewMode === 'unified'}
		<div class="whitespace-pre-wrap rounded-xl bg-bg-input/60 p-4 font-mono text-sm leading-relaxed" data-testid="diff-inline">
			{#each segments as segment}
				{#if segment.type === 'removed'}
					<span class="rounded-sm bg-neon-red/15 text-neon-red line-through decoration-neon-red/30">{segment.value}</span>
				{:else if segment.type === 'added'}
					<span class="rounded-sm bg-neon-green/15 text-neon-green">{segment.value}</span>
				{:else}
					<span class="text-text-secondary">{segment.value}</span>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="grid grid-cols-2 gap-3" data-testid="diff-side-by-side">
			<div>
				<div class="section-heading-dim mb-1.5">Original</div>
				<div
					bind:this={leftPanel}
					onscroll={() => syncScroll('left')}
					class="rounded-xl bg-bg-input/60 p-4 font-mono text-sm overflow-y-auto"
					style="max-height: 460px;"
					data-testid="diff-left-panel"
				>
					{#each lineDiff.left as line}
						<div class="flex {line.type === 'removed' ? 'bg-neon-red/12 -mx-2 px-2 rounded' : ''}">
							<span class="mr-3 inline-block w-6 shrink-0 select-none text-right text-text-dim/40 text-xs leading-relaxed tabular-nums" data-testid="line-number">{line.lineNumber}</span>
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
				<div class="section-heading-dim mb-1.5">Optimized</div>
				<div
					bind:this={rightPanel}
					onscroll={() => syncScroll('right')}
					class="rounded-xl bg-bg-input/60 p-4 font-mono text-sm overflow-y-auto"
					style="max-height: 460px;"
					data-testid="diff-right-panel"
				>
					{#each lineDiff.right as line}
						<div class="flex {line.type === 'added' ? 'bg-neon-green/12 -mx-2 px-2 rounded' : ''}">
							<span class="mr-3 inline-block w-6 shrink-0 select-none text-right text-text-dim/40 text-xs leading-relaxed tabular-nums" data-testid="line-number">{line.lineNumber}</span>
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
