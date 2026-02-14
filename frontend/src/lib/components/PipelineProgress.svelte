<script lang="ts">
	import PipelineStep from './PipelineStep.svelte';
	import type { StepState } from '$lib/stores/optimization.svelte';

	let { steps }: { steps: StepState[] } = $props();

	// Find the latest active step (running or last completed)
	let latestActiveIndex = $derived.by(() => {
		// If any step is running, that's the active one
		const runningIdx = steps.findIndex((s) => s.status === 'running');
		if (runningIdx >= 0) return runningIdx;

		// Otherwise, find the last completed step
		let lastComplete = -1;
		for (let i = steps.length - 1; i >= 0; i--) {
			if (steps[i].status === 'complete') {
				lastComplete = i;
				break;
			}
		}
		return lastComplete;
	});
</script>

<div class="animate-fade-in rounded-2xl border border-border-subtle bg-bg-card/60 p-6" data-testid="pipeline-progress" aria-live="polite" role="status">
	<div class="mb-5 flex items-center gap-3">
		<div class="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-cyan shadow-[0_0_8px_var(--color-neon-cyan)]"></div>
		<h3 class="font-display text-sm font-bold uppercase tracking-widest text-text-secondary">
			Pipeline
		</h3>
	</div>

	<div class="flex items-start gap-2">
		{#each steps as step, i (step.name)}
			<PipelineStep {step} index={i} isLatestActive={i === latestActiveIndex} />
			{#if i < steps.length - 1}
				<div class="flex h-12 items-center pt-1">
					<div class="relative h-px w-8">
						<div class="absolute inset-0 bg-text-dim/15"></div>
						{#if step.status === 'complete'}
							<div class="absolute inset-0 bg-gradient-to-r from-neon-cyan to-neon-purple" style="animation: fade-in 500ms ease forwards;"></div>
						{/if}
					</div>
				</div>
			{/if}
		{/each}
	</div>
</div>
