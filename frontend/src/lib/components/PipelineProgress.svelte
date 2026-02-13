<script lang="ts">
	import PipelineStep from './PipelineStep.svelte';
	import type { StepState } from '$lib/stores/optimization.svelte';

	let { steps }: { steps: StepState[] } = $props();

	const defaultSteps: StepState[] = [
		{ name: 'analyze', label: 'ANALYZE', status: 'pending', description: 'Analyzing prompt structure and intent' },
		{ name: 'optimize', label: 'OPTIMIZE', status: 'pending', description: 'Rewriting for clarity and effectiveness' },
		{ name: 'validate', label: 'VALIDATE', status: 'pending', description: 'Scoring and quality assessment' }
	];

	let displaySteps = $derived(steps.length > 0 ? steps : defaultSteps);
</script>

<div class="rounded-xl border border-text-dim/20 bg-bg-card p-5" data-testid="pipeline-progress">
	<h3 class="mb-4 font-mono text-sm font-semibold uppercase tracking-wider text-text-secondary">
		Pipeline Progress
	</h3>

	<div class="flex items-start gap-2">
		{#each displaySteps as step, i (step.name)}
			<PipelineStep {step} index={i} />
			{#if i < displaySteps.length - 1}
				<div class="flex h-12 items-center pt-1">
					<div
						class="h-0.5 w-8 transition-colors duration-500 {step.status === 'complete' ? 'bg-neon-cyan' : 'bg-text-dim/30'}"
					></div>
				</div>
			{/if}
		{/each}
	</div>
</div>
