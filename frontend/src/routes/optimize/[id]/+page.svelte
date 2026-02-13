<script lang="ts">
	import ResultPanel from '$lib/components/ResultPanel.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// Load the item into the optimization store so ResultPanel can work with it
	$effect(() => {
		if (data.item) {
			optimizationState.loadFromHistory(data.item);
		}
	});
</script>

<div class="mx-auto flex max-w-6xl flex-col gap-6">
	<div class="flex items-center gap-3">
		<a
			href="/"
			class="flex items-center gap-1.5 rounded-lg bg-bg-card px-3 py-1.5 font-mono text-xs text-text-secondary transition-colors hover:text-neon-cyan"
			data-testid="back-link"
		>
			<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<polyline points="15 18 9 12 15 6" />
			</svg>
			Back to Forge
		</a>
	</div>

	{#if optimizationState.result}
		<ResultPanel result={optimizationState.result} />
	{/if}
</div>
