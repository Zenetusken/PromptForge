<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchHealth, type HealthResponse } from '$lib/api/client';

	let health: HealthResponse | null = $state(null);
	let checking = $state(true);
	let showTooltip = $state(false);

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

<footer
	class="flex h-8 shrink-0 items-center justify-between border-t border-text-dim/20 bg-bg-secondary px-4"
	data-testid="footer"
>
	<span class="font-mono text-[10px] text-text-dim">
		PromptForge v1.0 &mdash; Powered by Claude
	</span>

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
