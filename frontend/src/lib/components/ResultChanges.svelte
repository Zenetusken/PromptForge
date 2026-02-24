<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import Icon from './Icon.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	let showChanges = $state(false);
	let showNotes = $state(false);
</script>

{#if result.changes_made.length > 0}
	<div class="border-t border-border-subtle" data-testid="changes-made">
		<button
			type="button"
			onclick={() => showChanges = !showChanges}
			class="flex w-full items-center gap-2 px-2.5 py-2 text-left transition-colors hover:bg-bg-hover/20"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="shrink-0 text-text-dim transition-transform duration-200 {showChanges ? 'rotate-90' : ''}"
			/>
			<h4 class="section-heading">Changes Made</h4>
			<span class="ml-auto text-[10px] text-text-dim">{result.changes_made.length}</span>
		</button>
		{#if showChanges}
			<div class="animate-fade-in px-2.5 pb-2">
				<ul class="space-y-1.5">
					{#each result.changes_made as change}
						<li class="flex items-start gap-2 text-sm leading-relaxed text-text-secondary">
							<span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-neon-cyan"></span>
							{change}
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>
{/if}

{#if result.optimization_notes}
	<div class="border-t border-border-subtle" data-testid="optimization-notes">
		<button
			type="button"
			onclick={() => showNotes = !showNotes}
			class="flex w-full items-center gap-2 px-2.5 py-2 text-left transition-colors hover:bg-bg-hover/20"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="shrink-0 text-text-dim transition-transform duration-200 {showNotes ? 'rotate-90' : ''}"
			/>
			<h4 class="section-heading">Notes</h4>
		</button>
		{#if showNotes}
			<div class="animate-fade-in px-2.5 pb-2">
				<p class="text-sm leading-relaxed text-text-secondary">{result.optimization_notes}</p>
			</div>
		{/if}
	</div>
{/if}
