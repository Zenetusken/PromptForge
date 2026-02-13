<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';
	import { fetchStats, type StatsResponse } from '$lib/api/client';

	let { sidebarOpen = $bindable(true) }: { sidebarOpen: boolean } = $props();

	let statsOpen = $state(false);
	let stats: StatsResponse | null = $state(null);
	let loadingStats = $state(false);

	async function toggleStats() {
		statsOpen = !statsOpen;
		if (statsOpen) {
			loadingStats = true;
			stats = await fetchStats();
			loadingStats = false;
		}
	}

	function formatScore(value: number | null): string {
		if (value === null || value === undefined) return '—';
		const pct = value <= 1 ? value * 100 : value;
		return Math.round(pct).toString();
	}

	function formatRate(value: number | null): string {
		if (value === null || value === undefined) return '—';
		return `${Math.round(value * 100)}%`;
	}
</script>

<header
	class="flex h-14 shrink-0 items-center justify-between border-b border-text-dim/20 bg-bg-secondary px-6"
	data-testid="header"
>
	<div class="flex items-center gap-3">
		<button
			onclick={() => (sidebarOpen = !sidebarOpen)}
			class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-card hover:text-neon-cyan"
			aria-label="Toggle sidebar"
			data-testid="sidebar-toggle"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="18"
				height="18"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<line x1="3" y1="6" x2="21" y2="6" />
				<line x1="3" y1="12" x2="21" y2="12" />
				<line x1="3" y1="18" x2="21" y2="18" />
			</svg>
		</button>

		<div class="flex items-center gap-2">
			<span
				class="font-mono text-xl font-bold tracking-tight"
				style="background: linear-gradient(135deg, var(--color-neon-cyan), var(--color-neon-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;"
				data-testid="logo-text"
			>
				PromptForge
			</span>
			<span class="rounded-full bg-neon-cyan/10 px-2 py-0.5 font-mono text-xs text-neon-cyan">
				v1.0
			</span>
		</div>
	</div>

	<div class="flex items-center gap-3">
		<button
			class="flex items-center gap-1.5 rounded-full border border-neon-cyan/30 bg-neon-cyan/10 px-3 py-1 text-sm transition-colors hover:bg-neon-cyan/20"
			onclick={toggleStats}
			data-testid="stats-badge"
		>
			<div class="h-2 w-2 rounded-full bg-neon-green shadow-[0_0_6px_var(--color-neon-green)]"></div>
			<span class="font-mono font-semibold text-neon-cyan" data-testid="stats-count">{historyState.total}</span>
			<span class="text-text-secondary">forged</span>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="12"
				height="12"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				class="text-text-dim transition-transform {statsOpen ? 'rotate-180' : ''}"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
		</button>
	</div>
</header>

{#if statsOpen}
	<div
		class="border-b border-text-dim/20 bg-bg-secondary px-6 py-4 animate-fade-in"
		data-testid="stats-panel"
	>
		{#if loadingStats}
			<div class="flex items-center justify-center py-4">
				<span class="font-mono text-xs text-text-dim">Loading stats...</span>
			</div>
		{:else if stats}
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
				<div class="rounded-lg border border-neon-cyan/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-neon-cyan">{formatScore(stats.average_overall_score)}</div>
					<div class="font-mono text-[10px] text-text-dim">Overall</div>
				</div>
				<div class="rounded-lg border border-neon-purple/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-neon-purple">{formatRate(stats.improvement_rate)}</div>
					<div class="font-mono text-[10px] text-text-dim">Improved</div>
				</div>
				<div class="rounded-lg border border-neon-green/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-neon-green">{stats.optimizations_today}</div>
					<div class="font-mono text-[10px] text-text-dim">Today</div>
				</div>
				<div class="rounded-lg border border-text-dim/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-text-primary">{stats.most_common_task_type || '—'}</div>
					<div class="font-mono text-[10px] text-text-dim">Top Task</div>
				</div>
				<div class="rounded-lg border border-text-dim/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-text-secondary">{formatScore(stats.average_clarity_score)}</div>
					<div class="font-mono text-[10px] text-text-dim">Clarity</div>
				</div>
				<div class="rounded-lg border border-text-dim/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-text-secondary">{formatScore(stats.average_specificity_score)}</div>
					<div class="font-mono text-[10px] text-text-dim">Specificity</div>
				</div>
				<div class="rounded-lg border border-text-dim/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-text-secondary">{formatScore(stats.average_structure_score)}</div>
					<div class="font-mono text-[10px] text-text-dim">Structure</div>
				</div>
				<div class="rounded-lg border border-text-dim/20 bg-bg-card p-3 text-center">
					<div class="font-mono text-lg font-bold text-text-secondary">{formatScore(stats.average_faithfulness_score)}</div>
					<div class="font-mono text-[10px] text-text-dim">Faithfulness</div>
				</div>
			</div>
		{:else}
			<div class="flex items-center justify-center py-4">
				<span class="font-mono text-xs text-text-dim">No stats available</span>
			</div>
		{/if}
	</div>
{/if}
