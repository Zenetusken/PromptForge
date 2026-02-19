<script lang="ts">
	import { providerState } from '$lib/stores/provider.svelte';
	import MCPInfo from './MCPInfo.svelte';
	import Icon from './Icon.svelte';
	import { Tooltip } from './ui';

	let showTooltip = $state(false);
	let showMCPInfo = $state(false);

	const apiDocsUrl = import.meta.env.VITE_API_URL
		? `${import.meta.env.VITE_API_URL}/docs`
		: '/docs';

	let health = $derived(providerState.health);
	let checking = $derived(providerState.healthChecking);

	function getDotColor(h: typeof health, isChecking: boolean): string {
		if (isChecking) return 'bg-neon-yellow shadow-[0_0_6px_var(--color-neon-yellow)]';
		if (h && h.status === 'ok' && h.db_connected) return 'bg-neon-green shadow-[0_0_6px_var(--color-neon-green)]';
		return 'bg-neon-red shadow-[0_0_6px_var(--color-neon-red)]';
	}

	function getStatusLabel(h: typeof health, isChecking: boolean): string {
		if (isChecking) return 'Checking...';
		if (h && h.status === 'ok') return 'Healthy';
		return 'Degraded';
	}

	let dotColor = $derived(getDotColor(health, checking));
	let statusLabel = $derived(getStatusLabel(health, checking));
</script>

<MCPInfo bind:open={showMCPInfo} />

<footer
	class="relative flex h-9 shrink-0 items-center justify-between bg-bg-secondary/80 px-4"
	data-testid="footer"
>
	<div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border-glow to-transparent"></div>
	<div class="flex items-center gap-4">
		<span class="text-[10px] text-text-dim/80">
			PromptForge &mdash; {health?.llm_provider ?? 'AI'}
		</span>
		<Tooltip text="View API documentation (Swagger UI)" side="top">
			<a
				href={apiDocsUrl}
				target="_blank"
				rel="noopener noreferrer"
				class="text-[10px] text-text-dim/70 transition-colors hover:text-neon-cyan hover:underline hover:underline-offset-2"
				data-testid="api-docs-link"
			>
				API
			</a>
		</Tooltip>
		<Tooltip text="Claude Code MCP integration" side="top">
			<button
				class="flex items-center gap-1 text-[10px] text-text-dim/70 transition-colors hover:text-neon-cyan hover:underline hover:underline-offset-2"
				onclick={() => (showMCPInfo = true)}
				data-testid="mcp-info-btn"
			>
				<Icon name="terminal" size={10} />
				MCP
			</button>
		</Tooltip>
	</div>

	<button
		type="button"
		class="relative flex items-center gap-1.5 cursor-default bg-transparent border-none p-0"
		onmouseenter={() => (showTooltip = true)}
		onmouseleave={() => (showTooltip = false)}
		onfocus={() => (showTooltip = true)}
		onblur={() => (showTooltip = false)}
		aria-label="Server health: {statusLabel}"
		aria-describedby={showTooltip && health ? 'health-tooltip' : undefined}
		data-testid="health-indicator"
	>
		<div class="h-1.5 w-1.5 rounded-full {dotColor} {!checking && health && health.status === 'ok' && health.db_connected ? 'status-dot-pulse' : ''}"></div>
		<span class="text-[10px] text-text-dim/80">{statusLabel}</span>

		{#if showTooltip && health}
			<div
				id="health-tooltip"
				role="tooltip"
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
					<div class="flex items-center justify-between gap-4">
						<span class="text-text-dim">Version</span>
						<span class="font-mono text-text-secondary">{health.version}</span>
					</div>
				</div>
			</div>
		{/if}
	</button>
</footer>
