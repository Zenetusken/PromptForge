<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

	let { result }: { result: OptimizationResultState } = $props();
</script>

{#if result.title}
	<div class="border-b border-border-subtle px-5 py-4">
		<h3 class="font-display text-base font-bold text-text-primary" data-testid="result-title">{result.title}</h3>
	</div>
{/if}

<div class="flex flex-wrap items-center gap-2 border-b border-border-subtle px-5 py-3" data-testid="result-metadata">
	{#if result.task_type}
		<span class="badge rounded-full bg-neon-cyan/10 text-xs text-neon-cyan" data-testid="task-type-badge">
			{result.task_type}
		</span>
	{/if}
	{#if result.complexity}
		<span class="badge rounded-full bg-neon-purple/10 text-xs text-neon-purple" data-testid="complexity-badge">
			{result.complexity}
		</span>
	{/if}
	{#if result.framework_applied}
		<span class="badge rounded-full bg-bg-hover text-xs text-text-secondary" data-testid="framework-badge">
			{result.framework_applied}
		</span>
	{/if}
	{#if result.model_used}
		<span class="badge rounded-full bg-bg-hover text-xs text-text-dim" data-testid="model-badge">
			{result.model_used}
		</span>
	{/if}
	{#if result.project}
		<span class="badge rounded-full bg-neon-yellow/10 text-xs text-neon-yellow" data-testid="project-badge">
			{result.project}
		</span>
	{/if}
	{#if result.tags.length > 0}
		{#each result.tags as tag}
			<span class="badge rounded-full bg-neon-purple/10 text-neon-purple" data-testid="tag-badge">
				#{tag}
			</span>
		{/each}
	{/if}
	{#if result.is_improvement}
		<span class="badge rounded-full bg-neon-green/10 text-xs text-neon-green" data-testid="improvement-badge">
			Improved
		</span>
	{:else}
		<span class="badge rounded-full bg-neon-yellow/10 text-xs text-neon-yellow">
			No improvement
		</span>
	{/if}
	{#if result.duration_ms > 0}
		<span class="ml-auto font-mono text-xs tabular-nums text-text-dim" data-testid="duration">
			{(result.duration_ms / 1000).toFixed(1)}s
		</span>
	{/if}
</div>
