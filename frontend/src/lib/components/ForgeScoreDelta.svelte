<script lang="ts">
	import { normalizeScore } from '$lib/utils/format';
	import { SCORE_WEIGHTS, DIMENSION_LABELS, ALL_DIMENSIONS, SUPPLEMENTARY_META, ALL_SUPPLEMENTARY, type ScoreDimension } from '$lib/utils/scoreDimensions';

	type Scores = Record<string, number>;

	let {
		scoresA,
		scoresB,
	}: {
		scoresA: Scores;
		scoresB: Scores;
	} = $props();

	const DIMS = ALL_DIMENSIONS;

	interface DeltaRow {
		dim: ScoreDimension;
		label: string;
		normA: number;
		normB: number;
		delta: number;
		weight: number;
	}

	let rows: DeltaRow[] = $derived(
		DIMS.map((dim) => {
			const normA = normalizeScore(scoresA[dim]) ?? 0;
			const normB = normalizeScore(scoresB[dim]) ?? 0;
			return {
				dim,
				label: DIMENSION_LABELS[dim],
				normA,
				normB,
				delta: normB - normA,
				weight: SCORE_WEIGHTS[dim],
			};
		})
	);

	let overallDelta = $derived.by(() => {
		const oA = normalizeScore(scoresA.overall) ?? 0;
		const oB = normalizeScore(scoresB.overall) ?? 0;
		return oB - oA;
	});
</script>

<div class="space-y-1.5">
	{#each rows as row}
		{@const isPositive = row.delta > 0}
		{@const isNegative = row.delta < 0}
		{@const absDelta = Math.abs(row.delta)}
		<div class="flex items-center gap-1.5">
			<span class="w-16 text-[9px] font-medium text-text-dim truncate">{row.label}</span>

			<!-- Delta bar -->
			<div class="flex-1 flex items-center gap-0.5">
				<!-- Center-anchored bar: negative grows left, positive grows right -->
				<div class="flex-1 relative h-2 bg-bg-primary/40 rounded-sm overflow-hidden">
					{#if isPositive}
						<div
							class="absolute left-1/2 h-full rounded-sm bg-neon-green/60 transition-[width] duration-300"
							style="width: {Math.min(absDelta, 50)}%"
						></div>
					{:else if isNegative}
						<div
							class="absolute right-1/2 h-full rounded-sm bg-neon-red/60 transition-[width] duration-300"
							style="width: {Math.min(absDelta, 50)}%"
						></div>
					{:else}
						<div class="absolute left-1/2 w-px h-full bg-text-dim/30"></div>
					{/if}
				</div>
			</div>

			<!-- Delta number -->
			<span
				class="w-8 text-right font-mono text-[9px] font-semibold {isPositive ? 'text-neon-green' : isNegative ? 'text-neon-red' : 'text-text-dim'}"
			>
				{isPositive ? '+' : ''}{row.delta}
			</span>
		</div>
	{/each}

	<!-- Supplementary dimension deltas -->
	{#each ALL_SUPPLEMENTARY as suppDim (suppDim)}
		{@const suppA = scoresA[suppDim]}
		{@const suppB = scoresB[suppDim]}
		{#if suppA != null && suppB != null}
			{@const normSA = normalizeScore(suppA) ?? 0}
			{@const normSB = normalizeScore(suppB) ?? 0}
			{@const suppDelta = normSB - normSA}
			{@const meta = SUPPLEMENTARY_META[suppDim]}
			<div class="flex items-center gap-1.5 opacity-70">
				<span class="w-16 text-[9px] font-medium text-text-dim truncate italic">{meta.label}</span>
				<div class="flex-1 flex items-center gap-0.5">
					<div class="flex-1 relative h-2 bg-bg-primary/40 rounded-sm overflow-hidden">
						{#if suppDelta > 0}
							<div
								class="absolute left-1/2 h-full rounded-sm bg-neon-green/60 transition-[width] duration-300"
								style="width: {Math.min(Math.abs(suppDelta), 50)}%"
							></div>
						{:else if suppDelta < 0}
							<div
								class="absolute right-1/2 h-full rounded-sm bg-neon-red/60 transition-[width] duration-300"
								style="width: {Math.min(Math.abs(suppDelta), 50)}%"
							></div>
						{:else}
							<div class="absolute left-1/2 w-px h-full bg-text-dim/30"></div>
						{/if}
					</div>
				</div>
				<span
					class="w-8 text-right font-mono text-[9px] font-semibold {suppDelta > 0 ? 'text-neon-green' : suppDelta < 0 ? 'text-neon-red' : 'text-text-dim'}"
				>
					{suppDelta > 0 ? '+' : ''}{suppDelta}
				</span>
			</div>
		{/if}
	{/each}

	<!-- Overall delta -->
	<div class="flex items-center gap-1.5 pt-1 border-t border-neon-cyan/8">
		<span class="w-16 text-[9px] font-bold text-text-primary">Overall</span>
		<div class="flex-1"></div>
		<span
			class="font-mono text-[10px] font-bold {overallDelta > 0 ? 'text-neon-green' : overallDelta < 0 ? 'text-neon-red' : 'text-text-dim'}"
		>
			{overallDelta > 0 ? '+' : ''}{overallDelta}
		</span>
	</div>
</div>
