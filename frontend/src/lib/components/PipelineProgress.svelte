<script lang="ts">
	import PipelineStep from './PipelineStep.svelte';
	import type { StepState } from '$lib/stores/optimization.svelte';

	let { steps }: { steps: StepState[] } = $props();

	// Find the latest active step (running or last completed)
	let latestActiveIndex = $derived.by(() => {
		const runningIdx = steps.findIndex((s) => s.status === 'running');
		if (runningIdx >= 0) return runningIdx;
		let lastComplete = -1;
		for (let i = steps.length - 1; i >= 0; i--) {
			if (steps[i].status === 'complete') {
				lastComplete = i;
				break;
			}
		}
		return lastComplete;
	});

	function formatElapsed(seconds: number): string {
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
	}

	// Total elapsed timer
	let totalElapsed = $state('');

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
			if (totalMs > 0) {
				totalElapsed = formatElapsed(Math.floor(totalMs / 1000));
			}
		}
	});

	// sr-only: announce only the latest step transition, not all steps cumulatively
	let liveAnnouncement = $derived.by(() => {
		const running = steps.find((s) => s.status === 'running');
		if (running) return `${running.label} running.`;
		// Find the last completed step
		for (let i = steps.length - 1; i >= 0; i--) {
			if (steps[i].status === 'complete') return `${steps[i].label} complete.`;
		}
		return '';
	});
</script>

<div class="animate-fade-in rounded-2xl border border-border-subtle bg-bg-card/60 p-6" data-testid="pipeline-progress">
	<div class="mb-5 flex items-center gap-3">
		<div class="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-cyan shadow-[0_0_8px_var(--color-neon-cyan)]"></div>
		<h3 class="font-display text-sm font-bold uppercase tracking-widest text-text-secondary">
			Pipeline
		</h3>
		{#if totalElapsed}
			<span class="font-mono text-[11px] tabular-nums text-text-dim" data-testid="pipeline-total-timer">{totalElapsed}</span>
		{/if}
	</div>

	<!-- sr-only live region: announces only the latest step transition -->
	<div class="sr-only" role="status" aria-live="polite" aria-atomic="true">
		{liveAnnouncement}
	</div>

	<!-- Desktop: horizontal, Mobile: vertical -->
	<div class="hidden sm:flex sm:items-start sm:gap-2">
		{#each steps as step, i (step.name)}
			<PipelineStep {step} index={i} isLatestActive={i === latestActiveIndex} />
			{#if i < steps.length - 1}
				<div class="flex h-12 items-center pt-1">
					<div class="relative h-0.5 w-12 rounded-full">
						<div class="absolute inset-0 rounded-full bg-text-dim/30"></div>
						{#if step.status === 'complete'}
							<div class="absolute inset-0 rounded-full bg-gradient-to-r from-neon-cyan to-neon-purple shadow-[0_0_6px_rgba(0,229,255,0.15)]" style="animation: fade-in 500ms ease forwards;"></div>
						{/if}
					</div>
				</div>
			{/if}
		{/each}
	</div>

	<!-- Mobile: vertical timeline -->
	<div class="flex flex-col gap-1 sm:hidden">
		{#each steps as step, i (step.name)}
			<PipelineStep {step} index={i} isLatestActive={i === latestActiveIndex} mobile={true} />
			{#if i < steps.length - 1}
				<div class="flex justify-center">
					<div class="relative h-6 w-0.5 rounded-full">
						<div class="absolute inset-0 rounded-full bg-text-dim/30"></div>
						{#if step.status === 'complete'}
							<div class="absolute inset-0 rounded-full bg-gradient-to-b from-neon-cyan to-neon-purple shadow-[0_0_6px_rgba(0,229,255,0.15)]" style="animation: fade-in 500ms ease forwards;"></div>
						{/if}
					</div>
				</div>
			{/if}
		{/each}
	</div>
</div>
