<script lang="ts">
	import type { StepState } from '$lib/stores/optimization.svelte';

	let { step, index }: { step: StepState; index: number } = $props();

	function getColor(): string {
		if (index === 0) return 'neon-cyan';
		if (index === 1) return 'neon-purple';
		return 'neon-green';
	}

	let color = $derived(getColor());
	let isActive = $derived(step.status === 'running' || step.status === 'complete');

	// Extract useful data from completed steps
	let taskType = $derived(step.data?.task_type as string | undefined);
	let weaknesses = $derived(step.data?.weaknesses as string[] | undefined);
	let strengths = $derived(step.data?.strengths as string[] | undefined);
	let hasStepData = $derived(step.status === 'complete' && step.data && Object.keys(step.data).length > 0);
</script>

<div class="flex flex-1 flex-col items-center gap-2 rounded-lg p-3 text-center">
	<!-- Status indicator -->
	<div class="relative flex h-12 w-12 items-center justify-center">
		{#if step.status === 'running'}
			<div
				class="absolute inset-0 animate-ping rounded-full opacity-20"
				class:bg-neon-cyan={index === 0}
				class:bg-neon-purple={index === 1}
				class:bg-neon-green={index === 2}
			></div>
			<div
				class="flex h-10 w-10 items-center justify-center rounded-full border-2"
				class:border-neon-cyan={index === 0}
				class:border-neon-purple={index === 1}
				class:border-neon-green={index === 2}
			>
				<svg
					class="h-5 w-5 animate-spin"
					class:text-neon-cyan={index === 0}
					class:text-neon-purple={index === 1}
					class:text-neon-green={index === 2}
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
				>
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
			</div>
		{:else if step.status === 'complete'}
			<div
				class="flex h-10 w-10 items-center justify-center rounded-full {color === 'neon-cyan' ? 'bg-neon-cyan/20' : color === 'neon-purple' ? 'bg-neon-purple/20' : 'bg-neon-green/20'}"
			>
				<svg
					class="h-5 w-5"
					class:text-neon-cyan={index === 0}
					class:text-neon-purple={index === 1}
					class:text-neon-green={index === 2}
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					stroke-width="2"
				>
					<polyline points="20 6 9 17 4 12" />
				</svg>
			</div>
		{:else if step.status === 'error'}
			<div class="flex h-10 w-10 items-center justify-center rounded-full bg-neon-red/20">
				<svg
					class="h-5 w-5 text-neon-red"
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					stroke-width="2"
				>
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</div>
		{:else}
			<div class="flex h-10 w-10 items-center justify-center rounded-full border-2 border-text-dim/30">
				<span class="font-mono text-sm text-text-dim">{String(index + 1).padStart(2, '0')}</span>
			</div>
		{/if}
	</div>

	<!-- Step label -->
	<div
		class="font-mono text-sm font-semibold"
		class:text-neon-cyan={index === 0 && isActive}
		class:text-neon-purple={index === 1 && isActive}
		class:text-neon-green={index === 2 && isActive}
		class:text-text-dim={step.status === 'pending'}
		class:text-neon-red={step.status === 'error'}
	>
		{step.label}
	</div>

	<!-- Description -->
	{#if step.description}
		<div class="text-xs text-text-dim">{step.description}</div>
	{/if}

	<!-- Step data details (shown when complete) -->
	{#if hasStepData}
		<div class="mt-1 flex flex-col items-center gap-1">
			{#if taskType}
				<span class="inline-block rounded-full bg-neon-cyan/10 px-2 py-0.5 font-mono text-[10px] text-neon-cyan">
					{taskType}
				</span>
			{/if}
			{#if weaknesses && weaknesses.length > 0}
				<div class="flex flex-wrap justify-center gap-1">
					{#each weaknesses.slice(0, 2) as weakness}
						<span class="inline-block max-w-[140px] truncate rounded bg-neon-red/10 px-1.5 py-0.5 text-[10px] text-neon-red">
							{weakness}
						</span>
					{/each}
				</div>
			{/if}
			{#if strengths && strengths.length > 0}
				<div class="flex flex-wrap justify-center gap-1">
					{#each strengths.slice(0, 2) as strength}
						<span class="inline-block max-w-[140px] truncate rounded bg-neon-green/10 px-1.5 py-0.5 text-[10px] text-neon-green">
							{strength}
						</span>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
