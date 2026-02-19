<script lang="ts">
	import DiffView from './DiffView.svelte';
	import CopyButton from './CopyButton.svelte';
	import ResultMetadata from './ResultMetadata.svelte';
	import ResultActions from './ResultActions.svelte';
	import PipelineNarrative from './PipelineNarrative.svelte';
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	let activeTab = $state<'optimized' | 'diff' | 'original'>('optimized');

	const tabs = [
		{ key: 'optimized' as const, label: 'Optimized', color: 'neon-cyan' },
		{ key: 'diff' as const, label: 'Diff View', color: 'neon-purple' },
		{ key: 'original' as const, label: 'Original', color: 'text-secondary' },
	];
</script>

<div class="animate-fade-in rounded-2xl border border-border-subtle bg-bg-card/60 overflow-hidden" data-testid="result-panel">
	<ResultMetadata {result} />

	<!-- Tabs -->
	<div class="flex items-center justify-between gap-2 border-b border-border-subtle px-5 overflow-x-auto">
		<div class="flex shrink-0" data-testid="result-tabs">
			{#each tabs as tab}
				<button
					class="relative px-4 py-3.5 text-sm transition-colors {activeTab === tab.key ? 'bg-[rgba(22,22,42,0.4)] font-medium' : ''}"
					class:text-neon-cyan={activeTab === tab.key && tab.color === 'neon-cyan'}
					class:text-neon-purple={activeTab === tab.key && tab.color === 'neon-purple'}
					class:text-text-primary={activeTab === tab.key && tab.color === 'text-secondary'}
					class:text-text-dim={activeTab !== tab.key}
					class:hover:text-text-secondary={activeTab !== tab.key}
					onclick={() => (activeTab = tab.key)}
					data-testid="tab-{tab.key}"
				>
					{tab.label}
					{#if activeTab === tab.key}
						<div
							class="absolute bottom-0 left-2 right-2 h-[3px] rounded-full transition-[width,left,right] duration-200"
							class:bg-neon-cyan={tab.color === 'neon-cyan'}
							class:bg-neon-purple={tab.color === 'neon-purple'}
							class:bg-text-secondary={tab.color === 'text-secondary'}
						></div>
					{/if}
				</button>
			{/each}
		</div>

		<CopyButton text={activeTab === 'original' ? result.original : result.optimized} />
	</div>

	<!-- Content -->
	<div class="p-5" data-testid="result-content">
		{#if activeTab === 'optimized'}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-primary">{result.optimized}</pre>
		{:else if activeTab === 'diff'}
			<DiffView original={result.original} optimized={result.optimized} />
		{:else}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-primary">{result.original}</pre>
		{/if}
	</div>

	<ResultActions {result} />
	<PipelineNarrative {result} />
</div>
