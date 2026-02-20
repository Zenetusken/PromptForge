<script lang="ts">
	import type { StepState } from '$lib/stores/optimization.svelte';
	import { formatScore } from '$lib/utils/format';
	import { safeStringOrUndefined, safeNumberOrUndefined, safeArrayOrUndefined } from '$lib/utils/safe';
	import { getStrategyColor } from '$lib/utils/strategies';
	import Icon from './Icon.svelte';
	import { Tooltip } from './ui';

	let { step, index, isLatestActive = false, mobile = false }: { step: StepState; index: number; isLatestActive?: boolean; mobile?: boolean } = $props();

	let isActive = $derived(step.status === 'running' || step.status === 'complete');

	// Click-to-expand override for completed steps
	let expandedOverride: boolean | null = $state(null);

	// Auto-collapse: show expanded only when running or when it's the latest completed and active
	// expandedOverride takes precedence for completed steps
	let isExpanded = $derived.by(() => {
		if (step.status === 'running') return true;
		if (step.status === 'complete' && expandedOverride !== null) return expandedOverride;
		return isLatestActive;
	});

	function toggleExpand() {
		if (step.status === 'complete') {
			expandedOverride = expandedOverride === null ? !isLatestActive : !expandedOverride;
		}
	}

	// ARIA status label for screen readers
	let ariaStatusLabel = $derived(
		`Step ${index + 1} ${step.label}: ${step.status === 'running' ? 'in progress' : step.status}`
	);

	// Extract useful data from completed steps
	let taskType = $derived(safeStringOrUndefined(step.data?.task_type));
	let complexity = $derived(safeStringOrUndefined(step.data?.complexity));
	let weaknesses = $derived(safeArrayOrUndefined(step.data?.weaknesses));
	let strengths = $derived(safeArrayOrUndefined(step.data?.strengths));
	let hasStepData = $derived(step.status === 'complete' && step.data && Object.keys(step.data).length > 0);

	// Scores for validate step
	let overallScore = $derived(safeNumberOrUndefined(step.data?.overall_score));
	let clarityScore = $derived(safeNumberOrUndefined(step.data?.clarity_score));
	let specificityScore = $derived(safeNumberOrUndefined(step.data?.specificity_score));
	let structureScore = $derived(safeNumberOrUndefined(step.data?.structure_score));
	let verdict = $derived(safeStringOrUndefined(step.data?.verdict));
	let isValidateStep = $derived(step.name === 'validate');

	// Optimized prompt preview and strategy badge for optimize step
	let optimizedPrompt = $derived(safeStringOrUndefined(step.data?.optimized_prompt));
	let frameworkApplied = $derived(safeStringOrUndefined(step.data?.framework_applied));
	let isOptimizeStep = $derived(step.name === 'optimize');

	// Strategy step data
	let isStrategyStep = $derived(step.name === 'strategy');
	let strategyName = $derived(safeStringOrUndefined(step.data?.strategy));
	let strategyReasoning = $derived(safeStringOrUndefined(step.data?.reasoning));
	let strategyConfidence = $derived(safeNumberOrUndefined(step.data?.confidence));
	let strategyTaskType = $derived(safeStringOrUndefined(step.data?.task_type));
	let isManualOverride = $derived(step.data?.is_override === true || (strategyReasoning?.startsWith('User-specified') ?? false));
	let secondaryFrameworks = $derived(safeArrayOrUndefined(step.data?.secondary_frameworks));
	let isAnalyzeStep = $derived(step.name === 'analyze');

	// Confidence color: green >= 0.80, yellow 0.60-0.79, orange < 0.60
	let confidenceColor = $derived.by(() => {
		if (strategyConfidence === undefined) return 'text-text-dim';
		if (strategyConfidence >= 0.80) return 'text-neon-green';
		if (strategyConfidence >= 0.60) return 'text-neon-yellow';
		return 'text-neon-red';
	});

	// Step color scheme: analyze=cyan, strategy=yellow, optimize=purple, validate=green
	const stepColors: Record<string, string> = {
		analyze: 'neon-cyan',
		strategy: 'neon-yellow',
		optimize: 'neon-purple',
		validate: 'neon-green',
	};
	let stepColor = $derived(stepColors[step.name] || 'neon-cyan');

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

