<script lang="ts">
	import { providerState } from '$lib/stores/provider.svelte';
	import { statsState } from '$lib/stores/stats.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { mcpActivityFeed } from '$lib/services/mcpActivityFeed.svelte';
	import { normalizeScore } from '$lib/utils/format';
	import MCPInfo from './MCPInfo.svelte';
	import NotificationTray from './NotificationTray.svelte';
	import Icon from './Icon.svelte';
	import { Tooltip } from './ui';

	let showMCPInfo = $state(false);
	let showHealthTooltip = $state(false);
	let now = $state(new Date());

	// Update clock every minute
	$effect(() => {
		const id = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(id);
	});

	let clockStr = $derived(
		now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
	);

	const apiDocsUrl = import.meta.env.VITE_API_URL
		? `${import.meta.env.VITE_API_URL}/docs`
		: '/docs';

	let health = $derived(providerState.health);
	let checking = $derived(providerState.healthChecking);
	let stats = $derived(statsState.activeStats);

	function getDotColor(h: typeof health, isChecking: boolean): string {
		if (isChecking) return 'bg-neon-yellow';
		if (h && h.status === 'ok' && h.db_connected) {
			if (!h.mcp_connected) return '';
			return 'bg-neon-green';
		}
		return 'bg-neon-red';
	}

	function getStatusLabel(h: typeof health, isChecking: boolean): string {
		if (isChecking) return 'Checking';
		if (h && h.status === 'ok' && h.db_connected) {
			if (!h.mcp_connected) return 'Partial';
			return 'OK';
		}
		return 'Down';
	}

	let dotColor = $derived(getDotColor(health, checking));
	let statusLabel = $derived(getStatusLabel(health, checking));
	let degraded = $derived(!checking && health?.status === 'ok' && health?.db_connected && !health?.mcp_connected);
	let dotAnimClass = $derived(
		!checking && health?.status === 'ok' && health?.db_connected
			? (health?.mcp_connected ? 'status-dot-pulse' : 'status-dot-degraded')
			: ''
	);
</script>

<MCPInfo bind:open={showMCPInfo} />

<div class="flex items-center gap-3 ml-auto pr-1">
	<!-- Compact stats -->
	{#if stats}
		<div class="flex items-center gap-2">
			<span class="font-mono text-[10px] tabular-nums text-text-dim">
				{stats.total_optimizations ?? 0} forged
			</span>
			{#if stats.average_overall_score}
				<span class="font-mono text-[10px] tabular-nums text-neon-cyan">
					avg {normalizeScore(stats.average_overall_score)}
				</span>
			{/if}
		</div>

		<div class="h-3 w-px bg-border-subtle"></div>
	{/if}

	<!-- Quick links -->
	<Tooltip text="API Docs" side="top">
		<a
			href={apiDocsUrl}
			target="_blank"
			rel="noopener noreferrer"
			class="text-[10px] text-text-dim/70 transition-colors hover:text-neon-cyan"
		>
			API
		</a>
	</Tooltip>

	<Tooltip text="MCP Info" side="top">
		<button
			class="flex items-center gap-0.5 text-[10px] text-text-dim/70 transition-colors hover:text-neon-cyan"
			onclick={() => (showMCPInfo = true)}
		>
			<Icon name="terminal" size={9} />
			MCP
		</button>
	</Tooltip>

	<!-- Network Activity -->
	{#if mcpActivityFeed.connected}
		<Tooltip text="Network Monitor ({mcpActivityFeed.activeCalls.length} active)" side="top">
			<button
				class="flex items-center gap-0.5 text-[10px] transition-colors
					{mcpActivityFeed.activeCalls.length > 0 ? 'text-neon-green animate-shimmer' : 'text-text-dim/70 hover:text-neon-green'}"
				onclick={() => windowManager.openNetworkMonitor()}
			>
				<Icon name="activity" size={9} />
				{#if mcpActivityFeed.activeCalls.length > 0}
					<span class="tabular-nums">{mcpActivityFeed.activeCalls.length}</span>
				{/if}
			</button>
		</Tooltip>
	{/if}

	<div class="h-3 w-px bg-border-subtle"></div>

	<!-- Notifications -->
	<NotificationTray />

	<div class="h-3 w-px bg-border-subtle"></div>

	<!-- Health -->
	<button
		type="button"
		class="relative flex items-center gap-1 cursor-default bg-transparent border-none p-0"
		onmouseenter={() => (showHealthTooltip = true)}
		onmouseleave={() => (showHealthTooltip = false)}
		onfocus={() => (showHealthTooltip = true)}
		onblur={() => (showHealthTooltip = false)}
		aria-label="Server health: {statusLabel}"
	>
		<div
			class="h-1.5 w-1.5 rounded-full {dotColor} {dotAnimClass}"
			style={degraded ? 'background-color: rgb(34, 255, 136)' : ''}
		></div>
		<span class="text-[10px] text-text-dim/80">{statusLabel}</span>

		{#if showHealthTooltip && health}
			<div
				role="tooltip"
				class="animate-scale-in absolute bottom-8 right-0 z-50 min-w-44 rounded-xl border border-border-subtle bg-bg-card p-3"
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
						<span class="text-text-dim">MCP</span>
						<span class={health.mcp_connected ? 'text-neon-green' : 'text-neon-orange'}>
							{health.mcp_connected ? 'connected' : 'optional'}
						</span>
					</div>
					<div class="flex items-center justify-between gap-4">
						<span class="text-text-dim">{health.llm_provider || 'LLM'}</span>
						<span class={health.llm_available ? 'text-neon-green' : 'text-neon-red'}>
							{health.llm_available ? 'available' : 'unavailable'}
						</span>
					</div>
					{#if health.llm_model}
						<div class="flex items-center justify-between gap-4">
							<span class="text-text-dim">Model</span>
							<span class="font-mono text-text-secondary">{health.llm_model}</span>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</button>

	<div class="h-3 w-px bg-border-subtle"></div>

	<!-- Clock -->
	<span class="font-mono text-[10px] tabular-nums text-text-dim/80 min-w-[35px] text-right">
		{clockStr}
	</span>
</div>
