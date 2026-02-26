<script lang="ts">
	import { statsState } from '$lib/stores/stats.svelte';
	import { normalizeScore } from '$lib/utils/format';
	import { STRATEGY_LABELS, STRATEGY_COLOR_META, type StrategyName } from '$lib/utils/strategies';
	import { WindowTabStrip, EmptyState } from './ui';

	const label = (s: string) => (STRATEGY_LABELS as Record<string, string>)[s] ?? s;

	let activeView: 'heatmap' | 'winrates' | 'combos' = $state('heatmap');

	let stats = $derived(statsState.activeStats);
	let scoreMatrix = $derived(stats?.score_matrix ?? null);
	let winRates = $derived(stats?.win_rates ?? null);
	let comboEffectiveness = $derived(stats?.combo_effectiveness ?? null);
	let stratDist = $derived(stats?.strategy_distribution ?? {});
	let scoreByStrategy = $derived(stats?.score_by_strategy ?? {});
	let confidenceByStrategy = $derived(stats?.confidence_by_strategy ?? {});

	// Extract unique strategies and task types from score matrix
	let strategies = $derived.by(() => {
		if (!scoreMatrix) return Object.keys(scoreByStrategy).sort();
		return Object.keys(scoreMatrix).sort();
	});

	let taskTypes = $derived.by(() => {
		if (!scoreMatrix) return [];
		const types = new Set<string>();
		for (const strat of Object.values(scoreMatrix)) {
			for (const tt of Object.keys(strat as Record<string, unknown>)) {
				types.add(tt);
			}
		}
		return [...types].sort();
	});

	function getHeatColor(score: number | null | undefined): string {
		if (score == null) return 'bg-bg-input';
		// Normalize 0-1 to color
		const n = score;
		if (n >= 0.8) return 'bg-neon-green/30';
		if (n >= 0.6) return 'bg-neon-cyan/20';
		if (n >= 0.4) return 'bg-neon-yellow/20';
		if (n >= 0.2) return 'bg-neon-orange/20';
		return 'bg-neon-red/20';
	}

	function getCellScore(strat: string, taskType: string): number | null {
		if (!scoreMatrix || !scoreMatrix[strat]) return null;
		const entry = (scoreMatrix[strat] as unknown as Record<string, { avg_score: number | null; count: number }>)[taskType];
		if (!entry || entry.avg_score == null) return null;
		return entry.avg_score;
	}
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<WindowTabStrip
		tabs={[
			{ id: 'heatmap', label: 'Score Heatmap' },
			{ id: 'winrates', label: 'Win Rates' },
			{ id: 'combos', label: 'Combo Analysis' },
		]}
		activeTab={activeView}
		onTabChange={(id) => activeView = id as typeof activeView}
	/>

	<div class="flex-1 overflow-y-auto p-3">
		{#if !stats}
			<EmptyState icon="layers" message="No analytics data yet. Run some forges first." />
		{:else if activeView === 'heatmap'}
			<!-- Strategy x Task Type score heatmap -->
			{#if strategies.length === 0 || taskTypes.length === 0}
				<p class="text-xs text-text-dim">Not enough data for heatmap. Run forges with different strategies and prompt types.</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="text-[10px] border-collapse">
						<thead>
							<tr>
								<th class="px-2 py-1 text-left text-text-dim font-normal">Strategy</th>
								{#each taskTypes as tt}
									<th class="px-2 py-1 text-center text-text-dim font-normal whitespace-nowrap">{tt}</th>
								{/each}
								<th class="px-2 py-1 text-center text-text-dim font-normal">Avg</th>
							</tr>
						</thead>
						<tbody>
							{#each strategies as strat}
								<tr class="border-t border-neon-cyan/5">
									<td class="px-2 py-1.5 text-text-secondary whitespace-nowrap">{label(strat)}</td>
									{#each taskTypes as tt}
										{@const score = getCellScore(strat, tt)}
										<td class="px-2 py-1.5 text-center">
											<span class="inline-flex items-center justify-center w-8 h-5 {getHeatColor(score)} text-[9px] tabular-nums">
												{score != null ? normalizeScore(score) : '-'}
											</span>
										</td>
									{/each}
									<td class="px-2 py-1.5 text-center text-neon-cyan tabular-nums">
										{scoreByStrategy[strat] != null ? normalizeScore(scoreByStrategy[strat]) : '-'}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

		{:else if activeView === 'winrates'}
			<!-- Win rates: which strategy wins most for each task type -->
			<div class="space-y-4">
				<h3 class="section-heading">Strategy Performance</h3>
				<div class="space-y-2">
					{#each strategies as strat}
						{@const count = stratDist[strat] ?? 0}
						{@const score = scoreByStrategy[strat] ?? 0}
						{@const confidence = confidenceByStrategy?.[strat] ?? 0}
						{@const maxCount = Math.max(...Object.values(stratDist), 1)}
						<div class="flex items-center gap-3">
							<span class="text-[11px] text-text-secondary w-32 truncate">{label(strat)}</span>
							<div class="flex-1 h-4 bg-bg-input relative">
								<div
									class="h-full bg-neon-cyan/20 transition-all"
									style="width: {(count / maxCount) * 100}%"
								></div>
								<span class="absolute inset-0 flex items-center px-2 text-[9px] tabular-nums text-text-primary">
									{count} uses
								</span>
							</div>
							<span class="text-[10px] text-neon-cyan tabular-nums w-10 text-right">{normalizeScore(score)}</span>
							<span class="text-[9px] text-text-dim tabular-nums w-10 text-right">{Math.round(confidence * 100)}%</span>
						</div>
					{/each}
				</div>

				{#if winRates && Object.keys(winRates).length > 0}
					<h3 class="section-heading pt-4">Best Strategy by Task Type</h3>
					<div class="space-y-1">
						{#each Object.entries(winRates) as [taskType, data]}
							<div class="flex items-center justify-between">
								<span class="text-[11px] text-text-secondary">{taskType}</span>
								<span class="text-[11px] text-neon-green">{(data as any).strategy ?? '-'}</span>
							</div>
						{/each}
					</div>
				{/if}
			</div>

		{:else if activeView === 'combos'}
			<!-- Primary + secondary strategy combo effectiveness -->
			{#if comboEffectiveness && Object.keys(comboEffectiveness).length > 0}
				<div class="space-y-3">
					<h3 class="section-heading">Strategy Combos</h3>
					{#each Object.entries(comboEffectiveness) as [primary, secondaries]}
						<div class="space-y-1">
							<span class="text-[11px] text-text-primary">{label(primary)}</span>
							{#each Object.entries(secondaries as unknown as Record<string, { count: number; avg_score: number | null }>) as [secondary, data]}
								<div class="flex items-center gap-2 pl-4">
									<span class="text-[10px] text-text-dim">+ {label(secondary)}</span>
									<span class="text-[10px] text-neon-cyan tabular-nums ml-auto">
										{data.avg_score != null ? normalizeScore(data.avg_score) : '-'}
									</span>
									<span class="text-[9px] text-text-dim tabular-nums">
										({data.count ?? 0} runs)
									</span>
								</div>
							{/each}
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-xs text-text-dim">No combo data yet. Try forging with secondary frameworks to see combo effectiveness.</p>
			{/if}
		{/if}
	</div>
</div>
