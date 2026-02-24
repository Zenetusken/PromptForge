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

	let findingCount = $derived(
		result.strengths.length + result.weaknesses.length,
	);

	/** Pre-compute dimension tags for each finding to avoid redundant regex work. */
	let strengthTags = $derived(result.strengths.map((s) => tagFinding(s)));
	let weaknessTags = $derived(result.weaknesses.map((w) => tagFinding(w)));

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
	<div class="flex items-center gap-2 mb-3">
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
				{#if result.changes_made.length > 0}
					<span class="opacity-50">&middot;</span>
					{result.changes_made.length} changes
				{/if}
			{/if}
		</span>
	</div>

	<!-- Stage Content -->
	{#if stage === "analysis"}
		{#if result.strengths.length > 0 || result.weaknesses.length > 0}
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				{#if result.strengths.length > 0}
					<div>
						<h4 class="mb-2 text-xs font-medium text-neon-green">
							Strengths ({result.strengths.length})
						</h4>
						<ul class="space-y-1.5">
							{#each result.strengths as strength, idx}
								{@const tags = strengthTags[idx]}
								<li
									class="flex items-start gap-2 rounded-md px-1.5 py-1 text-sm leading-relaxed text-text-secondary transition-all duration-200"
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
				{#if result.weaknesses.length > 0}
					<div>
						<h4 class="mb-2 text-xs font-medium text-neon-red">
							Weaknesses ({result.weaknesses.length})
						</h4>
						<ul class="space-y-1.5">
							{#each result.weaknesses as weakness, idx}
								{@const tags = weaknessTags[idx]}
								<li
									class="flex items-start gap-2 rounded-md px-1.5 py-1 text-sm leading-relaxed text-text-secondary transition-all duration-200"
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
			<p class="text-sm leading-relaxed text-text-secondary">
				{result.strategy_reasoning}
			</p>
		{/if}
		{#if result.secondary_frameworks.length > 0}
			<div class="mt-2 flex items-center gap-1.5 flex-wrap">
				<span class="text-[11px] text-text-dim">Secondary:</span>
				{#each result.secondary_frameworks as sf}
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
		{#if result.changes_made.length > 0}
			<ul class="space-y-1.5">
				{#each result.changes_made as change}
					<li
						class="flex items-start gap-2 text-sm leading-relaxed text-text-secondary"
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
			<p class="mt-3 text-xs leading-relaxed text-text-dim italic">
				{result.optimization_notes}
			</p>
		{/if}
	{/if}
</div>
