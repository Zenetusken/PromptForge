<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { fetchAuditLogs, type AuditLogEntry } from '$lib/kernel/services/auditClient';
	import { fetchApps } from '$lib/kernel/services/appManagerClient';
	import { kernelBusBridge } from '$lib/kernel/services/kernelBusBridge.svelte';

	let logs: AuditLogEntry[] = $state([]);
	let total = $state(0);
	let loading = $state(false);
	let error: string | null = $state(null);
	let selectedApp = $state('');
	let page = $state(0);
	let expandedId: number | null = $state(null);
	let busConnected = $derived(kernelBusBridge.connected);
	const pageSize = 50;

	const fallbackApps = ['promptforge', 'textforge', 'hello-world'];
	let appOptions: string[] = $state(fallbackApps);

	async function loadApps() {
		try {
			const result = await fetchApps();
			const ids = result.apps.map((a) => a.id).filter(Boolean);
			if (ids.length > 0) appOptions = ids;
		} catch {
			// Keep fallback list
		}
	}

	async function loadLogs() {
		loading = true;
		error = null;
		try {
			const appId = selectedApp || undefined;
			const result = await fetchAuditLogs(appId, pageSize, page * pageSize);
			logs = result.logs;
			total = result.total;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load audit logs';
		} finally {
			loading = false;
		}
	}

	function formatTimestamp(iso: string): string {
		const d = new Date(iso);
		const now = Date.now();
		const diff = now - d.getTime();
		if (diff < 60_000) return 'just now';
		if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
		if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
		return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
	}

	const actionColors: Record<string, string> = {
		optimize: 'text-neon-cyan',
		optimize_step: 'text-neon-cyan',
		analyze: 'text-neon-cyan',
		strategy: 'text-neon-cyan',
		validate: 'text-neon-cyan',
		transform: 'text-neon-green',
		create: 'text-neon-purple',
		update: 'text-neon-yellow',
		delete: 'text-neon-red',
		bulk_delete: 'text-neon-red',
		clear_all: 'text-neon-red',
		archive: 'text-neon-orange',
		unarchive: 'text-neon-teal',
		cancel: 'text-neon-orange',
		batch_optimize: 'text-neon-purple',
		sync_workspace: 'text-neon-teal',
		move: 'text-neon-blue',
		reorder: 'text-neon-blue',
		disconnect: 'text-neon-red',
	};

	function toggleExpand(id: number) {
		expandedId = expandedId === id ? null : id;
	}

	let unsubAudit: (() => void) | null = null;

	onMount(() => {
		loadApps();
		loadLogs();
		unsubAudit = systemBus.on('kernel:audit_logged', () => {
			loadLogs();
		});
	});

	onDestroy(() => {
		unsubAudit?.();
	});

	function handleAppChange() {
		page = 0;
		loadLogs();
	}

	function prevPage() {
		if (page > 0) { page--; loadLogs(); }
	}

	function nextPage() {
		if ((page + 1) * pageSize < total) { page++; loadLogs(); }
	}
</script>

<div class="flex h-full flex-col gap-3 p-4 text-text-primary">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-3">
			<select
				class="rounded border border-white/10 bg-bg-input px-2 py-1 text-xs text-text-primary"
				bind:value={selectedApp}
				onchange={handleAppChange}
			>
				<option value="">All Apps</option>
				{#each appOptions as app}
					<option value={app}>{app}</option>
				{/each}
			</select>
			<button
				class="flex items-center gap-1.5 rounded border border-white/10 px-2 py-1 text-xs text-text-secondary hover:text-text-primary"
				onclick={loadLogs}
			>
				{#if busConnected}
					<span class="relative flex h-1.5 w-1.5">
						<span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-green opacity-75"></span>
						<span class="relative inline-flex h-1.5 w-1.5 rounded-full bg-neon-green"></span>
					</span>
				{/if}
				Refresh
			</button>
		</div>
		<span class="text-xs text-text-dim">{total} entries</span>
	</div>

	<!-- Error -->
	{#if error}
		<div class="rounded border border-neon-red/30 bg-neon-red/5 p-2 text-xs text-neon-red">{error}</div>
	{/if}

	<!-- Table -->
	<div class="flex-1 overflow-auto">
		{#if loading && logs.length === 0}
			<div class="flex h-32 items-center justify-center text-text-dim text-xs">Loading...</div>
		{:else if logs.length === 0}
			<div class="flex h-32 items-center justify-center text-text-dim text-xs">No audit entries</div>
		{:else}
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-white/5 text-left text-text-dim">
						<th class="pb-2 pr-3 font-medium">Timestamp</th>
						<th class="pb-2 pr-3 font-medium">App</th>
						<th class="pb-2 pr-3 font-medium">Action</th>
						<th class="pb-2 pr-3 font-medium">Resource</th>
						<th class="pb-2 font-medium">ID</th>
					</tr>
				</thead>
				<tbody>
					{#each logs as entry (entry.id)}
						<tr
							class="border-b border-white/5 hover:bg-bg-hover cursor-pointer"
							onclick={() => toggleExpand(entry.id)}
						>
							<td class="py-1.5 pr-3 text-text-dim whitespace-nowrap">{formatTimestamp(entry.timestamp)}</td>
							<td class="py-1.5 pr-3 text-neon-blue">{entry.app_id}</td>
							<td class="py-1.5 pr-3">
								<span class={actionColors[entry.action] ?? 'text-text-secondary'}>{entry.action}</span>
							</td>
							<td class="py-1.5 pr-3 text-text-secondary">{entry.resource_type}</td>
							<td
								class="py-1.5 font-mono text-text-dim max-w-[120px] truncate"
								title={entry.resource_id ?? undefined}
							>{entry.resource_id ?? '\u2014'}</td>
						</tr>
						{#if expandedId === entry.id && entry.details}
							<tr class="border-b border-white/5 bg-bg-secondary">
								<td colspan="5" class="px-3 py-2">
									<div class="flex flex-wrap gap-x-4 gap-y-1 text-xs">
										{#each Object.entries(entry.details) as [key, value]}
											<span>
												<span class="text-text-dim">{key}:</span>
												<span class="text-text-secondary font-mono">{value ?? '\u2014'}</span>
											</span>
										{/each}
									</div>
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		{/if}
	</div>

	<!-- Pagination -->
	{#if total > pageSize}
		<div class="flex items-center justify-between border-t border-white/5 pt-2">
			<button
				class="text-xs text-text-secondary hover:text-text-primary disabled:opacity-30"
				disabled={page === 0}
				onclick={prevPage}
			>
				Previous
			</button>
			<span class="text-xs text-text-dim">
				{page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
			</span>
			<button
				class="text-xs text-text-secondary hover:text-text-primary disabled:opacity-30"
				disabled={(page + 1) * pageSize >= total}
				onclick={nextPage}
			>
				Next
			</button>
		</div>
	{/if}
</div>
