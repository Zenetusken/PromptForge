<script lang="ts">
	import type { StatsResponse } from '$lib/api/client';
	import { normalizeScore } from '$lib/utils/format';
	import {
		ALL_STRATEGIES,
		STRATEGY_LABELS,
		STRATEGY_DESCRIPTIONS,
		STRATEGY_DETAILS,
		STRATEGY_FIXED_COLORS,
	} from '$lib/utils/strategies';
	import type { StrategyName } from '$lib/utils/strategies';
	import { Tooltip } from './ui';

	let {
		stats,
		lastPrompt = '',
		onStrategySelect,
	}: {
		stats: StatsResponse;
		lastPrompt?: string;
		onStrategySelect?: (strategy: string) => void;
	} = $props();

	let expandedStrategy: string | null = $state(null);

	const distribution = $derived(stats.strategy_distribution ?? {});
	const scoreByStrategy = $derived(stats.score_by_strategy ?? {});
	const taskTypesByStrategy = $derived(stats.task_types_by_strategy ?? {});
	const total = $derived(Object.values(distribution).reduce((sum, c) => sum + c, 0));

	// Static Tailwind-safe class lookups keyed by bar color.
	// All 4 neon colors are covered — STRATEGY_FIXED_COLORS guarantees the key exists.
	const BORDER_COLORS: Record<string, string> = {
		'bg-neon-cyan': 'border-l-neon-cyan',
		'bg-neon-purple': 'border-l-neon-purple',
		'bg-neon-green': 'border-l-neon-green',
		'bg-neon-red': 'border-l-neon-red',
	};
	const BTN_BG_COLORS: Record<string, string> = {
		'bg-neon-cyan': 'bg-neon-cyan/10 hover:bg-neon-cyan/20',
		'bg-neon-purple': 'bg-neon-purple/10 hover:bg-neon-purple/20',
		'bg-neon-green': 'bg-neon-green/10 hover:bg-neon-green/20',
		'bg-neon-red': 'bg-neon-red/10 hover:bg-neon-red/20',
	};

	interface StrategyEntry {
		name: StrategyName;
		label: string;
		count: number;
		percentage: number;
		score: number | null;
		barColor: string;
		textColor: string;
	}

	const usedStrategies: StrategyEntry[] = $derived.by(() => {
		const entries: StrategyEntry[] = [];
		const sorted = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
		for (const [name, count] of sorted) {
			const key = name as StrategyName;
			const colors = STRATEGY_FIXED_COLORS[key] ?? { bar: 'bg-neon-cyan', text: 'text-neon-cyan' };
			entries.push({
				name: key,
				label: STRATEGY_LABELS[key] ?? name,
				count,
				percentage: total > 0 ? Math.round((count / total) * 100) : 0,
				score: scoreByStrategy[name] ?? null,
				barColor: colors.bar,
				textColor: colors.text,
			});
		}
		return entries;
	});

	const untriedStrategies = $derived(
		ALL_STRATEGIES.filter((s) => !(s in distribution)).map((s) => ({
			name: s,
			label: STRATEGY_LABELS[s],
			motivation: STRATEGY_DETAILS[s]?.motivation ?? '',
		}))
	);

	const topPerformer = $derived.by(() => {
		let best: StrategyEntry | null = null;
		for (const entry of usedStrategies) {
			if (entry.count >= 2 && entry.score !== null) {
				if (!best || (best.score !== null && entry.score > best.score)) {
					best = entry;
				}
			}
		}
		return best;
	});

	/** Data-driven recommendation: score untried strategies by overlap with user's task types. */
	const recommendation = $derived.by(() => {
		if (untriedStrategies.length === 0) return null;

		// Collect user's global task type frequency
		const taskFreq: Record<string, number> = {};
		for (const tasks of Object.values(taskTypesByStrategy)) {
			for (const [taskType, count] of Object.entries(tasks)) {
				taskFreq[taskType] = (taskFreq[taskType] ?? 0) + count;
			}
		}
		if (Object.keys(taskFreq).length === 0) {
			// No task type data — recommend the first untried
			const first = untriedStrategies[0];
			return { name: first.name, label: first.label, motivation: first.motivation, score: 0 };
		}

		let best: { name: StrategyName; label: string; motivation: string; score: number } | null = null;
		for (const s of untriedStrategies) {
			const details = STRATEGY_DETAILS[s.name];
			if (!details) continue;
			let score = 0;
			for (const taskType of details.bestFor) {
				score += taskFreq[taskType] ?? 0;
			}
			if (!best || score > best.score) {
				best = { name: s.name, label: s.label, motivation: s.motivation, score };
			}
		}
		return best;
	});

	function handleSelect(strategy: string) {
		onStrategySelect?.(strategy);
	}

	function toggleExpanded(name: string) {
		expandedStrategy = expandedStrategy === name ? null : name;
	}
</script>

