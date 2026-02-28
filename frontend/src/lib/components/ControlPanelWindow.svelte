<script lang="ts">
	import { settingsState, NEON_COLORS, NEON_COLOR_HEX } from '$lib/stores/settings.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { processScheduler } from '$lib/stores/processScheduler.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { ALL_STRATEGIES } from '$lib/utils/strategies';
	import { appRegistry } from '$lib/kernel/services/appRegistry.svelte';
	import type { AnyComponent } from '$lib/kernel/types';
	import Icon from './Icon.svelte';
	import { WindowTabStrip } from './ui';

	let activeTab = $state('providers');

	// Static tabs + dynamic app settings tabs
	const staticTabs = [
		{ id: 'providers', label: 'Providers', icon: 'cpu' },
		{ id: 'pipeline', label: 'Pipeline', icon: 'git-branch' },
		{ id: 'display', label: 'Display', icon: 'monitor' },
		{ id: 'system', label: 'System', icon: 'settings' },
	];

	let tabs = $derived([
		...staticTabs,
		...appRegistry.appsWithSettings.map(a => ({
			id: `app-${a.appId}`,
			label: a.name,
			icon: a.icon,
		})),
	]);

	// Cache resolved settings components per app ID
	let settingsComponentCache: Record<string, Promise<{ default: AnyComponent }>> = {};
	function getSettingsComponent(appId: string) {
		const app = appRegistry.appsWithSettings.find(a => a.appId === appId);
		if (!app) return null;
		if (!settingsComponentCache[appId] && app.instance.getSettingsComponent) {
			settingsComponentCache[appId] = app.instance.getSettingsComponent();
		}
		return settingsComponentCache[appId] ?? null;
	}

	const strategies = ['', ...ALL_STRATEGIES];
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<WindowTabStrip {tabs} {activeTab} onTabChange={(id) => activeTab = id} />

	<!-- Content -->
	<div class="flex-1 overflow-y-auto p-3 space-y-3">
		{#if activeTab === 'providers'}
			<div class="space-y-3">
				<h3 class="section-heading">Provider Configuration</h3>
				<div class="space-y-2">
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Active Provider</span>
						<span class="text-xs text-neon-green">{providerState.health?.llm_provider || 'Auto-detect'}</span>
					</div>
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Model</span>
						<span class="text-xs text-text-primary">{providerState.health?.llm_model || 'Default'}</span>
					</div>
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Status</span>
						<span class="text-xs {providerState.health?.llm_available ? 'text-neon-green' : 'text-neon-red'}">
							{providerState.health?.llm_available ? 'Connected' : 'Unavailable'}
						</span>
					</div>
				</div>
			</div>

		{:else if activeTab === 'pipeline'}
			<div class="space-y-3">
				<h3 class="section-heading">Pipeline Defaults</h3>
				<div class="space-y-2">
					<label class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Default Strategy</span>
						<select
							id="cp-default-strategy"
							class="bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1 outline-none focus:border-neon-cyan/30"
							value={settingsState.defaultStrategy}
							onchange={(e) => settingsState.update({ defaultStrategy: (e.target as HTMLSelectElement).value })}
						>
							{#each strategies as s (s)}
								<option value={s}>{s || 'Auto-select'}</option>
							{/each}
						</select>
					</label>
					<label class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Max Concurrent Forges</span>
						<input
							id="cp-max-concurrent"
							type="number"
							min="1"
							max="5"
							class="w-16 bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1 outline-none text-center focus:border-neon-cyan/30"
							value={settingsState.maxConcurrentForges}
							onchange={(e) => {
								const val = parseInt((e.target as HTMLInputElement).value) || 2;
								settingsState.update({ maxConcurrentForges: Math.max(1, Math.min(5, val)) });
							}}
						/>
					</label>
					<label class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Auto-retry on Rate Limit</span>
						<input
							id="cp-auto-retry"
							type="checkbox"
							class="accent-neon-cyan"
							checked={settingsState.autoRetryOnRateLimit}
							onchange={(e) => settingsState.update({ autoRetryOnRateLimit: (e.target as HTMLInputElement).checked })}
						/>
					</label>
				</div>
			</div>

		{:else if activeTab === 'display'}
			<div class="space-y-3">
				<h3 class="section-heading">Accent Color</h3>
				<div class="grid grid-cols-5 gap-2">
					{#each NEON_COLORS as color (color)}
						<button
							class="flex items-center justify-center w-8 h-8 border transition-colors
								{settingsState.accentColor === color
									? 'border-white/60'
									: 'border-transparent hover:border-white/20'}"
							onclick={() => settingsState.update({ accentColor: color })}
							title={color.replace('neon-', '')}
						>
							<span
								class="w-4 h-4"
								style="background-color: {NEON_COLOR_HEX[color]}"
							></span>
						</button>
					{/each}
				</div>

				<h3 class="section-heading pt-2">Animations</h3>
				<label class="flex items-center justify-between">
					<span class="text-xs text-text-secondary">Enable Animations</span>
					<input
						type="checkbox"
						class="accent-neon-cyan"
						checked={settingsState.enableAnimations}
						onchange={(e) => settingsState.update({ enableAnimations: (e.target as HTMLInputElement).checked })}
					/>
				</label>

				<button
					class="mt-2 flex items-center gap-1.5 text-[10px] text-text-dim hover:text-neon-cyan transition-colors"
					onclick={() => windowManager.openDisplaySettings()}
				>
					<Icon name="monitor" size={10} />
					<span>More Display Settings...</span>
				</button>
			</div>

		{:else if activeTab === 'system'}
			<div class="space-y-3">
				<h3 class="section-heading">System Info</h3>
				<div class="space-y-2">
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Backend Version</span>
						<span class="text-xs text-text-primary">{providerState.health?.version || 'Unknown'}</span>
					</div>
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">DB Connected</span>
						<span class="text-xs {providerState.health?.db_connected ? 'text-neon-green' : 'text-neon-red'}">
							{providerState.health?.db_connected ? 'Yes' : 'No'}
						</span>
					</div>
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">MCP Connected</span>
						<span class="text-xs {providerState.health?.mcp_connected ? 'text-neon-green' : 'text-neon-red'}">
							{providerState.health?.mcp_connected ? 'Yes' : 'No'}
						</span>
					</div>
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-secondary">Active Processes</span>
						<span class="text-xs text-text-primary">{processScheduler.runningCount} running, {processScheduler.queue.length} queued</span>
					</div>
				</div>

				{#if Object.keys(providerState.tokenBudgets).length > 0}
					<h3 class="section-heading pt-2">Token Usage</h3>
					<div class="space-y-2">
						{#each Object.entries(providerState.tokenBudgets) as [provider, budget]}
							<div class="border border-neon-cyan/10 p-2 space-y-1">
								<div class="text-xs text-neon-cyan font-medium">{provider}</div>
								<div class="flex items-center justify-between">
									<span class="text-[10px] text-text-dim">Requests</span>
									<span class="text-[10px] text-text-primary">{budget.request_count}</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[10px] text-text-dim">Input tokens</span>
									<span class="text-[10px] text-text-primary">{budget.input_tokens_used.toLocaleString()}</span>
								</div>
								<div class="flex items-center justify-between">
									<span class="text-[10px] text-text-dim">Output tokens</span>
									<span class="text-[10px] text-text-primary">{budget.output_tokens_used.toLocaleString()}</span>
								</div>
								{#if budget.daily_limit != null}
									<div class="flex items-center justify-between">
										<span class="text-[10px] text-text-dim">Remaining</span>
										<span class="text-[10px] {(budget.remaining ?? 0) > 0 ? 'text-neon-green' : 'text-neon-red'}">
											{budget.remaining?.toLocaleString() ?? '0'}
										</span>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}

				<button
					class="mt-2 border border-neon-red/20 px-3 py-1.5 text-[11px] text-neon-red hover:bg-neon-red/10 transition-colors"
					onclick={() => settingsState.reset()}
				>
					Reset All Settings
				</button>
			</div>
		{:else if activeTab.startsWith('app-')}
			{@const appId = activeTab.slice(4)}
			{@const componentPromise = getSettingsComponent(appId)}
			{#if componentPromise}
				{#await componentPromise then mod}
					{@const SettingsComponent = mod.default}
					<SettingsComponent />
				{:catch}
					<p class="text-xs text-text-secondary">Failed to load settings component.</p>
				{/await}
			{:else}
				<p class="text-xs text-text-secondary">No settings component available.</p>
			{/if}
		{/if}
	</div>
</div>