{#if mobile}
<!-- Mobile: horizontal row layout -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions -->
<div
	class="flex items-start gap-3 rounded-xl p-3 transition-[background-color] duration-300 {isExpanded ? 'bg-bg-hover/30' : ''} {step.status === 'complete' ? 'cursor-pointer' : ''}"
	data-testid="pipeline-step-{step.name}"
	aria-label={ariaStatusLabel}
	role={step.status === 'complete' ? 'button' : 'group'}
	onclick={toggleExpand}
	onkeydown={(e) => { if (step.status === 'complete' && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggleExpand(); } }}
	tabindex={step.status === 'complete' ? 0 : -1}
>
	<!-- Left: icon -->
	<div class="relative flex h-9 w-9 shrink-0 items-center justify-center">
		{#if step.status === 'running'}
			<div class="absolute inset-0 animate-ping rounded-full opacity-15" style="background-color: var(--color-{stepColor})"></div>
			<div class="flex h-9 w-9 items-center justify-center rounded-full border-2" style="border-color: var(--color-{stepColor})">
				<Icon name="spinner" size={14} class="animate-spin" style="color: var(--color-{stepColor})" />
			</div>
		{:else if step.status === 'complete'}
			<div class="flex h-9 w-9 items-center justify-center rounded-full" style="background-color: color-mix(in srgb, var(--color-{stepColor}) 15%, transparent)">
				<Icon name="check" size={14} style="color: var(--color-{stepColor})" />
			</div>
		{:else if step.status === 'error'}
			<div class="flex h-9 w-9 items-center justify-center rounded-full bg-neon-red/15">
				<Icon name="x" size={14} class="text-neon-red" />
			</div>
		{:else}
			<div class="flex h-9 w-9 items-center justify-center rounded-full border border-text-dim/20">
				<span class="font-mono text-xs text-text-dim">{String(index + 1).padStart(2, '0')}</span>
			</div>
		{/if}
	</div>

	<!-- Right: label + content -->
	<div class="min-w-0 flex-1">
		<div class="flex items-center gap-2">
			<span
				class="font-display text-xs font-bold tracking-widest"
				class:text-text-dim={step.status === 'pending'}
				class:text-neon-red={step.status === 'error'}
				style={isActive && step.status !== 'error' ? `color: var(--color-${stepColor})` : ''}
			>
				{step.label}
			</span>
			{#if step.status === 'running' && liveTimer}
				<span class="font-mono text-[10px] tabular-nums text-text-secondary">{liveTimer}</span>
			{:else if step.status === 'complete' && durationDisplay}
				<span class="font-mono text-[10px] tabular-nums text-text-dim">{durationDisplay}</span>
			{/if}
		</div>

		{#if step.description && (step.status === 'pending' || step.status === 'running')}
			<div class="mt-0.5 text-[11px] text-text-dim">{step.description}</div>
		{/if}

		{#if step.status === 'running' && step.streamingContent}
			<div class="mt-1.5 w-full max-w-sm rounded-lg border border-border-subtle bg-bg-primary/60 p-2 text-left" style="border-left: 2px solid color-mix(in srgb, var(--color-{stepColor}) 40%, transparent)">
				<p class="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text-secondary">
					{step.streamingContent.trim()}
				</p>
				<span class="mt-1 inline-block h-3 w-0.5 animate-pulse bg-neon-cyan"></span>
			</div>
		{/if}

		<!-- Collapsed summary badges on mobile -->
		{#if step.status === 'complete' && !isExpanded}
			<div class="mt-1 flex flex-wrap items-center gap-1">
				{#if isAnalyzeStep && taskType}
					<span class="inline-block rounded-full bg-neon-cyan/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-cyan">{taskType}</span>
				{/if}
				{#if isStrategyStep && strategyName}
					<span class="inline-block rounded-full bg-neon-yellow/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-yellow">{strategyName}</span>
					{#if secondaryFrameworks && secondaryFrameworks.length > 0}
						{#each secondaryFrameworks as sf}
							<span class="inline-block rounded-full bg-neon-yellow/5 px-1.5 py-0.5 font-mono text-[9px] text-neon-yellow/60">+{sf}</span>
						{/each}
					{/if}
				{/if}
				{#if isOptimizeStep && frameworkApplied}
					{@const fwc = getStrategyColor(frameworkApplied)}
					<span class="inline-block rounded-full px-1.5 py-0.5 font-mono text-[9px] {fwc.text}" style="background: color-mix(in srgb, currentColor 10%, transparent)">{frameworkApplied}</span>
				{/if}
				{#if isValidateStep && overallScore !== undefined}
					<span class="rounded-full bg-neon-green/15 px-1.5 py-0.5 font-mono text-[9px] font-bold text-neon-green">{formatScore(overallScore)}</span>
				{/if}
			</div>
		{/if}

		<!-- Expanded data on mobile -->
		{#if hasStepData && isExpanded}
			<div class="mt-1.5 flex flex-wrap items-center gap-1">
				{#if isAnalyzeStep && taskType}
					<span class="inline-block rounded-full bg-neon-cyan/10 px-2 py-0.5 font-mono text-[10px] text-neon-cyan">{taskType}</span>
					{#if complexity}
						<span class="inline-block rounded-full bg-neon-purple/10 px-2 py-0.5 font-mono text-[10px] text-neon-purple">{complexity}</span>
					{/if}
				{/if}
				{#if isAnalyzeStep && weaknesses && weaknesses.length > 0}
					{#each weaknesses.slice(0, 2) as weakness}
						<span class="inline-block max-w-[200px] truncate rounded-md bg-neon-red/8 px-1.5 py-0.5 text-[10px] text-neon-red">{weakness}</span>
					{/each}
				{/if}
				{#if isStrategyStep && strategyName}
					<span class="inline-block rounded-full bg-neon-yellow/10 px-2 py-0.5 font-mono text-[10px] text-neon-yellow">{strategyName}</span>
					{#if secondaryFrameworks && secondaryFrameworks.length > 0}
						{#each secondaryFrameworks as sf}
							<span class="inline-block rounded-full bg-neon-yellow/5 px-1.5 py-0.5 font-mono text-[9px] text-neon-yellow/60">+{sf}</span>
						{/each}
					{/if}
					{#if strategyConfidence !== undefined}
						<span class="font-mono text-[10px] {confidenceColor}">{Math.round(strategyConfidence * 100)}%</span>
					{/if}
				{/if}
				{#if isOptimizeStep && frameworkApplied}
					{@const fwc = getStrategyColor(frameworkApplied)}
					<span class="inline-block rounded-full px-2 py-0.5 font-mono text-[10px] {fwc.text}" style="background: color-mix(in srgb, currentColor 10%, transparent)">{frameworkApplied}</span>
				{/if}
				{#if isValidateStep && overallScore !== undefined}
					<span class="rounded-full bg-neon-green/15 px-2 py-0.5 font-mono text-sm font-bold text-neon-green">{formatScore(overallScore)}</span>
					<span class="text-[10px] text-text-dim">overall</span>
				{/if}
			</div>
			{#if isStrategyStep && strategyReasoning}
				<p class="mt-1 max-w-sm text-[10px] leading-relaxed text-text-secondary">{strategyReasoning}</p>
			{/if}
		{/if}
	</div>
</div>
{:else}
<!-- Desktop: vertical column layout -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions -->
<div
	class="flex flex-1 flex-col items-center gap-2 rounded-xl p-3 text-center transition-[background-color] duration-300 {isExpanded ? 'bg-bg-hover/30' : ''} {step.status === 'complete' ? 'cursor-pointer' : ''}"
	data-testid="pipeline-step-{step.name}"
	aria-label={ariaStatusLabel}
	role={step.status === 'complete' ? 'button' : 'group'}
	onclick={toggleExpand}
	onkeydown={(e) => { if (step.status === 'complete' && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggleExpand(); } }}
	tabindex={step.status === 'complete' ? 0 : -1}
>
	<!-- Status indicator -->
	<div class="relative flex h-11 w-11 items-center justify-center">
		{#if step.status === 'running'}
			<div
				class="absolute inset-0 animate-ping rounded-full opacity-15"
				style="background-color: var(--color-{stepColor})"
			></div>
			<div
				class="flex h-10 w-10 items-center justify-center rounded-full border-2"
				style="border-color: var(--color-{stepColor})"
			>
				<Icon
					name="spinner"
					size={16}
					class="animate-spin"
					style="color: var(--color-{stepColor})"
				/>
			</div>
		{:else if step.status === 'complete'}
			<div
				class="flex h-10 w-10 items-center justify-center rounded-full"
				style="background-color: color-mix(in srgb, var(--color-{stepColor}) 15%, transparent)"
			>
				<Icon
					name="check"
					size={16}
					style="color: var(--color-{stepColor})"
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
		class:text-text-dim={step.status === 'pending'}
		class:text-neon-red={step.status === 'error'}
		style={isActive && step.status !== 'error' ? `color: var(--color-${stepColor})` : ''}
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
		<div
			class="mt-1 w-full max-w-[280px] rounded-lg border border-border-subtle bg-bg-primary/60 p-2 text-left"
			style="border-left: 2px solid color-mix(in srgb, var(--color-{stepColor}) 40%, transparent)"
			data-testid="streaming-content-{step.name}"
		>
			<p class="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text-secondary">
				{step.streamingContent.trim()}
			</p>
			<span class="mt-1 inline-block h-3 w-0.5 animate-pulse bg-neon-cyan"></span>
		</div>
	{/if}

	<!-- Step data details (shown when complete and expanded) -->
	{#if hasStepData && isExpanded}
		<div class="mt-1 flex flex-col items-center gap-1">
			{#if isAnalyzeStep && taskType}
				<div class="flex items-center gap-1">
					<span class="inline-block rounded-full bg-neon-cyan/10 px-2 py-0.5 font-mono text-[10px] text-neon-cyan">
						{taskType}
					</span>
					{#if complexity}
						<Tooltip text="Prompt complexity level">
							<span class="inline-block rounded-full bg-neon-purple/10 px-2 py-0.5 font-mono text-[10px] text-neon-purple" data-testid="complexity-badge">
								{complexity}
							</span>
						</Tooltip>
					{/if}
				</div>
			{/if}
			{#if isAnalyzeStep && weaknesses && weaknesses.length > 0}
				<div class="flex flex-wrap justify-center gap-1">
					{#each weaknesses.slice(0, 2) as weakness}
						<Tooltip text={weakness}>
							<span class="inline-block max-w-[140px] truncate rounded-md bg-neon-red/8 px-1.5 py-0.5 text-[10px] text-neon-red">
								{weakness}
							</span>
						</Tooltip>
					{/each}
				</div>
			{/if}
			{#if isAnalyzeStep && strengths && strengths.length > 0}
				<div class="flex flex-wrap justify-center gap-1">
					{#each strengths.slice(0, 2) as strength}
						<Tooltip text={strength}>
							<span class="inline-block max-w-[140px] truncate rounded-md bg-neon-green/8 px-1.5 py-0.5 text-[10px] text-neon-green">
								{strength}
							</span>
						</Tooltip>
					{/each}
				</div>
			{/if}
			{#if isStrategyStep && strategyName}
				<div class="flex items-center gap-1">
					<span class="inline-block rounded-full bg-neon-yellow/10 px-2 py-0.5 font-mono text-[10px] text-neon-yellow" data-testid="strategy-badge">
						{strategyName}
					</span>
					<Tooltip text={isManualOverride ? 'Strategy manually selected' : 'Strategy auto-selected by LLM'}>
						<span
							class="inline-block rounded-full px-1.5 py-0.5 font-mono text-[9px] {isManualOverride ? 'bg-neon-purple/10 text-neon-purple' : 'bg-neon-cyan/10 text-neon-cyan'}"
							data-testid="strategy-mode-badge"
						>
							{isManualOverride ? 'manual' : 'auto'}
						</span>
					</Tooltip>
				</div>
				{#if secondaryFrameworks && secondaryFrameworks.length > 0}
					<div class="flex items-center gap-1">
						{#each secondaryFrameworks as sf}
							<Tooltip text="Secondary framework: {sf}">
								<span class="inline-block rounded-full bg-neon-yellow/5 px-1.5 py-0.5 font-mono text-[9px] text-neon-yellow/60" data-testid="secondary-badge">
									+ {sf}
								</span>
							</Tooltip>
						{/each}
					</div>
				{/if}
				{#if strategyTaskType}
					<Tooltip text="Detected task type">
						<span class="inline-block rounded-full bg-neon-cyan/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-cyan" data-testid="strategy-task-type">
							{strategyTaskType}
						</span>
					</Tooltip>
				{/if}
				{#if strategyConfidence !== undefined}
					<Tooltip text="LLM confidence in this strategy selection">
						<span class="font-mono text-[10px] {confidenceColor}" data-testid="strategy-confidence">
							{Math.round(strategyConfidence * 100)}% confidence
						</span>
					</Tooltip>
				{/if}
				{#if strategyReasoning}
					<p class="max-w-[200px] text-center text-[10px] leading-relaxed text-text-secondary">
						{strategyReasoning}
					</p>
				{/if}
				{#if strategyConfidence !== undefined && strategyConfidence < 0.70}
					<p class="max-w-[200px] text-center text-[9px] text-neon-yellow" data-testid="low-confidence-warning">
						Low confidence — consider selecting a strategy manually
					</p>
				{/if}
			{/if}
			{#if isOptimizeStep && frameworkApplied}
				{@const fwc = getStrategyColor(frameworkApplied)}
				<span class="inline-block rounded-full px-2 py-0.5 font-mono text-[10px] {fwc.text}" style="background: color-mix(in srgb, currentColor 10%, transparent)" data-testid="framework-badge">
					{frameworkApplied}
				</span>
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
							<Tooltip text="Clarity"><span class="rounded-md bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								CLR {formatScore(clarityScore)}
							</span></Tooltip>
						{/if}
						{#if specificityScore !== undefined}
							<Tooltip text="Specificity"><span class="rounded-md bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								SPC {formatScore(specificityScore)}
							</span></Tooltip>
						{/if}
						{#if structureScore !== undefined}
							<Tooltip text="Structure"><span class="rounded-md bg-bg-primary/50 px-1 py-0.5 text-[9px] text-text-secondary">
								STR {formatScore(structureScore)}
							</span></Tooltip>
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
		<div class="mt-1 flex flex-wrap items-center justify-center gap-1">
			{#if isAnalyzeStep && taskType}
				<span class="inline-block rounded-full bg-neon-cyan/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-cyan">
					{taskType}
				</span>
				{#if complexity}
					<Tooltip text="Prompt complexity level">
					<span class="inline-block rounded-full bg-neon-purple/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-purple">
						{complexity}
					</span>
					</Tooltip>
				{/if}
			{/if}
			{#if isStrategyStep && strategyName}
				<span class="inline-block rounded-full bg-neon-yellow/10 px-1.5 py-0.5 font-mono text-[9px] text-neon-yellow" data-testid="collapsed-strategy-badge">
					{strategyName}
				</span>
				{#if secondaryFrameworks && secondaryFrameworks.length > 0}
					{#each secondaryFrameworks as sf}
						<Tooltip text="Secondary framework: {sf}">
							<span class="inline-block rounded-full bg-neon-yellow/5 px-1 py-0.5 font-mono text-[8px] text-neon-yellow/60" data-testid="collapsed-secondary-badge">
								+{sf}
							</span>
						</Tooltip>
					{/each}
				{/if}
				<Tooltip text={isManualOverride ? 'Strategy manually selected' : 'Strategy auto-selected by LLM'}>
					<span
						class="inline-block rounded-full px-1 py-0.5 font-mono text-[8px] {isManualOverride ? 'bg-neon-purple/10 text-neon-purple' : 'bg-neon-cyan/10 text-neon-cyan'}"
						data-testid="collapsed-strategy-mode-badge"
					>
						{isManualOverride ? 'manual' : 'auto'}
					</span>
				</Tooltip>
				{#if strategyTaskType}
					<Tooltip text="Detected task type">
						<span class="inline-block rounded-full bg-neon-cyan/10 px-1 py-0.5 font-mono text-[8px] text-neon-cyan" data-testid="collapsed-strategy-task-type">
							{strategyTaskType}
						</span>
					</Tooltip>
				{/if}
				{#if strategyConfidence !== undefined}
					<Tooltip text="LLM confidence in this strategy selection">
						<span class="font-mono text-[8px] {confidenceColor}" data-testid="collapsed-strategy-confidence">
							{Math.round(strategyConfidence * 100)}%
						</span>
					</Tooltip>
				{/if}
				{#if strategyReasoning && !isManualOverride}
					<Tooltip text={strategyReasoning}><span class="inline-block max-w-[120px] truncate text-[8px] text-text-dim" data-testid="collapsed-strategy-reasoning">
						{strategyReasoning}
					</span></Tooltip>
				{/if}
			{/if}
			{#if isOptimizeStep && frameworkApplied}
				{@const fwc = getStrategyColor(frameworkApplied)}
				<Tooltip text="Strategy applied">
				<span class="inline-block rounded-full px-1.5 py-0.5 font-mono text-[9px] {fwc.text}" style="background: color-mix(in srgb, currentColor 10%, transparent)" data-testid="collapsed-framework-badge">
					{frameworkApplied}
				</span>
				</Tooltip>
			{/if}
			{#if isValidateStep && overallScore !== undefined}
				<Tooltip text="Overall quality score">
				<span class="rounded-full bg-neon-green/15 px-1.5 py-0.5 font-mono text-[9px] font-bold text-neon-green" data-testid="collapsed-score">
					{formatScore(overallScore)}
				</span>
				</Tooltip>
			{/if}
			{#if durationDisplay}
				<span class="font-mono text-[9px] tabular-nums text-text-dim" data-testid="step-duration-{step.name}">
					{durationDisplay}
				</span>
			{/if}
		</div>
	{/if}
</div>
{/if}
