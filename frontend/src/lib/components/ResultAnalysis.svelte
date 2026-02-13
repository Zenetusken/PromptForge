<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

	let { result }: { result: OptimizationResultState } = $props();
</script>

{#if result.verdict}
	<div class="border-t border-text-dim/20 px-5 py-4" data-testid="verdict">
		<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
			Verdict
		</h4>
		<p class="text-sm leading-relaxed text-text-primary">{result.verdict}</p>
	</div>
{/if}

{#if result.strengths.length > 0 || result.weaknesses.length > 0}
	<div class="border-t border-text-dim/20 px-5 py-4" data-testid="analysis">
		<h4 class="mb-3 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
			Analysis
		</h4>
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
			{#if result.strengths.length > 0}
				<div>
					<h5 class="mb-1.5 font-mono text-xs font-medium text-neon-green">Strengths</h5>
					<ul class="space-y-1">
						{#each result.strengths as strength}
							<li class="flex items-start gap-2 text-sm text-text-secondary">
								<span class="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-neon-green"></span>
								{strength}
							</li>
						{/each}
					</ul>
				</div>
			{/if}
			{#if result.weaknesses.length > 0}
				<div>
					<h5 class="mb-1.5 font-mono text-xs font-medium text-neon-red">Weaknesses</h5>
					<ul class="space-y-1">
						{#each result.weaknesses as weakness}
							<li class="flex items-start gap-2 text-sm text-text-secondary">
								<span class="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-neon-red"></span>
								{weakness}
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	</div>
{/if}
