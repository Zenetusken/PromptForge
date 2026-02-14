<script lang="ts">
	import type { StepState } from '$lib/stores/optimization.svelte';
	import { formatScore } from '$lib/utils/format';
	import Icon from './Icon.svelte';

	let { step, index, isLatestActive = false }: { step: StepState; index: number; isLatestActive?: boolean } = $props();

	let isActive = $derived(step.status === 'running' || step.status === 'complete');

	// Auto-collapse: show expanded only when running or when it's the latest completed and active
	let isExpanded = $derived(step.status === 'running' || isLatestActive);

	// ARIA status label for screen readers
	let ariaStatusLabel = $derived(
		`Step ${index + 1} ${step.label}: ${step.status === 'running' ? 'in progress' : step.status}`
	);

	// Extract useful data from completed steps
	let taskType = $derived(step.data?.task_type as string | undefined);
	let weaknesses = $derived(step.data?.weaknesses as string[] | undefined);
	let strengths = $derived(step.data?.strengths as string[] | undefined);
	let hasStepData = $derived(step.status === 'complete' && step.data && Object.keys(step.data).length > 0);

	// Scores for validate step
	let overallScore = $derived(step.data?.overall_score as number | undefined);
	let clarityScore = $derived(step.data?.clarity_score as number | undefined);
	let specificityScore = $derived(step.data?.specificity_score as number | undefined);
	let structureScore = $derived(step.data?.structure_score as number | undefined);
	let verdict = $derived(step.data?.verdict as string | undefined);
	let isValidateStep = $derived(step.name === 'validate');

	// Optimized prompt preview for optimize step
	let optimizedPrompt = $derived(step.data?.optimized_prompt as string | undefined);
	let isOptimizeStep = $derived(step.name === 'optimize');

	// Duration formatting
	let durationDisplay = $derived.by(() => {
		if (step.durationMs && step.durationMs > 0) {
			return (step.durationMs / 1000).toFixed(1) + 's';
		}
		if (step.status === 'running' && step.startTime) {
			return '...';
		}
		return null;
	});

	// Live timer
	let liveTimer = $state('');
	let timerInterval: ReturnType<typeof setInterval> | null = null;

	$effect(() => {
		// Always clear any existing interval first to prevent orphaned timers
		if (timerInterval) {
			clearInterval(timerInterval);
			timerInterval = null;
		}
		if (step.status === 'running' && step.startTime) {
			timerInterval = setInterval(() => {
				const elapsed = (Date.now() - (step.startTime || Date.now())) / 1000;
				liveTimer = Math.floor(elapsed) + 's';
			}, 1000);
		}
		return () => {
			if (timerInterval) {
				clearInterval(timerInterval);
				timerInterval = null;
			}
		};
	});
</script>

<div
	class="flex flex-1 flex-col items-center gap-2 rounded-xl p-3 text-center transition-[background-color] duration-300 {isExpanded ? 'bg-bg-hover/30' : ''}"
	data-testid="pipeline-step-{step.name}"
	aria-label={ariaStatusLabel}
	role="group"
