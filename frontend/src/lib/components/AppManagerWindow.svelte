<script lang="ts">
	import { onMount } from 'svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import Icon from './Icon.svelte';
	import {
		fetchApps,
		enableApp,
		disableApp,
		type KernelApp,
	} from '$lib/kernel/services/appManagerClient';
	import { fetchAllUsage, type AppUsageEntry } from '$lib/kernel/services/auditClient';

	let apps: KernelApp[] = $state([]);
	let usage: Map<string, AppUsageEntry[]> = $state(new Map());
	let loading = $state(false);
	let error: string | null = $state(null);
	let togglingId: string | null = $state(null);
	let expandedAppId: string | null = $state(null);

	const statusColors: Record<string, string> = {
		ENABLED: 'text-neon-green',
		DISABLED: 'text-text-dim',
		ERROR: 'text-neon-red',
		DISCOVERED: 'text-neon-yellow',
		INSTALLED: 'text-neon-blue',
	};

	const statusIcons: Record<string, string> = {
		ENABLED: 'check-circle',
		DISABLED: 'minus-circle',
		ERROR: 'alert-triangle',
		DISCOVERED: 'search',
		INSTALLED: 'download',
	};

	function getQuotaLimit(app: KernelApp, resource: string): number {
		if (!app.resource_quotas) return 0;
		if (resource === 'api_calls') return app.resource_quotas.max_api_calls_per_hour ?? 0;
		if (resource === 'documents') return app.resource_quotas.max_documents ?? 0;
		if (resource === 'storage') return app.resource_quotas.max_storage_mb ?? 0;
		return 0;
	}

	function getQuotaPercent(count: number, limit: number): number {
		if (limit <= 0) return 0;
		return Math.min(100, Math.round((count / limit) * 100));
	}

	function getQuotaColor(percent: number): string {
		if (percent >= 90) return 'bg-neon-red';
		if (percent >= 70) return 'bg-neon-yellow';
		return 'bg-neon-green';
	}

	const RESOURCE_LABELS: Record<string, string> = {
		api_calls: 'API Calls',
		documents: 'Documents',
		storage: 'Storage (MB)',
	};

	async function loadApps() {
		loading = true;
		error = null;
		try {
			const [appResult, usageResult] = await Promise.all([
				fetchApps(),
				fetchAllUsage().catch(() => ({ usage: [] })),
			]);
			apps = appResult.apps;

			// Group usage by app_id
			const grouped = new Map<string, AppUsageEntry[]>();
			for (const entry of usageResult.usage) {
				const existing = grouped.get(entry.app_id) ?? [];
				existing.push(entry);
				grouped.set(entry.app_id, existing);
			}
			usage = grouped;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load apps';
		} finally {
			loading = false;
		}
	}

	async function toggleApp(app: KernelApp) {
		togglingId = app.id;
		try {
			if (app.status === 'ENABLED') {
				await disableApp(app.id);
			} else {
				await enableApp(app.id);
			}
			await loadApps();
		} catch (e) {
			error = e instanceof Error ? e.message : `Failed to toggle ${app.name}`;
		} finally {
			togglingId = null;
		}
	}

	onMount(() => {
		loadApps();
		const unsub1 = systemBus.on('kernel:app_enabled', () => loadApps());
		const unsub2 = systemBus.on('kernel:app_disabled', () => loadApps());
		const unsub3 = systemBus.on('kernel:audit_logged', () => loadApps());
		return () => {
			unsub1();
			unsub2();
			unsub3();
		};
	});
</script>

