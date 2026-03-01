<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { fetchAuditLogs, type AuditLogEntry } from '$lib/kernel/services/auditClient';

	let logs: AuditLogEntry[] = $state([]);
	let total = $state(0);
	let loading = $state(false);
	let error: string | null = $state(null);
	let selectedApp = $state('');
	let page = $state(0);
	const pageSize = 50;

	const appOptions = ['', 'promptforge', 'textforge', 'hello-world'];

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
		transform: 'text-neon-green',
		delete: 'text-neon-red',
		create: 'text-neon-purple',
		update: 'text-neon-yellow',
	};

	let unsubAudit: (() => void) | null = null;

	onMount(() => {
		loadLogs();
		// Auto-refresh when audit events arrive via bus bridge
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
				{#each appOptions.filter(a => a) as app}
					<option value={app}>{app}</option>
				{/each}
			</select>
			<button
				class="rounded border border-white/10 px-2 py-1 text-xs text-text-secondary hover:text-text-primary"
				onclick={loadLogs}
			>
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
						<tr class="border-b border-white/5 hover:bg-bg-hover">
							<td class="py-1.5 pr-3 text-text-dim whitespace-nowrap">{formatTimestamp(entry.timestamp)}</td>
							<td class="py-1.5 pr-3 text-neon-blue">{entry.app_id}</td>
							<td class="py-1.5 pr-3">
								<span class={actionColors[entry.action] ?? 'text-text-secondary'}>{entry.action}</span>
							</td>
							<td class="py-1.5 pr-3 text-text-secondary">{entry.resource_type}</td>
							<td class="py-1.5 font-mono text-text-dim max-w-[120px] truncate">{entry.resource_id ?? '—'}</td>
						</tr>
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
