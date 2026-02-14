<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';
	import { fetchStats, type StatsResponse } from '$lib/api/client';
	import { formatScore, formatRate } from '$lib/utils/format';
	import Icon from './Icon.svelte';

	let { sidebarOpen = $bindable(true) }: { sidebarOpen: boolean } = $props();

	let statsOpen = $state(false);
	let stats: StatsResponse | null = $state(null);
	let loadingStats = $state(false);
	let statsFetchedAt = 0;

	async function toggleStats() {
		statsOpen = !statsOpen;
		if (statsOpen) {
			// Use cached stats if fetched within the last 60 seconds
			if (stats && Date.now() - statsFetchedAt < 60_000) return;
			loadingStats = true;
			stats = await fetchStats();
			statsFetchedAt = Date.now();
			loadingStats = false;
		}
	}
</script>

<header
	class="glass sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between border-b border-border-subtle px-5"
	data-testid="header"
>
	<div class="flex items-center gap-3">
		<button
			onclick={() => (sidebarOpen = !sidebarOpen)}
			class="flex h-8 w-8 items-center justify-center rounded-lg text-text-dim transition-[background-color,color] duration-200 hover:bg-bg-hover hover:text-neon-cyan"
			aria-label="Toggle sidebar"
			data-testid="sidebar-toggle"
		>
			{#if sidebarOpen}
				<Icon name="sidebar" size={16} />
			{:else}
				<Icon name="menu" size={16} />
			{/if}
		</button>

		<a href="/" class="flex items-center gap-2.5 no-underline">
			<!-- Forge icon -->
			<div class="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20">
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="url(#bolt-grad)" />
					<defs>
						<linearGradient id="bolt-grad" x1="3" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
							<stop stop-color="#00e5ff" />
							<stop offset="1" stop-color="#a855f7" />
						</linearGradient>
					</defs>
				</svg>
			</div>
			<span
				class="text-gradient-forge font-display text-lg font-bold leading-normal tracking-tight"
				data-testid="logo-text"
			>
				PromptForge
			</span>
		</a>
	</div>

	<div class="flex items-center gap-2">
		<button
			class="flex items-center gap-2 rounded-full border border-border-subtle bg-bg-card/50 px-3 py-1.5 text-xs transition-[border-color,background-color] duration-200 hover:border-neon-cyan/20 hover:bg-bg-hover"
			onclick={toggleStats}
			data-testid="stats-badge"
		>
			<div class="h-1.5 w-1.5 rounded-full bg-neon-green shadow-[0_0_6px_var(--color-neon-green)]"></div>
			<span class="font-mono font-semibold text-text-primary" data-testid="stats-count">{historyState.total}</span>
			<span class="text-text-dim">forged</span>
			<Icon name="chevron-down" size={10} class="text-text-dim transition-transform duration-200 {statsOpen ? 'rotate-180' : ''}" />
		</button>
	</div>
</header>

{#if statsOpen}
	<div
		class="glass border-b border-border-subtle py-2.5 animate-fade-in"
		data-testid="stats-panel"
	>
		<div class="mx-auto max-w-5xl px-6">
		{#if loadingStats}
			<div class="flex items-center justify-center py-2">
				<Icon name="spinner" size={14} class="animate-spin text-neon-cyan" />
			</div>
		{:else if stats}
			<div class="flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5">
				<!-- Primary stats -->
				<div class="flex items-baseline gap-1.5">
					<span class="font-mono text-sm font-bold text-neon-cyan">{formatScore(stats.average_overall_score)}</span>
					<span class="text-[10px] tracking-wider text-text-dim">OVERALL</span>
				</div>
				<div class="flex items-baseline gap-1.5">
					<span class="font-mono text-sm font-bold text-neon-purple">{formatRate(stats.improvement_rate)}</span>
					<span class="text-[10px] tracking-wider text-text-dim">IMPROVED</span>
				</div>
				<div class="flex items-baseline gap-1.5">
					<span class="font-mono text-sm font-bold text-neon-green">{stats.optimizations_today}</span>
					<span class="text-[10px] tracking-wider text-text-dim">TODAY</span>
				</div>
				<div class="flex items-baseline gap-1.5">
					<span class="truncate font-mono text-sm font-bold text-text-primary">{stats.most_common_task_type || '—'}</span>
					<span class="text-[10px] tracking-wider text-text-dim">TOP TASK</span>
				</div>

				<!-- Divider -->
				<div class="hidden h-3.5 w-px bg-border-subtle sm:block" aria-hidden="true"></div>

				<!-- Sub-scores -->
				<div class="flex items-baseline gap-1">
					<span class="font-mono text-xs font-semibold text-text-secondary">{formatScore(stats.average_clarity_score)}</span>
					<span class="text-[9px] tracking-wider text-text-dim">CLR</span>
				</div>
				<div class="flex items-baseline gap-1">
					<span class="font-mono text-xs font-semibold text-text-secondary">{formatScore(stats.average_specificity_score)}</span>
					<span class="text-[9px] tracking-wider text-text-dim">SPC</span>
				</div>
				<div class="flex items-baseline gap-1">
					<span class="font-mono text-xs font-semibold text-text-secondary">{formatScore(stats.average_structure_score)}</span>
					<span class="text-[9px] tracking-wider text-text-dim">STR</span>
				</div>
				<div class="flex items-baseline gap-1">
					<span class="font-mono text-xs font-semibold text-text-secondary">{formatScore(stats.average_faithfulness_score)}</span>
					<span class="text-[9px] tracking-wider text-text-dim">FTH</span>
				</div>
			</div>
		{:else}
			<div class="flex items-center justify-center py-2">
				<span class="text-xs text-text-dim">No stats available</span>
			</div>
		{/if}
		</div>
	</div>
{/if}
