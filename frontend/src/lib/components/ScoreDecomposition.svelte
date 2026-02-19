<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { normalizeScore, getScoreColorClass, getScoreTierLabel } from '$lib/utils/format';
	import { SCORE_WEIGHTS, DIMENSION_LABELS, computeContribution, type ScoreDimension } from '$lib/utils/scoreDimensions';
	import { generateScoreExplanation } from '$lib/utils/scoreExplanation';
	import Icon from './Icon.svelte';
	import { Separator, Tooltip } from './ui';

	type Scores = OptimizationResultState['scores'];

	let {
		scores,
		verdict,
		isImprovement,
		hasScores,
		pinnedDimension,
		onHighlight,
		onClear,
		onPin,
	}: {
		scores: Scores;
		verdict: string;
		isImprovement: boolean;
		hasScores: boolean;
		pinnedDimension: ScoreDimension | null;
		onHighlight: (dim: ScoreDimension) => void;
		onClear: () => void;
		onPin: (dim: ScoreDimension) => void;
	} = $props();

	const dimensions: ScoreDimension[] = ['faithfulness', 'clarity', 'specificity', 'structure'];

	const DIMENSION_TOOLTIPS: Record<ScoreDimension, string> = {
		clarity: 'How clearly the prompt communicates intent',
		specificity: 'How concrete and detailed the instructions are',
		structure: 'How well-organized the prompt layout is',
		faithfulness: 'How well the original intent is preserved',
	};

	let animated = $state(false);
	$effect(() => {
		const timer = setTimeout(() => { animated = true; }, 100);
		return () => clearTimeout(timer);
	});

	let overallPct = $derived(normalizeScore(scores.overall) ?? 0);
	let overallColor = $derived(getScoreColorClass(scores.overall));
	let overallTier = $derived(getScoreTierLabel(scores.overall));
	let explanation = $derived(generateScoreExplanation(scores));

	let showLowScoreGuidance = $derived(
		hasScores && (!isImprovement || overallPct < 50)
	);

	function scrollToAnalysis() {
		const el = document.querySelector('[data-pipeline-stage="analysis"]');
		el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}
</script>

