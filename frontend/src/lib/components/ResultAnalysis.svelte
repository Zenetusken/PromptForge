<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import Icon from './Icon.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	let showStrategy = $state(false);
	let showVerdict = $state(false);
	let showAnalysis = $state(false);
</script>

{#if result.strategy_reasoning}
	<div class="border-t border-border-subtle" data-testid="strategy-reasoning">
		<button
			type="button"
			onclick={() => showStrategy = !showStrategy}
			class="flex w-full items-center gap-2 px-5 py-3.5 text-left transition-colors hover:bg-bg-hover/20"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="shrink-0 text-text-dim transition-transform duration-200 {showStrategy ? 'rotate-90' : ''}"
			/>
			<h4 class="section-heading">Strategy</h4>
		</button>
		{#if showStrategy}
			<div class="animate-fade-in px-5 pb-4">
				<p class="text-sm leading-relaxed text-text-secondary">{result.strategy_reasoning}</p>
				{#if result.secondary_frameworks && result.secondary_frameworks.length > 0}
					<div class="mt-2 flex items-center gap-1.5">
						<span class="text-[11px] text-text-dim">Secondary:</span>
						{#each result.secondary_frameworks as sf}
							<span class="rounded-full bg-neon-cyan/10 px-2 py-0.5 font-mono text-[10px] text-neon-cyan">
								{sf}
							</span>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}

{#if result.verdict}
	<div class="border-t border-border-subtle" data-testid="verdict">
		<button
			type="button"
			onclick={() => showVerdict = !showVerdict}
			class="flex w-full items-center gap-2 px-5 py-3.5 text-left transition-colors hover:bg-bg-hover/20"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="shrink-0 text-text-dim transition-transform duration-200 {showVerdict ? 'rotate-90' : ''}"
			/>
			<h4 class="section-heading">Verdict</h4>
		</button>
		{#if showVerdict}
			<div class="animate-fade-in px-5 pb-4">
				<p class="text-sm leading-relaxed text-text-secondary">{result.verdict}</p>
			</div>
		{/if}
	</div>
{/if}

{#if result.strengths.length > 0 || result.weaknesses.length > 0}
	<div class="border-t border-border-subtle" data-testid="analysis">
		<button
			type="button"
			onclick={() => showAnalysis = !showAnalysis}
			class="flex w-full items-center gap-2 px-5 py-3.5 text-left transition-colors hover:bg-bg-hover/20"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="shrink-0 text-text-dim transition-transform duration-200 {showAnalysis ? 'rotate-90' : ''}"
			/>
			<h4 class="section-heading">Analysis</h4>
			<span class="ml-auto text-[10px] text-text-dim">
				{result.strengths.length + result.weaknesses.length} items
			</span>
		</button>
		{#if showAnalysis}
			<div class="animate-fade-in px-5 pb-4">
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
					{#if result.strengths.length > 0}
						<div>
							<h5 class="mb-2 text-xs font-medium text-neon-green">Strengths</h5>
							<ul class="space-y-1.5">
								{#each result.strengths as strength}
									<li class="flex items-start gap-2 text-sm leading-relaxed text-text-secondary">
										<span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-neon-green"></span>
										{strength}
									</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if result.weaknesses.length > 0}
						<div>
							<h5 class="mb-2 text-xs font-medium text-neon-red">Weaknesses</h5>
							<ul class="space-y-1.5">
								{#each result.weaknesses as weakness}
									<li class="flex items-start gap-2 text-sm leading-relaxed text-text-secondary">
										<span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-neon-red"></span>
										{weakness}
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</div>
{/if}