<div class="flex h-full flex-col gap-3 p-4 text-text-primary">
	<div class="flex items-center justify-between">
		<h3 class="text-sm font-medium">Installed Apps</h3>
		<button
			class="border border-white/10 px-2 py-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
			onclick={loadApps}
		>
			Refresh
		</button>
	</div>

	{#if error}
		<div class="border border-neon-red/30 bg-neon-red/5 p-2 text-xs text-neon-red flex items-center gap-1.5">
			<Icon name="alert-triangle" size={12} />
			{error}
		</div>
	{/if}

	{#if loading && apps.length === 0}
		<div class="flex h-32 items-center justify-center text-text-dim text-xs">Loading...</div>
	{:else}
		<div class="flex-1 overflow-auto">
			<div class="grid gap-2">
				{#each apps as app (app.id)}
					{@const isToggling = togglingId === app.id}
					{@const isExpanded = expandedAppId === app.id}
					{@const appUsage = usage.get(app.id) ?? []}
					<div
						class="border border-white/10 bg-bg-card transition-colors"
						class:opacity-50={app.status === 'DISABLED'}
					>
						<!-- Header row -->
						<button
							class="flex w-full items-center justify-between p-3 text-left"
							onclick={() => { expandedAppId = isExpanded ? null : app.id; }}
						>
							<div class="flex items-center gap-2 min-w-0">
								{#if app.icon}
									<Icon name={app.icon as any} size={14} class="shrink-0 text-text-secondary" />
								{/if}
								<div class="min-w-0">
									<span class="text-sm font-medium truncate block">{app.name}</span>
									<span class="text-[10px] text-text-dim">v{app.version}</span>
								</div>
							</div>
							<div class="flex items-center gap-2 shrink-0">
								<span class="flex items-center gap-1 {statusColors[app.status] ?? 'text-text-secondary'}">
									<Icon name={(statusIcons[app.status] ?? 'circle') as any} size={10} />
									<span class="text-[10px]">{app.status}</span>
								</span>
								{#if app.status === 'ENABLED' || app.status === 'DISABLED'}
									<!-- svelte-ignore a11y_click_events_have_key_events -->
									<span
										class="border px-2 py-0.5 text-[10px] transition-colors cursor-pointer {app.status === 'ENABLED'
											? 'border-neon-red/20 text-neon-red hover:bg-neon-red/10'
											: 'border-neon-green/20 text-neon-green hover:bg-neon-green/10'}"
										role="button"
										tabindex="0"
										onclick={(e) => { e.stopPropagation(); toggleApp(app); }}
										class:pointer-events-none={isToggling}
										class:opacity-50={isToggling}
									>
										{#if isToggling}
											...
										{:else}
											{app.status === 'ENABLED' ? 'Disable' : 'Enable'}
										{/if}
									</span>
								{/if}
								<Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} size={10} class="text-text-dim" />
							</div>
						</button>

						{#if app.error}
							<div class="mx-3 mb-2 text-[10px] text-neon-red">{app.error}</div>
						{/if}

						<!-- Summary stats row -->
						<div class="flex flex-wrap gap-x-3 gap-y-1 px-3 pb-2 text-[10px]">
							{#if app.services_satisfied !== undefined}
								<span class:text-neon-green={app.services_satisfied} class:text-neon-red={!app.services_satisfied}>
									{app.services_satisfied ? 'Services OK' : 'Missing services'}
								</span>
							{/if}
							{#if app.windows}
								<span class="text-text-dim">{app.windows} windows</span>
							{/if}
							{#if app.routers}
								<span class="text-text-dim">{app.routers} routers</span>
							{/if}
						</div>

						<!-- Expanded detail: usage & quotas -->
						{#if isExpanded}
							<div class="border-t border-white/5 px-3 py-2">
								<span class="text-[10px] text-text-dim uppercase tracking-wider">Resource Usage</span>
								<div class="mt-1.5 grid gap-1.5">
									{#each ['api_calls', 'documents', 'storage'] as resource}
										{@const limit = getQuotaLimit(app, resource)}
										{@const entry = appUsage.find(u => u.resource === resource)}
										{@const count = entry?.count ?? 0}
										{@const percent = getQuotaPercent(count, limit)}
										{#if limit > 0}
											<div class="flex items-center gap-2">
												<span class="text-[10px] text-text-dim w-20 shrink-0">{RESOURCE_LABELS[resource] ?? resource}</span>
												<div class="flex-1 h-1.5 bg-white/5 overflow-hidden">
													<div
														class="h-full transition-all {getQuotaColor(percent)}"
														style="width: {percent}%"
													></div>
												</div>
												<span class="text-[10px] text-text-secondary w-16 text-right shrink-0">
													{count}/{limit}
												</span>
											</div>
										{/if}
									{/each}
									{#if !['api_calls', 'documents', 'storage'].some(r => getQuotaLimit(app, r) > 0)}
										<span class="text-[10px] text-text-dim">No quotas configured</span>
									{/if}
								</div>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