<div class="space-y-4" data-testid="score-decomposition">
	<!-- Headline -->
	<div class="flex items-center gap-2">
		<h3 class="section-heading" style="color: var(--color-neon-green);">Validation</h3>
		{#if hasScores}
			<span class="text-sm text-text-secondary">
				Overall
				<span
					class="font-mono font-bold tabular-nums"
					class:text-neon-green={overallColor === 'neon-green'}
					class:text-neon-yellow={overallColor === 'neon-yellow'}
					class:text-neon-red={overallColor === 'neon-red'}
				>{overallPct}/100</span>
				{#if overallTier}
					<span class="text-text-dim">&middot;</span>
					<span
						class="text-xs font-medium"
						class:text-neon-green={overallColor === 'neon-green'}
						class:text-neon-yellow={overallColor === 'neon-yellow'}
						class:text-neon-red={overallColor === 'neon-red'}
					>{overallTier}</span>
				{/if}
				{#if isImprovement}
					<Tooltip text="Improvement over original"><span class="text-neon-green">&#10003;</span></Tooltip>
				{/if}
			</span>
		{/if}
	</div>

	<!-- Verdict -->
	{#if verdict}
		<p class="text-sm leading-relaxed text-text-secondary">{verdict}</p>
	{/if}

	<!-- Score Breakdown -->
	{#if hasScores}
		<div class="rounded-xl border border-border-subtle bg-bg-input/40 p-4">
			<h4 class="section-heading mb-3">Score Breakdown</h4>

			<div class="space-y-3">
				{#each dimensions as dim (dim)}
					{@const rawScore = scores[dim]}
					{@const pct = normalizeScore(rawScore) ?? 0}
					{@const color = getScoreColorClass(rawScore)}
					{@const weight = Math.round(SCORE_WEIGHTS[dim] * 100)}
					{@const contribution = computeContribution(pct, dim)}
					{@const isPinned = pinnedDimension === dim}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						class="group/score w-full text-left rounded-lg p-2.5 transition-colors hover:bg-bg-hover/20 focus-within:bg-bg-hover/20 hover:ring-1 hover:ring-border-subtle focus-within:ring-1 focus-within:ring-border-subtle cursor-pointer {isPinned ? 'bg-bg-hover/20 ring-1 ring-border-subtle' : ''}"
						role="button"
						tabindex="0"
						aria-label="View {DIMENSION_LABELS[dim]} analysis findings"
						aria-pressed={isPinned}
						onmouseenter={() => onHighlight(dim)}
						onmouseleave={() => onClear()}
						onfocusin={() => onHighlight(dim)}
						onfocusout={() => onClear()}
						onclick={() => { if (!isPinned) scrollToAnalysis(); onPin(dim); }}
						onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (!isPinned) scrollToAnalysis(); onPin(dim); } }}
						data-testid="score-bar-{dim}"
					>
						<div class="mb-1.5 flex items-center justify-between text-sm">
							<Tooltip text={DIMENSION_TOOLTIPS[dim]} side="right"><span class="text-text-primary">{DIMENSION_LABELS[dim]}</span></Tooltip>
							<span class="flex items-center gap-2 font-mono text-xs tabular-nums">
								<span
									class="font-bold"
									class:text-neon-green={color === 'neon-green'}
									class:text-neon-yellow={color === 'neon-yellow'}
									class:text-neon-red={color === 'neon-red'}
								>{pct}</span>
								<Tooltip text="Score contribution weight"><span class="text-text-dim">&times; {weight}%</span></Tooltip>
								<span class="text-text-dim">=</span>
								<span class="text-text-secondary">{contribution.toFixed(1)} pts</span>
							</span>
						</div>
						<div
							class="h-1.5 w-full overflow-hidden rounded-full bg-bg-primary/80"
							role="meter"
							aria-label="{DIMENSION_LABELS[dim]}: {pct} out of 100"
							aria-valuenow={pct}
							aria-valuemin={0}
							aria-valuemax={100}
						>
							<div
								class="score-fill h-full rounded-full transition-[width] duration-700 ease-out"
								class:bg-neon-green={color === 'neon-green'}
								class:bg-neon-yellow={color === 'neon-yellow'}
								class:bg-neon-red={color === 'neon-red'}
								style="width: {animated ? pct : 0}%;"
							></div>
						</div>
					</div>
				{/each}

				<!-- Separator -->
				<Separator class="divider-glow my-1" />

				<!-- Overall -->
				<div class="rounded-lg p-2.5" data-testid="score-bar-overall">
					<div class="mb-1.5 flex items-center justify-between text-sm">
						<span class="font-semibold text-text-primary">Overall</span>
						<span class="flex items-center gap-2 font-mono text-xs tabular-nums">
							<span
								class="text-base font-bold"
								class:text-neon-green={overallColor === 'neon-green'}
								class:text-neon-yellow={overallColor === 'neon-yellow'}
								class:text-neon-red={overallColor === 'neon-red'}
							>{overallPct}</span>
							<span class="text-text-dim">(weighted sum)</span>
						</span>
					</div>
					<div class="h-2 w-full overflow-hidden rounded-full bg-bg-primary/80">
						<div
							class="score-fill h-full rounded-full transition-[width] duration-700 ease-out"
							class:bg-neon-green={overallColor === 'neon-green'}
							class:bg-neon-yellow={overallColor === 'neon-yellow'}
							class:bg-neon-red={overallColor === 'neon-red'}
							style="width: {animated ? overallPct : 0}%;"
						></div>
					</div>
				</div>
			</div>
		</div>

		<!-- Explanation -->
		<p class="text-xs leading-relaxed text-text-dim">{explanation}</p>
	{/if}

	<!-- Low score / no improvement guidance -->
	{#if showLowScoreGuidance}
		<div class="flex items-start gap-3 rounded-xl border border-neon-yellow/15 bg-neon-yellow/5 p-3.5" data-testid="low-score-guidance">
			<Icon name="info" size={16} class="mt-0.5 shrink-0 text-neon-yellow" />
			<div class="text-sm leading-relaxed text-text-secondary">
				{#if !isImprovement}
					<span class="font-medium text-neon-yellow">No improvement detected.</span>
				{:else}
					<span class="font-medium text-neon-yellow">Score is below average.</span>
				{/if}
				Try selecting a different strategy, making your prompt more specific, or adding context before re-forging.
			</div>
		</div>
	{/if}
</div>
