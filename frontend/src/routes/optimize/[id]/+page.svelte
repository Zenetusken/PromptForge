<script lang="ts">
	import ResultPanel from '$lib/components/ResultPanel.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import Breadcrumbs from '$lib/components/Breadcrumbs.svelte';
	import ForgeSiblings from '$lib/components/ForgeSiblings.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { navigationState, projectLabel } from '$lib/stores/navigation.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let isError = $derived(data.item?.status === 'error');

	let backDest = $derived(navigationState.getBackForOptimize(data.item));
	let breadcrumbs = $derived.by(() => {
		const segments: { label: string; href?: string }[] = [{ label: 'Home', href: '/' }];
		if (data.item?.project && data.item?.project_id) {
			segments.push({
				label: projectLabel(data.item.project, data.item.project_status),
				href: `/projects/${data.item.project_id}`,
			});
		}
		segments.push({ label: data.item?.title || 'Forge Detail' });
		return segments;
	});

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

<div class="flex flex-col gap-6">
	<div class="flex items-center gap-3">
		<a
			href={backDest.url}
			class="flex items-center gap-1.5 rounded-lg bg-bg-card/60 px-3 py-1.5 text-xs text-text-dim transition-colors hover:text-neon-cyan"
			data-testid="back-link"
		>
			<Icon name="chevron-left" size={12} />
			{backDest.label}
		</a>
		<span class="text-text-dim/30">|</span>
		<Breadcrumbs segments={breadcrumbs} />
	</div>

	{#if data.item?.project_id && data.item?.prompt_id}
		{#key data.item.prompt_id}
			<ForgeSiblings
				currentForgeId={data.item.id}
				projectId={data.item.project_id}
				promptId={data.item.prompt_id}
			/>
		{/key}
	{/if}

	{#if isError}
		<div class="rounded-2xl border border-neon-red/15 bg-bg-card/60 p-6" data-testid="error-state">
			<div class="flex items-center gap-3 mb-4">
				<div class="flex h-8 w-8 items-center justify-center rounded-full bg-neon-red/10">
					<Icon name="x" size={16} class="text-neon-red" />
				</div>
				<div>
					<h3 class="text-sm font-medium text-neon-red">Optimization Failed</h3>
					<p class="text-xs text-text-dim">This optimization encountered an error during processing.</p>
				</div>
			</div>
			{#if data.item?.error_message}
				<div class="rounded-xl bg-neon-red/5 border border-neon-red/10 p-4">
					<p class="font-mono text-xs leading-relaxed text-text-secondary">{data.item.error_message}</p>
				</div>
			{/if}
			{#if data.item?.raw_prompt}
				<div class="mt-4">
					<h4 class="section-heading mb-2">Original Prompt</h4>
					<pre class="whitespace-pre-wrap rounded-xl bg-bg-secondary/80 p-4 font-mono text-sm leading-relaxed text-text-secondary">{data.item.raw_prompt}</pre>
				</div>
			{/if}
		</div>
	{:else if optimizationState.result}
		<ResultPanel result={optimizationState.result} />
	{/if}
</div>
