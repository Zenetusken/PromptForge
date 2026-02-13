<script lang="ts">
	import { fetchStats } from '$lib/api/client';
	import { onMount } from 'svelte';

	let { sidebarOpen = $bindable(true) }: { sidebarOpen: boolean } = $props();

	let totalOptimizations = $state(0);

	async function loadStats() {
		const stats = await fetchStats();
		if (stats) {
			totalOptimizations = stats.total_optimizations;
		}
	}

	onMount(() => {
		loadStats();
		// Refresh stats periodically
		const interval = setInterval(loadStats, 10000);
		return () => clearInterval(interval);
	});

	// Also expose a refresh method for external callers
	export function refreshStats() {
		loadStats();
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
		<div
			class="flex items-center gap-1.5 rounded-full border border-neon-cyan/30 bg-neon-cyan/10 px-3 py-1 text-sm"
			data-testid="stats-badge"
		>
			<div class="h-2 w-2 rounded-full bg-neon-green shadow-[0_0_6px_var(--color-neon-green)]"></div>
			<span class="font-mono font-semibold text-neon-cyan" data-testid="stats-count">{totalOptimizations}</span>
			<span class="text-text-secondary">forged</span>
		</div>
	</div>
</header>
