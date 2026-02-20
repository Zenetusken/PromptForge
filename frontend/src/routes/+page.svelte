<script lang="ts">
	import { goto } from '$app/navigation';
	import PromptInput from '$lib/components/PromptInput.svelte';
	import PipelineProgress from '$lib/components/PipelineProgress.svelte';
	import ResultPanel from '$lib/components/ResultPanel.svelte';
	import StrategyInsights from '$lib/components/StrategyInsights.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { formatRelativeTime, formatExactTime, normalizeScore, formatScore, formatRate, getScoreBadgeClass, getScoreColorClass } from '$lib/utils/format';
	import { fetchStats } from '$lib/api/client';
	import type { OptimizeMetadata, StatsResponse } from '$lib/api/client';
	import { EntryTitle, Tooltip } from '$lib/components/ui';

	const QUICK_START_TEMPLATES = [
		{
			label: 'Code Review',
			icon: 'terminal' as const,
			color: 'cyan',
			prompt: 'Review this Python function for correctness, performance issues, and adherence to best practices. Suggest specific refactors with code examples and explain the reasoning behind each change.'
		},
		{
			label: 'Marketing Email',
			icon: 'edit' as const,
			color: 'purple',
			prompt: 'Write a compelling product launch email for a B2B SaaS audience. Include a subject line, preview text, hero section, three benefit-driven paragraphs, social proof, and a clear call-to-action.'
		},
		{
			label: 'Technical Docs',
			icon: 'layers' as const,
			color: 'green',
			prompt: 'Create comprehensive API documentation for a REST endpoint including description, authentication requirements, request/response schemas with examples, error codes, and rate limiting details.'
		},
		{
			label: 'Error Messages',
			icon: 'alert-circle' as const,
			color: 'red',
			prompt: 'Design user-friendly error messages for a web application covering validation failures, network errors, authentication issues, and permission denials. Each message should explain what went wrong and how to fix it.'
		}
	] as const;

	const COLOR_CLASSES = {
		cyan: {
			text: 'text-neon-cyan',
			bgLight: 'bg-neon-cyan/10',
			bgHover: 'hover:bg-neon-cyan/15',
			border: 'border-neon-cyan/20',
			shadow: 'hover:shadow-[0_0_20px_rgba(0,229,255,0.08)]'
		},
		purple: {
			text: 'text-neon-purple',
			bgLight: 'bg-neon-purple/10',
			bgHover: 'hover:bg-neon-purple/15',
			border: 'border-neon-purple/20',
			shadow: 'hover:shadow-[0_0_20px_rgba(168,85,247,0.08)]'
		},
		green: {
			text: 'text-neon-green',
			bgLight: 'bg-neon-green/10',
			bgHover: 'hover:bg-neon-green/15',
			border: 'border-neon-green/20',
			shadow: 'hover:shadow-[0_0_20px_rgba(34,255,136,0.08)]'
		},
		red: {
			text: 'text-neon-red',
			bgLight: 'bg-neon-red/10',
			bgHover: 'hover:bg-neon-red/15',
			border: 'border-neon-red/20',
			shadow: 'hover:shadow-[0_0_20px_rgba(255,51,102,0.08)]'
		}
	} as const;

	const SCORE_DIMENSIONS = [
		{ key: 'average_clarity_score' as const, label: 'CLR', fullLabel: 'Clarity', color: 'bg-neon-cyan/50', textColor: 'text-neon-cyan' },
		{ key: 'average_specificity_score' as const, label: 'SPC', fullLabel: 'Specificity', color: 'bg-neon-purple/50', textColor: 'text-neon-purple' },
		{ key: 'average_structure_score' as const, label: 'STR', fullLabel: 'Structure', color: 'bg-neon-green/50', textColor: 'text-neon-green' },
		{ key: 'average_faithfulness_score' as const, label: 'FTH', fullLabel: 'Faithfulness', color: 'bg-neon-yellow/50', textColor: 'text-neon-yellow' },
	] as const;

	// Clear stale optimization state when navigating to home
	// (e.g., after viewing a detail page via logo click)
	if (!optimizationState.isRunning) {
		optimizationState.result = null;
		optimizationState.currentRun = null;
		optimizationState.error = null;
	}

	let stats = $state<StatsResponse | null>(null);
	let lastStatsTotal = $state<number | null>(null);

	$effect(() => {
		if (historyState.hasLoaded && historyState.total > 0) {
			if (!stats || lastStatsTotal !== historyState.total) {
				lastStatsTotal = historyState.total;
				fetchStats().then((res) => { stats = res; });
			}
		}
	});

	// Static lookup so all class strings are visible to Tailwind's scanner
	const SCORE_CARD_STYLES: Record<string, { text: string; border: string; shadow: string }> = {
		'neon-green': { text: 'text-neon-green', border: 'border-l-neon-green', shadow: 'hover:shadow-[inset_0_0_20px_rgba(34,255,136,0.04)]' },
		'neon-yellow': { text: 'text-neon-yellow', border: 'border-l-neon-yellow', shadow: 'hover:shadow-[inset_0_0_20px_rgba(251,191,36,0.04)]' },
		'neon-red': { text: 'text-neon-red', border: 'border-l-neon-red', shadow: 'hover:shadow-[inset_0_0_20px_rgba(255,51,102,0.04)]' },
	};

	const statsCards = $derived.by(() => {
		if (!stats) return [];
		const scoreStyle = SCORE_CARD_STYLES[getScoreColorClass(stats.average_overall_score)];
		return [
			{
				label: 'Total Forged',
				description: 'Total prompt optimizations performed',
				value: stats.total_optimizations,
				labelColor: 'text-neon-cyan',
				valueColor: 'text-neon-cyan',
				border: 'border-l-neon-cyan',
				shadow: 'hover:shadow-[inset_0_0_20px_rgba(0,229,255,0.04)]',
			},
			{
				label: 'Avg Score',
				description: 'Weighted average quality score (1\u2013100)',
				value: normalizeScore(stats.average_overall_score) ?? '—',
				labelColor: scoreStyle.text,
				valueColor: scoreStyle.text,
				border: scoreStyle.border,
				shadow: scoreStyle.shadow,
			},
			{
				label: 'Improved',
				description: 'Percentage scoring higher than the original',
				value: formatRate(stats.improvement_rate),
				labelColor: 'text-neon-green',
				valueColor: 'text-neon-green',
				border: 'border-l-neon-green',
				shadow: 'hover:shadow-[inset_0_0_20px_rgba(34,255,136,0.04)]',
			},
			{
				label: 'Today',
				description: 'Optimizations completed today',
				value: stats.optimizations_today,
				labelColor: 'text-neon-purple',
				valueColor: 'text-neon-purple',
				border: 'border-l-neon-purple',
				shadow: 'hover:shadow-[inset_0_0_20px_rgba(168,85,247,0.04)]',
			},
		];
	});

	function handleOptimize(prompt: string, metadata?: OptimizeMetadata) {
		promptState.set(prompt);
		optimizationState.startOptimization(prompt, metadata);
	}

	function handleCancel() {
		optimizationState.cancel();
		optimizationState.currentRun = null;
		toastState.show('Optimization cancelled', 'info');
	}

	function handleRetry() {
		if (promptState.text) {
			optimizationState.error = null;
			optimizationState.startOptimization(promptState.text);
		}
	}

	function handleStrategySelect(strategy: string) {
		promptState.strategy = strategy;
		// Defer scroll/focus until after Svelte processes the strategy $effect
		queueMicrotask(() => {
			const textarea = document.querySelector('[data-testid="prompt-textarea"]') as HTMLTextAreaElement;
			textarea?.scrollIntoView({ behavior: 'smooth', block: 'center' });
			textarea?.focus();
		});
	}

	// Rate limit retry countdown
	let retryCountdown = $state(0);
	let retryInterval: ReturnType<typeof setInterval> | null = null;

	$effect(() => {
		const retryAfter = optimizationState.retryAfter;
		if (retryInterval) {
			clearInterval(retryInterval);
			retryInterval = null;
		}
		if (retryAfter && retryAfter > 0) {
			retryCountdown = retryAfter;
			retryInterval = setInterval(() => {
				retryCountdown--;
				if (retryCountdown <= 0 && retryInterval) {
					clearInterval(retryInterval);
					retryInterval = null;
				}
			}, 1000);
		} else {
			retryCountdown = 0;
		}
		return () => {
			if (retryInterval) {
				clearInterval(retryInterval);
				retryInterval = null;
			}
		};
	});
