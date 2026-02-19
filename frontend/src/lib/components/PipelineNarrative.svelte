<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import type { ScoreDimension } from '$lib/utils/scoreDimensions';
	import NarrativeStage from './NarrativeStage.svelte';
	import ScoreDecomposition from './ScoreDecomposition.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	let hoveredDimension = $state<ScoreDimension | null>(null);
	let pinnedDimension = $state<ScoreDimension | null>(null);
	let highlightedDimension = $derived(pinnedDimension ?? hoveredDimension);

	const stages = [
		{ key: 'analysis' as const, color: 'neon-cyan' },
		{ key: 'strategy' as const, color: 'neon-yellow' },
		{ key: 'optimization' as const, color: 'neon-purple' },
	];

	let hasScores = $derived(
		result.scores.clarity > 0 ||
		result.scores.specificity > 0 ||
		result.scores.structure > 0 ||
		result.scores.faithfulness > 0 ||
		result.scores.overall > 0
	);

	let hasValidation = $derived(hasScores || !!result.verdict);
	let hasAnalysis = $derived(result.strengths.length > 0 || result.weaknesses.length > 0 || result.task_type);
	let hasStrategy = $derived(!!result.strategy || !!result.strategy_reasoning);
	let hasOptimization = $derived(result.changes_made.length > 0 || !!result.optimization_notes);

	function shouldShow(stage: 'analysis' | 'strategy' | 'optimization'): boolean {
		if (stage === 'analysis') return !!hasAnalysis;
		if (stage === 'strategy') return !!hasStrategy;
		if (stage === 'optimization') return !!hasOptimization;
		return false;
	}

	let visibleStages = $derived(stages.filter(s => shouldShow(s.key)));
	let hasAnyContent = $derived(visibleStages.length > 0 || hasValidation);

	/**
	 * Full ordered list of timeline entries (including validation)
	 * so we can compute "next color" for each entry's connecting line.
	 */
	let allEntries = $derived.by(() => {
		const entries: { key: string; color: string }[] = visibleStages.map(s => ({ key: s.key, color: s.color }));
		if (hasValidation) {
			entries.push({ key: 'validation', color: 'neon-green' });
		}
		return entries;
	});
</script>

{#if hasAnyContent}
<div class="border-t border-border-subtle" data-testid="pipeline-narrative">
	<div class="px-5 py-5">
		<div
			class="pipeline-timeline"
			style:--highlight-color={highlightedDimension === 'structure' ? 'var(--color-neon-purple)' :
				highlightedDimension === 'faithfulness' ? 'var(--color-neon-green)' :
				highlightedDimension ? 'var(--color-neon-cyan)' : 'transparent'}
		>
			{#each visibleStages as stage, i (stage.key)}
				{@const entryIdx = allEntries.findIndex(e => e.key === stage.key)}
				{@const isLast = entryIdx === allEntries.length - 1}
				{@const nextColor = isLast ? stage.color : allEntries[entryIdx + 1].color}
				<div
					class="pipeline-entry"
					class:pipeline-entry--connected={!isLast}
					style="--pipeline-color-from: var(--color-{stage.color}); --pipeline-color-to: var(--color-{nextColor});"
				>
					<div
						class="pipeline-node"
						style="background-color: var(--color-{stage.color}); box-shadow: 0 0 8px var(--color-{stage.color});"
						aria-hidden="true"
					></div>

					<div class="pipeline-content">
						<NarrativeStage
							stage={stage.key}
							{result}
							{highlightedDimension}
							color={stage.color}
						/>
					</div>
				</div>
			{/each}

			{#if hasValidation}
				<div class="pipeline-entry">
					<div
						class="pipeline-node"
						style="background-color: var(--color-neon-green); box-shadow: 0 0 8px var(--color-neon-green);"
						aria-hidden="true"
					></div>

					<div class="pipeline-content" data-pipeline-stage="validation">
						<ScoreDecomposition
							scores={result.scores}
							verdict={result.verdict}
							isImprovement={result.is_improvement}
							{hasScores}
							{pinnedDimension}
							onHighlight={(dim) => hoveredDimension = dim}
							onClear={() => hoveredDimension = null}
							onPin={(dim) => pinnedDimension = pinnedDimension === dim ? null : dim}
						/>
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>
{/if}
