<script lang="ts">
	import ResultPanel from '$lib/components/ResultPanel.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import Breadcrumbs from '$lib/components/Breadcrumbs.svelte';
	import ForgeSiblings from '$lib/components/ForgeSiblings.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { statsState } from '$lib/stores/stats.svelte';
	import { Collapsible } from 'bits-ui';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let showContextSnapshot = $state(false);
	let contextKeys = $derived.by(() => {
		const ctx = data.item?.codebase_context_snapshot;
		if (!ctx) return [];
		return Object.entries(ctx).filter(([_, v]) =>
			v && (typeof v !== 'object' || (Array.isArray(v) && v.length > 0))
		);
	});

	let isError = $derived(data.item?.status === 'error');

	let breadcrumbs = $derived.by(() => {
		const segments: { label: string; href?: string }[] = [{ label: 'Home', href: '/' }];
		if (data.item?.project && data.item?.project_id) {
			const name = data.item.project;
			const label = data.item.project_status === 'archived' ? `${name} (archived)` : name;
			segments.push({ label, href: `/projects/${data.item.project_id}` });
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

	// Scope header stats to this optimization's project (if any)
	$effect(() => {
		if (data.item?.project) {
			statsState.setContext(data.item.project);
		}
		return () => statsState.clearProjectContext();
	});
</script>

<div class="flex flex-col gap-3">
	<Breadcrumbs segments={breadcrumbs} />

	{#if data.item?.project_id && data.item?.prompt_id}
		{#key data.item.prompt_id}
			<ForgeSiblings
				currentForgeId={data.item.id}
				projectId={data.item.project_id}
				promptId={data.item.prompt_id}
			/>
		{/key}
	{/if}

	{#if contextKeys.length > 0}
		<Collapsible.Root bind:open={showContextSnapshot}>
			<Collapsible.Trigger
				class="flex w-full items-center gap-2 rounded-md border border-neon-green/10 bg-bg-card/30 px-2.5 py-1 text-left transition-colors hover:border-neon-green/20 hover:bg-bg-card/50"
			>
				<Icon
					name="chevron-right"
					size={12}
					class="text-neon-green/60 transition-transform duration-200 {showContextSnapshot ? 'rotate-90' : ''}"
				/>
				<span class="text-xs font-medium text-neon-green/80">Context Used</span>
				<span class="h-1.5 w-1.5 rounded-full bg-neon-green"></span>
			</Collapsible.Trigger>
			<Collapsible.Content>
				<div class="mt-1 rounded-md border border-neon-green/10 bg-bg-card/20 p-2">
					<div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2 md:grid-cols-3">
						{#each contextKeys as [key, val]}
							<div class="rounded-md bg-bg-secondary/40 p-1.5">
								<div class="mb-1 text-[10px] font-bold uppercase tracking-wider text-neon-green/60">{key.replace(/_/g, ' ')}</div>
								{#if Array.isArray(val)}
									<ul class="space-y-0.5 text-xs text-text-secondary">
										{#each val as item}
											<li class="truncate">&#8226; {item}</li>
										{/each}
									</ul>
								{:else}
									<p class="text-xs text-text-secondary">{val}</p>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			</Collapsible.Content>
		</Collapsible.Root>
	{/if}

	{#if isError}
		<div class="rounded-md border border-neon-red/15 bg-bg-card/60 p-2.5" data-testid="error-state">
			<div class="flex items-center gap-2 mb-2">
				<div class="flex h-6 w-6 items-center justify-center rounded-full bg-neon-red/10">
					<Icon name="x" size={16} class="text-neon-red" />
				</div>
				<div>
					<h3 class="text-sm font-medium text-neon-red">Optimization Failed</h3>
					<p class="text-xs text-text-dim">This optimization encountered an error during processing.</p>
				</div>
			</div>
			{#if data.item?.error_message}
				<div class="rounded-md bg-neon-red/5 border border-neon-red/10 p-2">
					<p class="font-mono text-xs leading-relaxed text-text-secondary">{data.item.error_message}</p>
				</div>
			{/if}
			{#if data.item?.raw_prompt}
				<div class="mt-2">
					<h4 class="section-heading mb-2">Original Prompt</h4>
					<pre class="whitespace-pre-wrap rounded-md bg-bg-secondary/80 p-2.5 font-mono text-sm leading-relaxed text-text-secondary">{data.item.raw_prompt}</pre>
				</div>
			{/if}
		</div>
	{:else if optimizationState.result}
		<ResultPanel result={optimizationState.result} />
	{/if}
</div>
