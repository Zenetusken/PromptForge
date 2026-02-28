<script lang="ts">
	import type { OptimizationResultState } from "$lib/stores/optimization.svelte";
	import {
		tagFinding,
		type ScoreDimension,
	} from "$lib/utils/scoreDimensions";
	import { getTaskTypeColor } from "$lib/utils/taskTypes";
	import { getComplexityColor } from "$lib/utils/complexity";
	import { MetaBadge } from "./ui";

	let {
		stage,
		result,
		highlightedDimension,
		color,
	}: {
		stage: "analysis" | "strategy" | "optimization";
		result: OptimizationResultState;
		highlightedDimension: ScoreDimension | null;
		color: string;
	} = $props();

	const stageLabels = {
		analysis: "Analysis",
		strategy: "Strategy",
		optimization: "Optimization",
	} as const;

	let safeStrengths = $derived(Array.isArray(result.strengths) ? result.strengths : []);
	let safeWeaknesses = $derived(Array.isArray(result.weaknesses) ? result.weaknesses : []);
	let safeChangesMade = $derived(Array.isArray(result.changes_made) ? result.changes_made : []);
	let safeSecondary = $derived(Array.isArray(result.secondary_frameworks) ? result.secondary_frameworks : []);

	let findingCount = $derived(
		safeStrengths.length + safeWeaknesses.length,
	);

	/** Pre-compute dimension tags for each finding to avoid redundant regex work. */
	let strengthTags = $derived(safeStrengths.map((s) => tagFinding(s)));
	let weaknessTags = $derived(safeWeaknesses.map((w) => tagFinding(w)));

	function formatConfidence(confidence: number): string {
		if (confidence <= 1) return `${Math.round(confidence * 100)}%`;
		return `${Math.round(confidence)}%`;
	}
</script>

<div
	class="pipeline-stage"
	data-pipeline-stage={stage}
	data-testid="narrative-stage-{stage}"
>
	<!-- Stage Header -->
	<div class="flex items-center gap-2 mb-1.5">
		<h3 class="section-heading" style="color: var(--color-{color});">
			{stageLabels[stage]}
		</h3>

		<!-- Headline summary -->
		<span class="flex items-center gap-1.5 text-xs text-text-dim">
			{#if stage === "analysis"}
				{#if result.task_type}
					<MetaBadge
						type="task"
						value={result.task_type}
						showTooltip={false}
						size="xs"
					/>
				{/if}
				{#if result.complexity}
					<span class="opacity-50">&middot;</span>
					<span class={getComplexityColor(result.complexity).text}
						>{result.complexity}</span
					> complexity
				{/if}
				{#if findingCount > 0}
					<span class="opacity-50">&middot;</span>
					{findingCount} findings
				{/if}
			{:else if stage === "strategy"}
				{#if result.strategy}
					<MetaBadge
						type="strategy"
						value={result.strategy}
						showTooltip={false}
						size="xs"
					/>
				{/if}
				{#if result.strategy_confidence}
					<span class="opacity-50">&middot;</span>
					{formatConfidence(result.strategy_confidence)} confidence
				{/if}
			{:else if stage === "optimization"}
				{#if result.framework_applied}
					Applied <MetaBadge
						type="strategy"
						value={result.framework_applied}
						showTooltip={false}
						size="xs"
					/>
				{/if}
				{#if safeChangesMade.length > 0}
					<span class="opacity-50">&middot;</span>
					{safeChangesMade.length} changes
				{/if}
			{/if}
		</span>
	</div>

	<!-- Stage Content -->
	{#if stage === "analysis"}
		{#if safeStrengths.length > 0 || safeWeaknesses.length > 0}
			<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
				{#if safeStrengths.length > 0}
					<div>
						<h4 class="mb-1 text-xs font-medium text-neon-green">
							Strengths ({safeStrengths.length})
						</h4>
						<ul class="space-y-1.5">
							{#each safeStrengths as strength, idx}
								{@const tags = strengthTags[idx]}
								<li
									class="flex items-start gap-2 rounded-md px-1 py-0.5 text-xs leading-snug text-text-secondary transition-colors duration-200"
									class:finding-highlight={highlightedDimension !==
										null &&
										tags.includes(highlightedDimension)}
									data-dimensions={tags.join(",")}
								>
									<span
										class="mt-2 h-1 w-1 shrink-0 rounded-full bg-neon-green"
									></span>
									{strength}
								</li>
							{/each}
						</ul>
					</div>
				{/if}
				{#if safeWeaknesses.length > 0}
					<div>
						<h4 class="mb-1 text-xs font-medium text-neon-red">
							Weaknesses ({safeWeaknesses.length})
						</h4>
						<ul class="space-y-1.5">
							{#each safeWeaknesses as weakness, idx}
								{@const tags = weaknessTags[idx]}
								<li
									class="flex items-start gap-2 rounded-md px-1 py-0.5 text-xs leading-snug text-text-secondary transition-colors duration-200"
									class:finding-highlight={highlightedDimension !==
										null &&
										tags.includes(highlightedDimension)}
									data-dimensions={tags.join(",")}
								>
									<span
										class="mt-2 h-1 w-1 shrink-0 rounded-full bg-neon-red"
									></span>
									{weakness}
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			</div>
		{/if}
	{:else if stage === "strategy"}
		{#if result.strategy_reasoning}
			<p class="text-xs leading-snug text-text-secondary">
				{result.strategy_reasoning}
			</p>
		{/if}
		{#if safeSecondary.length > 0}
			<div class="mt-2 flex items-center gap-1.5 flex-wrap">
				<span class="text-[11px] text-text-dim">Secondary:</span>
				{#each safeSecondary as sf}
					<MetaBadge
						type="strategy"
						value={sf}
						variant="pill"
						size="xs"
						showTooltip={false}
					/>
				{/each}
			</div>
		{/if}
	{:else if stage === "optimization"}
		{#if safeChangesMade.length > 0}
			<ul class="space-y-1.5">
				{#each safeChangesMade as change}
					<li
						class="flex items-start gap-2 text-xs leading-snug text-text-secondary"
					>
						<span
							class="mt-2 h-1 w-1 shrink-0 rounded-full bg-neon-purple"
						></span>
						{change}
					</li>
				{/each}
			</ul>
		{/if}
		{#if result.optimization_notes}
			<p class="mt-1.5 text-xs leading-snug text-text-dim italic">
				{result.optimization_notes}
			</p>
		{/if}
	{/if}
</div>
