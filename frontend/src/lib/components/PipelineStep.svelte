<script lang="ts">
	import type { StepState } from '$lib/stores/optimization.svelte';

	let { step, index, isLatestActive = false }: { step: StepState; index: number; isLatestActive?: boolean } = $props();

	function getColor(): string {
		if (index === 0) return 'neon-cyan';
		if (index === 1) return 'neon-purple';
		return 'neon-green';
	}

	let color = $derived(getColor());
	let isActive = $derived(step.status === 'running' || step.status === 'complete');

	function getBorderColor(): string {
		if (step.status === 'error') return 'var(--color-neon-red)';
		if (step.status === 'pending') return 'rgba(85, 85, 119, 0.3)';
		if (index === 0) return 'var(--color-neon-cyan)';
		if (index === 1) return 'var(--color-neon-purple)';
		return 'var(--color-neon-green)';
	}

	// Auto-collapse: show expanded only when running or when it's the latest completed and active
	let isExpanded = $derived(step.status === 'running' || isLatestActive);

	// ARIA status label for screen readers
	let ariaStatusLabel = $derived.by(() => {
		const stepNumber = index + 1;
		const statusText = step.status === 'running' ? 'in progress' : step.status;
		return `Step ${stepNumber} ${step.label}: ${statusText}`;
	});

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
			// Live timer will be updated via interval
			return '...';
		}
		return null;
	});

	// Format score for display (stored as 0-1 floats, display as 0-100)
	function formatScore(score: number | undefined): string {
		if (score === undefined || score === null) return '—';
		// Scores might be 0-1 or 0-100 range
		const displayScore = score <= 1 ? Math.round(score * 100) : Math.round(score);
		return String(displayScore);
	}

	// Live timer
	let liveTimer = $state('');
	let timerInterval: ReturnType<typeof setInterval> | null = null;

	$effect(() => {
		if (step.status === 'running' && step.startTime) {
			timerInterval = setInterval(() => {
				const elapsed = (Date.now() - (step.startTime || Date.now())) / 1000;
				liveTimer = elapsed.toFixed(1) + 's';
			}, 100);
		} else {
			if (timerInterval) {
				clearInterval(timerInterval);
				timerInterval = null;
			}
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
	class="flex flex-1 flex-col items-center gap-2 rounded-lg border-l-2 p-3 text-center transition-all duration-300"
	style="border-left-color: {getBorderColor()};"
	data-testid="pipeline-step-{step.name}"
	aria-label={ariaStatusLabel}
	role="group"
>
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

	<!-- Duration timer -->
	{#if step.status === 'running' && liveTimer}
		<div class="font-mono text-xs text-text-secondary" data-testid="step-timer-{step.name}">
			{liveTimer}
		</div>
	{:else if step.status === 'complete' && durationDisplay}
		<div class="font-mono text-xs text-text-secondary" data-testid="step-duration-{step.name}">
			{durationDisplay}
		</div>
	{/if}

	<!-- Description (shown when pending or running) -->
	{#if step.description && (step.status === 'pending' || step.status === 'running')}
		<div class="text-xs text-text-dim">{step.description}</div>
	{/if}

	<!-- Streaming content (shown while running) -->
	{#if step.status === 'running' && step.streamingContent}
		<div class="mt-1 w-full max-w-[200px] rounded border border-text-dim/20 bg-bg-primary/50 p-2 text-left" data-testid="streaming-content-{step.name}">
			<p class="whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-text-secondary">
				{step.streamingContent.trim()}
			</p>
			<span class="mt-1 inline-block h-3 w-1 animate-pulse bg-neon-cyan"></span>
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
			{#if isOptimizeStep && optimizedPrompt}
				<div class="mt-1 max-w-[200px] rounded border border-neon-purple/20 bg-neon-purple/5 p-1.5 text-left">
					<p class="line-clamp-3 font-mono text-[10px] leading-relaxed text-text-secondary">
						{optimizedPrompt.slice(0, 150)}{optimizedPrompt.length > 150 ? '...' : ''}
					</p>
				</div>
			{/if}
			{#if isValidateStep && overallScore !== undefined}
				<div class="mt-1 flex flex-col items-center gap-1" data-testid="step-scores">
					<div class="flex items-center gap-1">
						<span class="rounded-full bg-neon-green/20 px-2 py-0.5 font-mono text-sm font-bold text-neon-green" data-testid="overall-score">
							{formatScore(overallScore)}
						</span>
						<span class="text-[10px] text-text-dim">overall</span>
					</div>
					<div class="flex flex-wrap justify-center gap-1">
						{#if clarityScore !== undefined}
							<span class="rounded bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								CLA {formatScore(clarityScore)}
							</span>
						{/if}
						{#if specificityScore !== undefined}
							<span class="rounded bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								SPE {formatScore(specificityScore)}
							</span>
						{/if}
						{#if structureScore !== undefined}
							<span class="rounded bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
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
				<span class="rounded-full bg-neon-green/20 px-1.5 py-0.5 font-mono text-[9px] font-bold text-neon-green" data-testid="collapsed-score">
					{formatScore(overallScore)}
				</span>
			{/if}
			{#if durationDisplay}
				<span class="font-mono text-[9px] text-text-dim" data-testid="step-duration-{step.name}">
					{durationDisplay}
				</span>
			{/if}
		</div>
	{/if}
</div>
