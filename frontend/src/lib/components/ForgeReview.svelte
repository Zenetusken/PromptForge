<script lang="ts">
	import { optimizationState, type OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { normalizeScore, getScoreBadgeClass, formatScore } from '$lib/utils/format';
	import { getStrategyColor } from '$lib/utils/strategies';
	import { ALL_DIMENSIONS, DIMENSION_LABELS, DIMENSION_COLORS } from '$lib/utils/scoreDimensions';
	import Icon from './Icon.svelte';
	import CopyButton from './CopyButton.svelte';
	import ForgeIterationTimeline from './ForgeIterationTimeline.svelte';
	import ContextSnapshotPanel from './ContextSnapshotPanel.svelte';
	import ForgeContents from './ForgeContents.svelte';
	import ExtensionSlot from '$lib/kernel/components/ExtensionSlot.svelte';

	let result = $derived(optimizationState.forgeResult);

	let activeTab = $state<'optimized' | 'original'>('optimized');

	// Find previous result for comparison (second item in history, since first is current)
	let previousResult = $derived.by(() => {
		if (!result) return null;
		const history = optimizationState.resultHistory;
		const idx = history.findIndex((r) => r.id === result!.id);
		// Return the next item (older) if available
		return idx >= 0 && idx + 1 < history.length ? history[idx + 1] : null;
	});

	function handleIterate() {
		if (!result) return;
		forgeSession.loadRequest({
			text: result.optimized,
			sourceAction: 'reiterate',
			project: result.project,
			promptId: result.prompt_id,
			title: result.title,
			version: result.version,
			tags: Array.isArray(result.tags) ? result.tags.join(', ') : '',
			strategy: 'auto',
		});
		forgeMachine.back();
	}

	function handleReforge() {
		if (!result) return;
		const metadata = forgeSession.buildMetadata();
		optimizationState.startOptimization(result.original, metadata);
		forgeMachine.enterForging();
	}

	function handleCompareWithPrevious() {
		if (!result || !previousResult) return;
		const prev = previousResult;
		forgeMachine.compare(prev.id, result.id);
	}

	function handleCompareWith(target: OptimizationResultState) {
		if (!result) return;
		forgeMachine.compare(target.id, result.id);
	}

</script>

{#if result}
	<div class="flex flex-1 flex-col overflow-y-auto" data-testid="forge-review">
		<!-- Score header -->
		<div class="px-2 pt-2 pb-1.5">
			<div class="flex items-center gap-1.5 mb-1">
				{#if result.scores.overall}
					<span class="score-circle score-circle-sm {getScoreBadgeClass(result.scores.overall)}">
						{normalizeScore(result.scores.overall)}
					</span>
				{/if}
				<div class="min-w-0 flex-1">
					<h3 class="truncate text-[11px] font-semibold text-text-primary">
						{result.title || 'Optimization complete'}
					</h3>
					<div class="flex items-center gap-1.5 mt-0.5">
						{#if result.strategy}
							{@const sColors = getStrategyColor(result.strategy)}
							<span
								class="rounded-sm px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider {sColors.text}"
								style="background: {sColors.rawRgba.replace('0.35', '0.10')}; border: 1px solid {sColors.rawRgba.replace('0.35', '0.20')};"
							>
								{result.strategy}
							</span>
						{/if}
						{#if result.strategy_confidence}
							<span class="font-mono text-[9px] {result.strategy_confidence >= 0.8 ? 'text-neon-green' : result.strategy_confidence >= 0.6 ? 'text-neon-yellow' : 'text-neon-red'}">
								{Math.round(result.strategy_confidence * 100)}%
							</span>
						{/if}
					</div>
				</div>
				<button
					onclick={() => windowManager.minimizeWindow('ide')}
					class="shrink-0 text-text-dim hover:text-text-primary transition-colors"
					aria-label="Minimize to taskbar"
				>
					<Icon name="minimize-2" size={12} />
				</button>
			</div>

			<!-- Score breakdown bars -->
			<div class="space-y-1">
				{#each ALL_DIMENSIONS as dim}
					{@const score = result.scores[dim]}
					{@const normalized = normalizeScore(score)}
					<div class="flex items-center gap-1.5">
						<span class="w-16 text-[9px] font-medium text-text-dim truncate">{DIMENSION_LABELS[dim]}</span>
						<div class="flex-1 h-1 rounded-full bg-bg-primary/60 overflow-hidden">
							<div
								class="h-full rounded-full transition-[width] duration-500"
								style="width: {normalized ?? 0}%; background-color: var(--color-{DIMENSION_COLORS[dim]})"
							></div>
						</div>
						<span class="w-5 text-right font-mono text-[9px] text-text-dim">{formatScore(score)}</span>
					</div>
				{/each}
			</div>
		</div>

		<!-- Tabs -->
		<div class="flex border-y border-neon-cyan/8">
			<button
				class="flex-1 px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors {activeTab === 'optimized' ? 'text-neon-cyan bg-neon-cyan/5 border-b border-neon-cyan' : 'text-text-dim hover:text-text-secondary'}"
				onclick={() => (activeTab = 'optimized')}
			>
				Optimized
			</button>
			<button
				class="flex-1 px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors {activeTab === 'original' ? 'text-text-secondary bg-bg-hover/30 border-b border-text-secondary' : 'text-text-dim hover:text-text-secondary'}"
				onclick={() => (activeTab = 'original')}
			>
				Original
			</button>
		</div>

		<!-- Content -->
		<div class="flex-1 overflow-y-auto px-2 py-1.5">
			<pre class="whitespace-pre-wrap font-mono text-[11px] leading-snug text-text-primary">{activeTab === 'optimized' ? result.optimized : result.original}</pre>
		</div>

		<!-- Strategy reasoning (collapsible) -->
		{#if result.strategy_reasoning}
			<div class="px-2 pb-0.5">
				<details class="text-[10px]">
					<summary class="cursor-pointer text-text-dim hover:text-text-secondary transition-colors font-medium">
						Strategy reasoning
					</summary>
					<p class="mt-1 text-text-secondary leading-snug">{result.strategy_reasoning}</p>
				</details>
			</div>
		{/if}

		<!-- Verdict -->
		{#if result.verdict}
			<div class="px-2 pb-1.5">
				<p class="text-[10px] italic text-text-dim leading-snug">{result.verdict}</p>
			</div>
		{/if}

		<!-- Codebase context snapshot (collapsible) -->
		{#if result.codebase_context_snapshot}
			<ContextSnapshotPanel context={result.codebase_context_snapshot} />
		{/if}

		<!-- Forge sub-artifact contents -->
		<ForgeContents {result} />

		<!-- Iteration timeline -->
		<ForgeIterationTimeline
			currentId={result.id}
			onselect={(target) => handleCompareWith(target)}
		/>

		<!-- Actions -->
		<div class="shrink-0 border-t border-neon-cyan/8 px-2 py-1.5 flex flex-wrap gap-1">
			<CopyButton text={result.optimized} />
			<button
				onclick={handleIterate}
				class="forge-action-btn"
				aria-label="Load optimized text into composer"
			>
				<Icon name="edit" size={10} />
				Iterate
			</button>
			<button
				onclick={handleReforge}
				class="forge-action-btn"
				aria-label="Re-forge with different settings"
			>
				<Icon name="refresh" size={10} />
				Re-forge
			</button>
			{#if optimizationState.resultHistory.length > 1}
				<button
					onclick={handleCompareWithPrevious}
					class="forge-action-btn {!previousResult ? 'opacity-40 cursor-not-allowed' : ''}"
					disabled={!previousResult}
					aria-label="Compare with previous iteration"
				>
					<Icon name="layers" size={10} />
					Compare
				</button>
			{/if}
			<!-- Extension point: apps can inject actions here -->
			<ExtensionSlot
				slotId="promptforge:review-actions"
				context={{ resultId: result.id, optimizedPrompt: result.optimized }}
			/>
		</div>
	</div>
{:else}
	<div class="flex flex-1 items-center justify-center p-4">
		<p class="text-[11px] text-text-dim">No result to review</p>
	</div>
{/if}

