<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchHealth, type HealthResponse } from '$lib/api/client';
	import MCPInfo from './MCPInfo.svelte';
	import Icon from './Icon.svelte';

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
	class="flex h-9 shrink-0 items-center justify-between border-t border-border-subtle bg-bg-secondary/80 px-4"
	data-testid="footer"
>
	<div class="flex items-center gap-4">
		<span class="text-[10px] text-text-dim/60">
			PromptForge &mdash; Powered by Claude
		</span>
		<a
			href={apiDocsUrl}
			target="_blank"
			rel="noopener noreferrer"
			class="text-[10px] text-text-dim/50 transition-colors hover:text-neon-cyan"
			data-testid="api-docs-link"
		>
			API
		</a>
		<button
			class="flex items-center gap-1 text-[10px] text-text-dim/50 transition-colors hover:text-neon-cyan"
			onclick={() => (showMCPInfo = true)}
			data-testid="mcp-info-btn"
		>
			<Icon name="terminal" size={10} />
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
		<span class="text-[10px] text-text-dim/60">{statusLabel}</span>

		{#if showTooltip && health}
			<div
				class="animate-scale-in absolute bottom-7 right-0 z-50 min-w-44 rounded-xl border border-border-subtle bg-bg-card p-3 shadow-xl"
				data-testid="health-tooltip"
			>
				<div class="space-y-2 text-[10px]">
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
						<span class="font-mono text-text-secondary">{health.version}</span>
					</div>
				</div>
			</div>
		{/if}
	</div>
</footer>
