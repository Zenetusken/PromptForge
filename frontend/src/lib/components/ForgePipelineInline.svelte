<script lang="ts">
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { stepDotClass } from '$lib/utils/scoreDimensions';
	import PipelineStep from './PipelineStep.svelte';
	import ForgeError from './ForgeError.svelte';

	let steps = $derived(optimizationState.currentRun?.steps ?? []);

	// Find the latest active step
	let latestActiveIndex = $derived.by(() => {
		const runningIdx = steps.findIndex((s) => s.status === 'running');
		if (runningIdx >= 0) return runningIdx;
		let lastComplete = -1;
		for (let i = steps.length - 1; i >= 0; i--) {
			if (steps[i].status === 'complete') { lastComplete = i; break; }
		}
		return lastComplete;
	});

	// Total elapsed timer
	let totalElapsed = $state('');

	function formatElapsed(seconds: number): string {
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
	}

	$effect(() => {
		const anyRunning = steps.some((s) => s.status === 'running');
		const startTimes = steps.map((s) => s.startTime).filter((t): t is number => t !== undefined);
		const earliest = startTimes.length > 0 ? Math.min(...startTimes) : null;

		if (anyRunning && earliest) {
			const interval = setInterval(() => {
				totalElapsed = formatElapsed(Math.floor((Date.now() - earliest) / 1000));
			}, 1000);
			return () => clearInterval(interval);
		} else if (earliest) {
			const totalMs = steps.reduce((sum, s) => sum + (s.durationMs ?? 0), 0);
			if (totalMs > 0) totalElapsed = formatElapsed(Math.floor(totalMs / 1000));
		}
	});

	let isExpanded = $derived(!forgeMachine.isCompact);
</script>

<div class="flex flex-1 flex-col overflow-y-auto" data-testid="forge-pipeline-inline">
	{#if steps.length > 0}
		{#if isExpanded}
			<!-- Expanded pipeline: vertical step list -->
			<div class="px-2.5 pt-2.5 animate-fade-in">
				<div class="mb-2 flex items-center gap-2">
					<div class="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-cyan"></div>
					<h3 class="font-display text-[11px] font-bold uppercase tracking-widest text-text-secondary">
						Pipeline
					</h3>
					{#if totalElapsed}
						<span class="font-mono text-[10px] tabular-nums text-text-dim">{totalElapsed}</span>
					{/if}
				</div>

				<div class="flex flex-col gap-1">
					{#each steps as step, i (step.name)}
						<PipelineStep {step} index={i} isLatestActive={i === latestActiveIndex} mobile={true} />
						{#if i < steps.length - 1}
							<div class="flex justify-center">
								<div class="relative h-4 w-0.5 rounded-full">
									<div class="absolute inset-0 rounded-full bg-text-dim/30"></div>
									{#if step.status === 'complete'}
										<div class="absolute inset-0 rounded-full bg-gradient-to-b from-neon-cyan to-neon-purple" style="animation: fade-in 500ms ease forwards;"></div>
									{/if}
								</div>
							</div>
						{/if}
					{/each}
				</div>
			</div>
		{:else}
			<!-- Compact pipeline: dots only -->
			<div class="px-2.5 pt-2.5">
				<div class="flex items-center gap-2 mb-2">
					<div class="flex items-center gap-1">
						{#each steps as step}
							<div class="h-2 w-2 rounded-full {stepDotClass(step.status)}"></div>
						{/each}
					</div>
					{#if totalElapsed}
						<span class="font-mono text-[9px] tabular-nums text-text-dim">{totalElapsed}</span>
					{/if}
				</div>
				{#if optimizationState.currentRun}
					{@const currentStep = steps.find((s) => s.status === 'running')}
					{#if currentStep}
						<div class="text-[10px] text-text-dim mb-1">
							<span class="text-neon-cyan font-bold">{currentStep.label}</span>
							{#if currentStep.description}
								<span class="text-text-dim/60"> — {currentStep.description}</span>
							{/if}
						</div>
						{#if currentStep.streamingContent}
							<div class="rounded-md border border-border-subtle bg-bg-primary/60 p-1.5 mb-1">
								<p class="line-clamp-3 whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-text-secondary">
									{currentStep.streamingContent.trim()}
								</p>
								<span class="mt-0.5 inline-block h-2.5 w-0.5 animate-pulse bg-neon-cyan"></span>
							</div>
						{/if}
					{/if}
				{/if}
			</div>
		{/if}
	{/if}

	<!-- Error display -->
	<div class="px-2.5 pt-1.5">
		<ForgeError />
	</div>
</div>
