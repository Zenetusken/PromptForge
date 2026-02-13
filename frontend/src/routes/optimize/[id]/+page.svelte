<script lang="ts">
	import ResultPanel from '$lib/components/ResultPanel.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let isError = $derived(data.item?.status === 'error');

	// Load the item into the optimization store so ResultPanel can work with it
	$effect(() => {
		if (data.item) {
			if (isError) {
				// Clear stale result so it doesn't leak across navigations
				optimizationState.result = null;
			} else {
				optimizationState.loadFromHistory(data.item);
			}
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
		{#if data.item?.title}
			<span class="font-mono text-sm text-text-primary" data-testid="detail-title">{data.item.title}</span>
		{/if}
	</div>

	{#if isError}
		<div class="rounded-xl border border-neon-red/20 bg-bg-card p-6" data-testid="error-state">
			<div class="flex items-center gap-3 mb-4">
				<span class="flex h-8 w-8 items-center justify-center rounded-full bg-neon-red/10">
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-neon-red">
						<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
					</svg>
				</span>
				<div>
					<h3 class="font-mono text-sm font-semibold text-neon-red">Optimization Failed</h3>
					<p class="text-xs text-text-dim">This optimization encountered an error during processing.</p>
				</div>
			</div>
			{#if data.item?.error_message}
				<div class="rounded-lg bg-neon-red/5 border border-neon-red/10 p-4">
					<p class="font-mono text-xs text-text-secondary">{data.item.error_message}</p>
				</div>
			{/if}
			{#if data.item?.raw_prompt}
				<div class="mt-4">
					<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">Original Prompt</h4>
					<pre class="whitespace-pre-wrap rounded-lg bg-bg-secondary p-3 font-mono text-sm text-text-secondary">{data.item.raw_prompt}</pre>
				</div>
			{/if}
		</div>
	{:else if optimizationState.result}
		<ResultPanel result={optimizationState.result} />
	{/if}
</div>
