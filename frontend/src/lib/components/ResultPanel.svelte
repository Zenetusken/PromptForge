<script lang="ts">
	import DiffView from './DiffView.svelte';
	import ScorePanel from './ScorePanel.svelte';
	import CopyButton from './CopyButton.svelte';
	import ResultMetadata from './ResultMetadata.svelte';
	import ResultActions from './ResultActions.svelte';
	import ResultAnalysis from './ResultAnalysis.svelte';
	import ResultChanges from './ResultChanges.svelte';
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	let activeTab = $state<'optimized' | 'diff' | 'original'>('optimized');

	let hasScores = $derived(
		result.scores.clarity > 0 ||
		result.scores.specificity > 0 ||
		result.scores.structure > 0 ||
		result.scores.faithfulness > 0 ||
		result.scores.overall > 0
	);
</script>

<div class="animate-fade-in rounded-xl border border-neon-cyan/20 bg-bg-card" data-testid="result-panel">
	<ResultMetadata {result} />

	<!-- Tabs -->
	<div class="flex items-center justify-between border-b border-text-dim/20 px-5">
		<div class="flex gap-1" data-testid="result-tabs">
			<button
				class="border-b-2 px-4 py-3 font-mono text-sm transition-colors"
				class:border-neon-cyan={activeTab === 'optimized'}
				class:text-neon-cyan={activeTab === 'optimized'}
				class:border-transparent={activeTab !== 'optimized'}
				class:text-text-secondary={activeTab !== 'optimized'}
				onclick={() => (activeTab = 'optimized')}
				data-testid="tab-optimized"
			>
				Optimized
			</button>
			<button
				class="border-b-2 px-4 py-3 font-mono text-sm transition-colors"
				class:border-neon-purple={activeTab === 'diff'}
				class:text-neon-purple={activeTab === 'diff'}
				class:border-transparent={activeTab !== 'diff'}
				class:text-text-secondary={activeTab !== 'diff'}
				onclick={() => (activeTab = 'diff')}
				data-testid="tab-diff"
			>
				Diff View
			</button>
			<button
				class="border-b-2 px-4 py-3 font-mono text-sm transition-colors"
				class:border-text-secondary={activeTab === 'original'}
				class:text-text-primary={activeTab === 'original'}
				class:border-transparent={activeTab !== 'original'}
				class:text-text-secondary={activeTab !== 'original'}
				onclick={() => (activeTab = 'original')}
				data-testid="tab-original"
			>
				Original
			</button>
		</div>

		<div class="flex items-center gap-2">
			<CopyButton text={activeTab === 'original' ? result.original : result.optimized} />
		</div>
	</div>

	<!-- Content -->
	<div class="p-5" data-testid="result-content">
		{#if activeTab === 'optimized'}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-primary">{result.optimized}</pre>
		{:else if activeTab === 'diff'}
			<DiffView original={result.original} optimized={result.optimized} />
		{:else}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-secondary">{result.original}</pre>
		{/if}
	</div>

	<ResultActions {result} />
	<ResultAnalysis {result} />
	<ResultChanges {result} />

	<!-- Scores -->
	{#if hasScores}
		<div class="border-t border-text-dim/20 p-5">
			<ScorePanel scores={result.scores} />
		</div>
	{/if}
</div>
