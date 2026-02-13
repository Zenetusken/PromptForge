<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

	type Scores = OptimizationResultState['scores'];

	let { scores }: { scores: Scores } = $props();

	/**
	 * Normalize score: if <= 1, treat as 0-1 scale and multiply by 100.
	 * Otherwise treat as already 0-100.
	 */
	function normalizeScore(score: number): number {
		if (score <= 1) return Math.round(score * 100);
		return Math.round(score);
	}

	function getScoreColor(score: number): string {
		const pct = normalizeScore(score);
		if (pct >= 70) return 'neon-green';
		if (pct >= 40) return 'neon-yellow';
		return 'neon-red';
	}

	const scoreLabels: { key: keyof Scores; label: string }[] = [
		{ key: 'clarity', label: 'Clarity' },
		{ key: 'specificity', label: 'Specificity' },
		{ key: 'structure', label: 'Structure' },
		{ key: 'faithfulness', label: 'Faithfulness' },
		{ key: 'overall', label: 'Overall' }
	];

	let animated = $state(false);
	$effect(() => {
		// Trigger animation after mount
		setTimeout(() => { animated = true; }, 100);
	});
</script>

<div data-testid="score-panel">
	<h4 class="mb-3 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
		Quality Scores
	</h4>

	<div class="grid gap-3 sm:grid-cols-2">
		{#each scoreLabels as { key, label } (key)}
			{@const rawScore = scores[key]}
			{@const pct = normalizeScore(rawScore)}
			{@const color = getScoreColor(rawScore)}
			<div class="rounded-lg bg-bg-input p-3" class:sm:col-span-2={key === 'overall'} data-testid="score-bar-{key}" role="meter" aria-label="{label}: {pct} out of 100" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
				<div class="mb-2 flex items-center justify-between">
					<span class="text-sm text-text-primary" class:font-semibold={key === 'overall'}>
						{label}
					</span>
					<span
						class="font-mono text-sm font-bold"
						class:text-neon-green={color === 'neon-green'}
						class:text-neon-yellow={color === 'neon-yellow'}
						class:text-neon-red={color === 'neon-red'}
					>
						{pct}
					</span>
				</div>
				<div class="h-1.5 w-full overflow-hidden rounded-full bg-bg-primary" class:h-2={key === 'overall'}>
					<div
						class="h-full rounded-full transition-all duration-700 ease-out"
						class:bg-neon-green={color === 'neon-green'}
						class:bg-neon-yellow={color === 'neon-yellow'}
						class:bg-neon-red={color === 'neon-red'}
						style="width: {animated ? pct : 0}%;"
					></div>
				</div>
			</div>
		{/each}
	</div>
</div>
