<script lang="ts">
	import DiffView from './DiffView.svelte';
	import ScorePanel from './ScorePanel.svelte';
	import CopyButton from './CopyButton.svelte';
	import ResultMetadata from './ResultMetadata.svelte';
	import ResultActions from './ResultActions.svelte';
	import ResultAnalysis from './ResultAnalysis.svelte';
	import ResultChanges from './ResultChanges.svelte';
	import Icon from './Icon.svelte';
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { normalizeScore } from '$lib/utils/format';

	let { result }: { result: OptimizationResultState } = $props();

	let activeTab = $state<'optimized' | 'diff' | 'original'>('optimized');

	let hasScores = $derived(
		result.scores.clarity > 0 ||
		result.scores.specificity > 0 ||
		result.scores.structure > 0 ||
		result.scores.faithfulness > 0 ||
		result.scores.overall > 0
	);

	let showLowScoreGuidance = $derived(
		hasScores && (!result.is_improvement || (normalizeScore(result.scores.overall) ?? 0) < 50)
	);

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
	<ResultAnalysis {result} />
	<ResultChanges {result} />

	<!-- Scores -->
	{#if hasScores}
		<div class="border-t border-border-subtle p-5">
			<ScorePanel scores={result.scores} />
		</div>
	{/if}

	<!-- Low score / no improvement guidance -->
	{#if showLowScoreGuidance}
		<div class="border-t border-border-subtle px-5 py-4" data-testid="low-score-guidance">
			<div class="flex items-start gap-3 rounded-xl border border-neon-yellow/15 bg-neon-yellow/5 p-3.5">
				<Icon name="info" size={16} class="mt-0.5 shrink-0 text-neon-yellow" />
				<div class="text-sm leading-relaxed text-text-secondary">
					{#if !result.is_improvement}
						<span class="font-medium text-neon-yellow">No improvement detected.</span>
					{:else}
						<span class="font-medium text-neon-yellow">Score is below average.</span>
					{/if}
					Try selecting a different strategy, making your prompt more specific, or adding context before re-forging.
				</div>
			</div>
		</div>
	{/if}
</div>
