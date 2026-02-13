<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

	let { result }: { result: OptimizationResultState } = $props();
</script>

{#if result.changes_made.length > 0}
	<div class="border-t border-text-dim/20 px-5 py-4" data-testid="changes-made">
		<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
			Changes Made
		</h4>
		<ul class="space-y-1">
			{#each result.changes_made as change}
				<li class="flex items-start gap-2 text-sm text-text-secondary">
					<span class="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-neon-cyan"></span>
					{change}
				</li>
			{/each}
		</ul>
	</div>
{/if}

{#if result.optimization_notes}
	<div class="border-t border-text-dim/20 px-5 py-4" data-testid="optimization-notes">
		<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
			Notes
		</h4>
		<p class="text-sm leading-relaxed text-text-secondary">{result.optimization_notes}</p>
	</div>
{/if}
