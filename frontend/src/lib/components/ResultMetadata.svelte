<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { normalizeScore, getScoreBadgeClass, formatMetadataSummary } from '$lib/utils/format';
	import MetadataSummaryLine from './MetadataSummaryLine.svelte';
	import Icon from './Icon.svelte';
	import { EntryTitle, Tooltip } from './ui';

	let { result }: { result: OptimizationResultState } = $props();
	let hasTokens = $derived(result.input_tokens > 0 || result.output_tokens > 0);
	let lowConfidence = $derived(result.strategy_confidence > 0 && result.strategy_confidence < 0.70);

	let segments = $derived(formatMetadataSummary({
		taskType: result.task_type,
		framework: result.framework_applied,
		model: result.model_used,
	}));

	let secondaryFrameworks = $derived(
		result.secondary_frameworks.length > 0 ? result.secondary_frameworks : null
	);

	let score = $derived(normalizeScore(result.scores.overall));
</script>

<!-- Row 1: Title + Score circle + Improvement arrow -->
{#if result.title || score !== null}
	<div class="flex items-center gap-3 border-b border-border-subtle px-5 py-4">
		<h3 class="min-w-0 flex-1 font-display text-base font-bold" data-testid="result-title">
			<EntryTitle title={result.title} />
		</h3>
		<div class="flex shrink-0 items-center gap-1.5">
			{#if result.is_improvement}
				<Tooltip text="Improved over original"><Icon name="arrow-up" size={14} class="text-neon-green" /></Tooltip>
			{/if}
			{#if score !== null}
				<Tooltip text="Overall quality score">
					<span class="score-circle {getScoreBadgeClass(result.scores.overall)}" data-testid="result-score-circle">
						{score}
					</span>
				</Tooltip>
			{/if}
		</div>
	</div>
{/if}

<!-- Row 2: Classification summary line + Row 3: Project / Tags / Technical -->
<div class="flex flex-col gap-2 border-b border-border-subtle px-5 py-3" data-testid="result-metadata">
	<!-- Classification line -->
	{#if segments.length > 0 || result.complexity}
		<div class="flex flex-wrap items-center gap-1.5">
			<MetadataSummaryLine
				{segments}
				complexity={result.complexity}
				{lowConfidence}
				confidenceValue={result.strategy_confidence}
			/>
			{#if secondaryFrameworks}
				{#each secondaryFrameworks as sf}
					<Tooltip text="Secondary framework: {sf}">
						<span class="rounded-full bg-neon-cyan/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-cyan" data-testid="secondary-framework-badge">+{sf}</span>
					</Tooltip>
				{/each}
			{/if}
		</div>
	{/if}

	<!-- Project + Tags + Technical stats -->
	<div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
		{#if result.project}
			{#if result.project_id}
				<a
					href="/projects/{result.project_id}"
					class="text-[11px] font-medium text-neon-yellow transition-colors hover:text-neon-yellow/80 hover:underline"
					data-testid="project-badge"
				>
					{result.project}
				</a>
			{:else}
				<span class="text-[11px] font-medium text-neon-yellow" data-testid="project-badge">
					{result.project}
				</span>
			{/if}
		{/if}
		{#if result.tags.length > 0}
			<div class="flex items-center gap-2">
				{#each result.tags as tag}
					<span class="tag-chip" data-testid="tag-badge">#{tag}</span>
				{/each}
			</div>
		{/if}
		{#if hasTokens || result.duration_ms > 0}
			<div class="ml-auto flex items-center gap-2 font-mono text-[10px] tabular-nums text-text-dim">
				{#if hasTokens}
					<Tooltip text="Tokens used during optimization">
						<span data-testid="token-usage">
							{result.input_tokens.toLocaleString()} in / {result.output_tokens.toLocaleString()} out
						</span>
					</Tooltip>
				{/if}
				{#if result.duration_ms > 0}
					<Tooltip text="Total optimization time">
						<span data-testid="duration">{(result.duration_ms / 1000).toFixed(1)}s</span>
					</Tooltip>
				{/if}
			</div>
		{/if}
	</div>
</div>