{#if usedStrategies.length > 0}
	<div class="mt-3 animate-fade-in" style="animation-delay: 500ms; animation-fill-mode: backwards;">
		<!-- Recommendation card -->
		{#if recommendation}
			<div class="mb-3 rounded-lg border border-neon-yellow/20 bg-neon-yellow/5 p-2.5">
				<div class="flex items-start gap-2">
					<span class="mt-0.5 text-sm text-neon-yellow">&#9733;</span>
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-1.5">
							<span class="text-[10px] font-semibold uppercase tracking-wider text-neon-yellow/70">Recommended</span>
							<span class="text-xs font-semibold text-text-primary">{recommendation.label}</span>
						</div>
						<p class="mt-0.5 text-[10px] leading-relaxed text-text-dim">{recommendation.motivation}</p>
						<div class="mt-1.5 flex flex-wrap gap-1.5">
							<button
								onclick={() => handleSelect(recommendation!.name)}
								class="rounded-full bg-neon-yellow/10 px-2.5 py-0.5 text-[10px] font-semibold text-neon-yellow transition-colors hover:bg-neon-yellow/20"
							>
								Try it
							</button>
							{#if lastPrompt}
								<button
									onclick={() => handleSelect(recommendation!.name)}
									class="rounded-full bg-neon-yellow/5 px-2.5 py-0.5 text-[10px] font-medium text-neon-yellow/70 transition-colors hover:bg-neon-yellow/15"
								>
									Re-forge last prompt
								</button>
							{/if}
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Strategy bars -->
		<div class="space-y-1">
			{#each usedStrategies as entry}
				<div>
					<button
						onclick={() => toggleExpanded(entry.name)}
						class="group flex w-full items-center gap-2 rounded px-1 py-0.5 text-left transition-colors hover:bg-bg-hover/30"
					>
						<span class="w-[110px] shrink-0 truncate text-right text-[10px] font-medium {entry.textColor}">
							{entry.label}
							{#if topPerformer?.name === entry.name}
								<Tooltip text="Top performer (highest avg score with 2+ uses)">
									<span class="ml-0.5 text-neon-yellow">&#9733;</span>
								</Tooltip>
							{/if}
						</span>
						<div class="relative h-3 flex-1 overflow-hidden rounded-full bg-bg-primary/40">
							<div
								class="{entry.barColor} opacity-70 h-full rounded-full transition-all duration-500"
								style="width: {entry.percentage}%"
							></div>
						</div>
						<span class="w-7 shrink-0 text-right font-mono text-[10px] text-text-dim">{entry.count}</span>
						<Tooltip text={entry.score !== null ? `Average score for ${entry.label}` : `No score data for ${entry.label}`}>
							<span class="w-7 shrink-0 rounded bg-bg-hover/50 text-center font-mono text-[10px] font-semibold {entry.score !== null ? 'text-text-secondary' : 'text-text-dim/30'}">
								{entry.score !== null ? normalizeScore(entry.score) : '—'}
							</span>
						</Tooltip>
						<span class="w-3 shrink-0 text-center text-[10px] text-text-dim/40 transition-transform duration-200 {expandedStrategy === entry.name ? 'rotate-90' : ''}">&#9656;</span>
					</button>

					<!-- Expanded detail panel -->
					{#if expandedStrategy === entry.name}
						<div class="ml-[118px] mt-1 mb-1.5 rounded-lg border-l-2 {BORDER_COLORS[entry.barColor]} bg-bg-secondary/30 p-2.5 animate-fade-in">
							<p class="text-[10px] leading-relaxed text-text-dim">{STRATEGY_DESCRIPTIONS[entry.name] ?? ''}</p>

							{#if taskTypesByStrategy[entry.name]}
								<div class="mt-1.5 flex flex-wrap gap-1">
									{#each Object.entries(taskTypesByStrategy[entry.name]) as [taskType, count]}
										<span class="rounded-full bg-bg-hover/60 px-1.5 py-0.5 text-[9px] font-medium text-text-secondary">
											{taskType} <span class="text-text-dim">({count})</span>
										</span>
									{/each}
								</div>
							{/if}

							<div class="mt-2 flex flex-wrap gap-1.5">
								<button
									onclick={() => handleSelect(entry.name)}
									class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold {entry.textColor} {BTN_BG_COLORS[entry.barColor]} transition-colors"
								>
									Try this strategy
								</button>
								{#if lastPrompt}
									<button
										onclick={() => handleSelect(entry.name)}
										class="rounded-full bg-bg-hover/40 px-2.5 py-0.5 text-[10px] font-medium text-text-secondary transition-colors hover:bg-bg-hover/60"
									>
										Re-forge last prompt
									</button>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Untried strategies -->
		{#if untriedStrategies.length > 0}
			<div class="mt-2.5 flex flex-wrap items-center gap-1.5">
				<span class="text-[9px] font-semibold uppercase tracking-wider text-text-dim/50">Untried</span>
				{#each untriedStrategies as strategy}
					<Tooltip text={strategy.motivation || `Try overriding with ${strategy.label} in the Strategy section`}>
						<button
							onclick={() => handleSelect(strategy.name)}
							class="rounded-full bg-neon-yellow/8 px-2 py-0.5 text-[10px] font-medium text-neon-yellow/70 transition-colors hover:bg-neon-yellow/15 hover:text-neon-yellow"
						>
							{strategy.label}
						</button>
					</Tooltip>
				{/each}
			</div>
		{/if}
	</div>
{/if}