>
	<!-- Status indicator -->
	<div class="relative flex h-11 w-11 items-center justify-center">
		{#if step.status === 'running'}
			<div
				class="absolute inset-0 animate-ping rounded-full opacity-15"
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
				<Icon
					name="spinner"
					size={16}
					class="animate-spin {index === 0 ? 'text-neon-cyan' : index === 1 ? 'text-neon-purple' : 'text-neon-green'}"
				/>
			</div>
		{:else if step.status === 'complete'}
			<div
				class="flex h-10 w-10 items-center justify-center rounded-full {index === 0 ? 'bg-neon-cyan/15' : index === 1 ? 'bg-neon-purple/15' : 'bg-neon-green/15'}"
			>
				<Icon
					name="check"
					size={16}
					class={index === 0 ? 'text-neon-cyan' : index === 1 ? 'text-neon-purple' : 'text-neon-green'}
				/>
			</div>
		{:else if step.status === 'error'}
			<div class="flex h-10 w-10 items-center justify-center rounded-full bg-neon-red/15">
				<Icon name="x" size={16} class="text-neon-red" />
			</div>
		{:else}
			<div class="flex h-10 w-10 items-center justify-center rounded-full border border-text-dim/20">
				<span class="font-mono text-xs text-text-dim">{String(index + 1).padStart(2, '0')}</span>
			</div>
		{/if}
	</div>

	<!-- Step label -->
	<div
		class="font-display text-xs font-bold tracking-widest"
		class:text-neon-cyan={index === 0 && isActive}
		class:text-neon-purple={index === 1 && isActive}
		class:text-neon-green={index === 2 && isActive}
		class:text-text-dim={step.status === 'pending'}
		class:text-neon-red={step.status === 'error'}
	>
		{step.label}
	</div>

	<!-- Duration timer -->
	{#if step.status === 'running' && liveTimer}
		<div class="font-mono text-[10px] tabular-nums text-text-secondary" data-testid="step-timer-{step.name}">
			{liveTimer}
		</div>
	{:else if step.status === 'complete' && durationDisplay}
		<div class="font-mono text-[10px] tabular-nums text-text-dim" data-testid="step-duration-{step.name}">
			{durationDisplay}
		</div>
	{/if}

	<!-- Description (shown when pending or running) -->
	{#if step.description && (step.status === 'pending' || step.status === 'running')}
		<div class="text-[11px] text-text-dim">{step.description}</div>
	{/if}

	<!-- Streaming content (shown while running) -->
	{#if step.status === 'running' && step.streamingContent}
		<div class="mt-1 w-full max-w-[200px] rounded-lg border border-border-subtle bg-bg-primary/60 p-2 text-left" data-testid="streaming-content-{step.name}">
			<p class="whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-text-secondary">
				{step.streamingContent.trim()}
			</p>
			<span class="mt-1 inline-block h-3 w-0.5 animate-pulse bg-neon-cyan"></span>
		</div>
	{/if}

	<!-- Step data details (shown when complete and expanded) -->
	{#if hasStepData && isExpanded}
		<div class="mt-1 flex flex-col items-center gap-1">
			{#if taskType}
				<span class="inline-block rounded-full bg-neon-cyan/10 px-2 py-0.5 font-mono text-[10px] text-neon-cyan">
					{taskType}
				</span>
			{/if}
			{#if weaknesses && weaknesses.length > 0}
				<div class="flex flex-wrap justify-center gap-1">
					{#each weaknesses.slice(0, 2) as weakness}
						<span class="inline-block max-w-[140px] truncate rounded-md bg-neon-red/8 px-1.5 py-0.5 text-[10px] text-neon-red">
							{weakness}
						</span>
					{/each}
				</div>
			{/if}
			{#if strengths && strengths.length > 0}
				<div class="flex flex-wrap justify-center gap-1">
					{#each strengths.slice(0, 2) as strength}
						<span class="inline-block max-w-[140px] truncate rounded-md bg-neon-green/8 px-1.5 py-0.5 text-[10px] text-neon-green">
							{strength}
						</span>
					{/each}
				</div>
			{/if}
			{#if isOptimizeStep && optimizedPrompt}
				<div class="mt-1 max-w-[200px] rounded-lg border border-neon-purple/15 bg-neon-purple/5 p-1.5 text-left">
					<p class="line-clamp-3 font-mono text-[10px] leading-relaxed text-text-secondary">
						{optimizedPrompt.slice(0, 150)}{optimizedPrompt.length > 150 ? '...' : ''}
					</p>
				</div>
			{/if}
			{#if isValidateStep && overallScore !== undefined}
				<div class="mt-1 flex flex-col items-center gap-1" data-testid="step-scores">
					<div class="flex items-center gap-1">
						<span class="rounded-full bg-neon-green/15 px-2 py-0.5 font-mono text-sm font-bold text-neon-green" data-testid="overall-score">
							{formatScore(overallScore)}
						</span>
						<span class="text-[10px] text-text-dim">overall</span>
					</div>
					<div class="flex flex-wrap justify-center gap-1">
						{#if clarityScore !== undefined}
							<span class="rounded-md bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								CLA {formatScore(clarityScore)}
							</span>
						{/if}
						{#if specificityScore !== undefined}
							<span class="rounded-md bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								SPE {formatScore(specificityScore)}
							</span>
						{/if}
						{#if structureScore !== undefined}
							<span class="rounded-md bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								STR {formatScore(structureScore)}
							</span>
						{/if}
					</div>
					{#if verdict}
						<span class="max-w-[180px] truncate text-[10px] text-text-secondary">
							{verdict}
						</span>
					{/if}
				</div>
			{/if}
		</div>
	{:else if step.status === 'complete' && !isExpanded}
		<!-- Collapsed completed step: just show summary -->
		<div class="mt-1 flex items-center gap-1">
			{#if taskType}
				<span class="inline-block rounded-full bg-neon-cyan/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-cyan">
					{taskType}
				</span>
			{/if}
			{#if isValidateStep && overallScore !== undefined}
				<span class="rounded-full bg-neon-green/15 px-1.5 py-0.5 font-mono text-[9px] font-bold text-neon-green" data-testid="collapsed-score">
					{formatScore(overallScore)}
				</span>
			{/if}
			{#if durationDisplay}
				<span class="font-mono text-[9px] tabular-nums text-text-dim" data-testid="step-duration-{step.name}">
					{durationDisplay}
				</span>
			{/if}
		</div>
	{/if}
</div>