</script>

<div class="flex flex-col gap-4">
	<PromptInput onsubmit={handleOptimize} oncancel={handleCancel} disabled={optimizationState.isRunning} />

	<!-- Template cards (new users) or recent history (returning users) -->
	{#if !optimizationState.currentRun && !optimizationState.result && !optimizationState.error && historyState.hasLoaded}
		{#if historyState.total === 0}
			<div class="mt-2">
				<p class="section-heading-dim mb-3 px-1">Try a template</p>
				<div class="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
					{#each QUICK_START_TEMPLATES as template, i}
						{@const colors = COLOR_CLASSES[template.color]}
						<button
							type="button"
							onclick={() => promptState.set(template.prompt)}
							class="group flex flex-col items-center gap-2.5 rounded-xl border {colors.border} bg-bg-card/50 p-4 text-center transition-all duration-200 {colors.bgHover} {colors.shadow} hover:border-opacity-40 animate-fade-in"
							style="animation-delay: {200 + i * 75}ms; animation-fill-mode: backwards;"
						>
							<div class="flex h-9 w-9 items-center justify-center rounded-full {colors.bgLight} transition-transform duration-200 group-hover:scale-110">
								<Icon name={template.icon} size={16} class={colors.text} />
							</div>
							<span class="text-xs font-medium text-text-secondary group-hover:text-text-primary transition-colors">{template.label}</span>
						</button>
					{/each}
				</div>
			</div>
		{:else if historyState.items.length > 0}
			<div class="mt-2">
				<p class="section-heading-dim mb-3 px-1">Recent</p>
				<div class="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
					{#each historyState.items.slice(0, 3) as entry, i}
						{@const score = normalizeScore(entry.overall_score)}
						{@const entryArchived = entry.project_status === 'archived'}
						<button
							type="button"
							onclick={() => goto(`/optimize/${entry.id}`)}
							class="card-top-glow group flex flex-col gap-2 rounded-xl border border-border-subtle bg-bg-card/50 p-3.5 text-left transition-all duration-200 hover:bg-bg-hover hover:border-neon-cyan/15 hover:shadow-[0_0_20px_rgba(0,229,255,0.06)] animate-fade-in"
							style="animation-delay: {200 + i * 75}ms; animation-fill-mode: backwards;"
						>
							<p class="text-sm font-medium text-text-secondary group-hover:text-text-primary transition-colors line-clamp-2 leading-snug">
								<EntryTitle title={entry.title} maxLength={80} />
							</p>
							<div class="h-px w-full bg-gradient-to-r from-transparent via-border-glow to-transparent"></div>
							<div class="flex items-center gap-2 mt-auto">
								{#if score !== null}
									<Tooltip text="Overall score">
									<span class="score-circle {getScoreBadgeClass(entry.overall_score)}">
										{score}
									</span>
									</Tooltip>
								{/if}
								{#if entry.framework_applied}
									<Tooltip text="Strategy: {entry.framework_applied}">
									<span class="rounded-full bg-neon-purple/8 px-1.5 py-0.5 font-mono text-[10px] text-neon-purple">{entry.framework_applied}</span>
									</Tooltip>
								{/if}
								{#if entry.project && entryArchived}
									<span class="text-[10px] text-neon-yellow/50">
										{entry.project} (archived)
									</span>
								{/if}
								<Tooltip text={formatExactTime(entry.created_at)} class="ml-auto"><span class="text-[10px] text-text-dim">{formatRelativeTime(entry.created_at)}</span></Tooltip>
							</div>
						</button>
					{/each}
				</div>

				{#if stats}
					<div class="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
						{#each statsCards as card, i}
							<Tooltip text={card.description}>
								<div
									class="w-full rounded-xl border border-border-subtle border-l-2 {card.border} bg-bg-card/50 p-3 transition-all duration-200 hover:bg-bg-hover/30 {card.shadow} animate-fade-in"
									style="animation-delay: {425 + i * 50}ms; animation-fill-mode: backwards;"
								>
									<p class="text-[10px] font-medium uppercase tracking-wider {card.labelColor}">{card.label}</p>
									<p class="mt-1 font-mono text-xl font-semibold {card.valueColor}">{card.value}</p>
								</div>
							</Tooltip>
						{/each}
					</div>

					{#if stats.average_clarity_score != null || stats.most_common_task_type}
						<div class="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 animate-fade-in" style="animation-delay: 475ms; animation-fill-mode: backwards;">
							{#each SCORE_DIMENSIONS as dim}
								{@const rawScore = stats[dim.key]}
								<Tooltip text="{dim.fullLabel}: {formatScore(rawScore)}/10">
									<div class="flex items-center gap-1.5">
										<span class="font-mono text-xs font-semibold {dim.textColor}">{formatScore(rawScore)}</span>
										<span class="text-[9px] tracking-wider text-text-dim">{dim.label}</span>
										<div class="h-1 w-8 overflow-hidden rounded-full bg-bg-hover">
											<div class="{dim.color} h-full rounded-full transition-all" style="width: {rawScore != null ? rawScore * 100 : 0}%"></div>
										</div>
									</div>
								</Tooltip>
							{/each}
							{#if stats.most_common_task_type}
								<div class="hidden h-3.5 w-px bg-border-subtle sm:block" aria-hidden="true"></div>
								<span class="rounded-full bg-neon-cyan/8 px-2 py-0.5 font-mono text-xs font-semibold text-neon-cyan">{stats.most_common_task_type}</span>
								<span class="text-[9px] tracking-wider text-text-dim">TOP TASK</span>
							{/if}
						</div>
					{/if}

					<StrategyInsights {stats} lastPrompt={promptState.text} onStrategySelect={handleStrategySelect} />
				{/if}
			</div>
		{/if}
	{/if}

	{#if optimizationState.error}
		<div class="animate-fade-in rounded-xl border border-neon-red/20 bg-neon-red/5 p-4" role="alert" data-testid="error-display">
			<div class="flex items-center gap-3">
				<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-neon-red/10">
					<Icon name="alert-circle" size={16} class="text-neon-red" />
				</div>
				<div class="flex-1">
					<p class="text-sm font-medium text-neon-red">
						{optimizationState.errorType === 'rate_limit' ? 'Rate limit reached' : 'Optimization failed'}
					</p>
					<p class="mt-0.5 text-sm text-text-secondary">{optimizationState.error}</p>
					{#if optimizationState.errorType === 'rate_limit' && retryCountdown > 0}
						<p class="mt-1 font-mono text-xs text-neon-yellow" data-testid="retry-countdown">
							Try again in {retryCountdown}s
						</p>
					{/if}
				</div>
				{#if promptState.text}
					<button
						onclick={handleRetry}
						disabled={optimizationState.errorType === 'rate_limit' && retryCountdown > 0}
						class="shrink-0 rounded-lg border border-neon-cyan/20 bg-neon-cyan/5 px-4 py-1.5 font-mono text-xs text-neon-cyan transition-[background-color] hover:bg-neon-cyan/10 disabled:opacity-40 disabled:cursor-not-allowed"
						data-testid="retry-button"
					>
						Retry
					</button>
				{/if}
			</div>
		</div>
	{/if}

	{#if optimizationState.currentRun}
		<PipelineProgress steps={optimizationState.currentRun.steps} />
	{/if}

	{#if optimizationState.result}
		<ResultPanel result={optimizationState.result} />
	{/if}
</div>
