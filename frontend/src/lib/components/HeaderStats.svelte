<script lang="ts">
	import { statsState } from "$lib/stores/stats.svelte";
	import {
		normalizeScore,
		formatScore,
		formatRate,
		getScoreColorClass,
	} from "$lib/utils/format";
	import { Tooltip, MetaBadge } from "./ui";

	const SCORE_DIMENSIONS = [
		{
			key: "average_clarity_score" as const,
			label: "CLR",
			fullLabel: "Clarity",
			barColor: "bg-neon-cyan/50",
			textColor: "text-neon-cyan",
		},
		{
			key: "average_specificity_score" as const,
			label: "SPC",
			fullLabel: "Specificity",
			barColor: "bg-neon-purple/50",
			textColor: "text-neon-purple",
		},
		{
			key: "average_structure_score" as const,
			label: "STR",
			fullLabel: "Structure",
			barColor: "bg-neon-green/50",
			textColor: "text-neon-green",
		},
		{
			key: "average_faithfulness_score" as const,
			label: "FTH",
			fullLabel: "Faithfulness",
			barColor: "bg-neon-yellow/50",
			textColor: "text-neon-yellow",
		},
	] as const;

	const SCORE_COLOR_TEXT: Record<string, string> = {
		"neon-green": "text-neon-green",
		"neon-yellow": "text-neon-yellow",
		"neon-red": "text-neon-red",
	};

	let { sidebarOpen = true }: { sidebarOpen?: boolean } = $props();

	let stats = $derived(statsState.activeStats);
	let scopeLabel = $derived(
		statsState.activeProject ? ` (in ${statsState.activeProject})` : "",
	);

	let avgScoreColor = $derived.by(() => {
		if (!stats) return "text-text-dim";
		return (
			SCORE_COLOR_TEXT[getScoreColorClass(stats.average_overall_score)] ??
			"text-neon-yellow"
		);
	});

	let taskType = $derived(stats?.most_common_task_type);
	let taskLabel = $derived(taskType?.toUpperCase() ?? "");
</script>

{#if stats}
	<div
		class="header-hud-root animate-fade-in"
		style="animation-delay: 50ms; animation-fill-mode: backwards;"
	>
		<div class="header-stats-grid">
			<!-- Col 1: Left wing — all summary stats -->
			<div
				class="hidden sm:flex items-center justify-self-start min-w-0 overflow-hidden {sidebarOpen
					? ''
					: 'pl-6'}"
			>
				<Tooltip
					text="Total forges performed (includes re-forges){scopeLabel}"
				>
					<div class="header-stat">
						<span class="header-stat-value text-neon-cyan"
							>{stats.total_optimizations}</span
						>
						<span class="header-stat-label">FORGED</span>
					</div>
				</Tooltip>

				<div class="header-divider" aria-hidden="true"></div>

				<Tooltip
					text="Weighted average quality score (1-100){scopeLabel}"
				>
					<div class="header-stat">
						<span class="header-stat-value {avgScoreColor}"
							>{normalizeScore(stats.average_overall_score) ??
								"—"}</span
						>
						<span class="header-stat-label">AVG</span>
					</div>
				</Tooltip>

				<!-- IMP, PROJ, TODAY — show at md: -->
				<div
					class="header-divider hidden md:block"
					aria-hidden="true"
				></div>

				<div class="hidden md:flex items-center">
					<Tooltip
						text="Percentage scoring higher than the original{scopeLabel}"
					>
						<div class="header-stat">
							<span class="header-stat-value text-neon-green"
								>{formatRate(stats.improvement_rate)}</span
							>
							<span class="header-stat-label">IMP</span>
						</div>
					</Tooltip>

					<div class="header-divider" aria-hidden="true"></div>

					<Tooltip text="Active projects">
						<div class="header-stat">
							<span class="header-stat-value text-neon-yellow"
								>{statsState.stats?.total_projects ??
									stats.total_projects}</span
							>
							<span class="header-stat-label">PROJ</span>
						</div>
					</Tooltip>

					<div class="header-divider" aria-hidden="true"></div>

					<Tooltip text="Optimizations completed today{scopeLabel}">
						<div class="header-stat">
							<span class="header-stat-value text-neon-purple"
								>{stats.optimizations_today}</span
							>
							<span class="header-stat-label">TODAY</span>
						</div>
					</Tooltip>
				</div>
			</div>

			<!-- Col 2: Center headpiece — task type badge -->
			<div class="header-center-col">
				{#if taskLabel && taskType}
					<MetaBadge type="task" value={taskType} />
				{:else}
					<span class="header-center-placeholder">—</span>
				{/if}
			</div>

			<!-- Col 3: Right wing — dimension score bars only -->
			{#if stats.average_clarity_score != null}
				<div
					class="hidden lg:flex items-center gap-2.5 justify-self-end min-w-0 overflow-hidden shrink-0"
				>
					{#each SCORE_DIMENSIONS as dim}
						{@const rawScore = stats[dim.key]}
						<Tooltip
							text="{dim.fullLabel}: {formatScore(
								rawScore,
							)}/100{scopeLabel}"
						>
							<div class="flex items-center gap-1">
								<span
									class="font-mono text-[10px] font-semibold {dim.textColor}"
									>{formatScore(rawScore)}</span
								>
								<span
									class="text-[8px] tracking-wider text-text-dim/60"
									>{dim.label}</span
								>
								<div
									class="h-[6px] w-6 overflow-hidden rounded-full bg-bg-hover"
								>
									<div
										class="{dim.barColor} h-full rounded-full transition-all duration-500"
										style="width: {rawScore != null
											? rawScore * 100
											: 0}%"
									></div>
								</div>
							</div>
						</Tooltip>
					{/each}
				</div>
			{:else}
				<!-- Empty col 3 placeholder to maintain grid structure -->
				<div></div>
			{/if}
		</div>
		<!-- /header-stats-grid -->

		<!-- Border is on the <header> element -->
	</div>
	<!-- /header-hud-root -->
{:else}
	<div class="flex flex-1 items-center justify-center">
		<span class="text-[10px] tracking-wider text-text-dim/40"
			>No forge data yet</span
		>
	</div>
{/if}

<style>
	.header-stat {
		display: flex;
		align-items: baseline;
		gap: 3px;
		padding: 0 4px;
	}
	.header-stat-value {
		font-family: var(--font-mono);
		font-size: 13px;
		font-weight: 600;
		line-height: 1;
		transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
	}
	.header-stat:hover .header-stat-value {
		transform: scale(1.08);
	}
	.header-stat-label {
		font-family: var(--font-mono);
		font-size: 9px;
		font-weight: 500;
		letter-spacing: 0.08em;
		color: var(--color-text-dim);
		opacity: 0.6;
	}
	.header-divider {
		width: 1px;
		height: 12px;
		background: var(--color-border-subtle);
		flex-shrink: 0;
	}

	.header-center-placeholder {
		font-family: var(--font-mono);
		font-size: 12px;
		font-weight: 800;
		color: var(--color-text-dim);
		opacity: 0.3;
		padding: 0 12px;
	}

	/* ── HUD root: fills the header horizontally ── */
	.header-hud-root {
		position: relative;
		flex: 1;
		min-width: 0;
	}

	/* ── The stats grid fills the full width of the root ── */
	.header-stats-grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
		align-items: center;
		width: 100%;
		height: 100%;
	}
	.header-center-col {
		display: flex;
		align-items: center;
		justify-content: center;
	}

</style>
