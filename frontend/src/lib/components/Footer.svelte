<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchHealth, type HealthResponse } from '$lib/api/client';
	import MCPInfo from './MCPInfo.svelte';

	let health: HealthResponse | null = $state(null);
	let checking = $state(true);
	let showTooltip = $state(false);
	let showMCPInfo = $state(false);

	const apiDocsUrl = import.meta.env.VITE_API_URL
		? `${import.meta.env.VITE_API_URL}/docs`
		: '/docs';

	async function pollHealth() {
		checking = true;
		health = await fetchHealth();
		checking = false;
	}

	onMount(() => {
		pollHealth();
		const interval = setInterval(pollHealth, 30000);
		return () => clearInterval(interval);
	});

	function getDotColor(h: HealthResponse | null, isChecking: boolean): string {
		if (isChecking) return 'bg-neon-yellow shadow-[0_0_6px_var(--color-neon-yellow)]';
		if (h && h.status === 'ok' && h.db_connected) return 'bg-neon-green shadow-[0_0_6px_var(--color-neon-green)]';
		return 'bg-neon-red shadow-[0_0_6px_var(--color-neon-red)]';
	}

	function getStatusLabel(h: HealthResponse | null, isChecking: boolean): string {
		if (isChecking) return 'Checking...';
		if (h && h.status === 'ok') return 'Healthy';
		return 'Degraded';
	}

	let dotColor = $derived(getDotColor(health, checking));
	let statusLabel = $derived(getStatusLabel(health, checking));
</script>

<MCPInfo bind:open={showMCPInfo} />

<footer
	class="flex h-8 shrink-0 items-center justify-between border-t border-text-dim/20 bg-bg-secondary px-4"
	data-testid="footer"
>
	<div class="flex items-center gap-3">
		<span class="font-mono text-[10px] text-text-dim">
			PromptForge v1.0 &mdash; Powered by Claude
		</span>
		<a
			href={apiDocsUrl}
			target="_blank"
			rel="noopener noreferrer"
			class="font-mono text-[10px] text-text-dim transition-colors hover:text-neon-cyan"
			data-testid="api-docs-link"
		>
			API Docs
		</a>
		<button
			class="flex items-center gap-1 font-mono text-[10px] text-text-dim transition-colors hover:text-neon-cyan"
			onclick={() => (showMCPInfo = true)}
			data-testid="mcp-info-btn"
		>
			<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
			</svg>
			MCP
		</button>
	</div>

	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="relative flex items-center gap-1.5 cursor-default"
		onmouseenter={() => (showTooltip = true)}
		onmouseleave={() => (showTooltip = false)}
		data-testid="health-indicator"
	>
		<div class="h-1.5 w-1.5 rounded-full {dotColor}"></div>
		<span class="font-mono text-[10px] text-text-dim">{statusLabel}</span>

		{#if showTooltip && health}
			<div
				class="absolute bottom-6 right-0 z-50 min-w-48 rounded-lg border border-text-dim/20 bg-bg-card p-3 shadow-lg"
				data-testid="health-tooltip"
			>
				<div class="space-y-1.5 font-mono text-[10px]">
					<div class="flex items-center justify-between gap-4">
						<span class="text-text-dim">API</span>
						<span class={health.status === 'ok' ? 'text-neon-green' : 'text-neon-red'}>
							{health.status}
						</span>
					</div>
					<div class="flex items-center justify-between gap-4">
						<span class="text-text-dim">Database</span>
						<span class={health.db_connected ? 'text-neon-green' : 'text-neon-red'}>
							{health.db_connected ? 'connected' : 'disconnected'}
						</span>
					</div>
					<div class="flex items-center justify-between gap-4">
						<span class="text-text-dim">Claude</span>
						<span class={health.claude_available ? 'text-neon-green' : 'text-neon-red'}>
							{health.claude_available ? 'available' : 'unavailable'}
						</span>
					</div>
					<div class="flex items-center justify-between gap-4">
						<span class="text-text-dim">Version</span>
						<span class="text-text-secondary">{health.version}</span>
					</div>
				</div>
			</div>
		{/if}
	</div>
</footer>
