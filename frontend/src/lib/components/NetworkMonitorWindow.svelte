<script lang="ts">
	import { mcpActivityFeed, MCP_TOOL_COLORS, type MCPActivityEvent } from '$lib/services/mcpActivityFeed.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import Icon from './Icon.svelte';
	import { WindowTabStrip, EmptyState, InlineProgress, StatusDot } from './ui';
	import { onMount } from 'svelte';

	let activeTab: 'live' | 'log' | 'connections' = $state('live');

	const EVENT_TYPE_COLORS: Record<string, string> = {
		tool_start: 'text-neon-cyan',
		tool_progress: 'text-neon-yellow',
		tool_complete: 'text-neon-green',
		tool_error: 'text-neon-red',
		session_connect: 'text-neon-blue',
		session_disconnect: 'text-text-dim',
	};

	function getToolColor(name: string | undefined): string {
		return MCP_TOOL_COLORS[name ?? ''] ?? 'text-text-secondary';
	}

	function getEventColor(type: string): string {
		return EVENT_TYPE_COLORS[type] ?? 'text-text-secondary';
	}

	function formatTime(ts: string): string {
		try {
			return new Date(ts).toLocaleTimeString([], {
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit',
			});
		} catch {
			return '--:--:--';
		}
	}

	function formatElapsed(startedAt: number, _tick: number): string {
		const ms = _tick - startedAt;
		if (ms < 1000) return '<1s';
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}s`;
		return `${Math.floor(s / 60)}m ${s % 60}s`;
	}

	function formatDuration(ms: number | undefined): string {
		if (ms == null) return '-';
		if (ms < 1000) return `${ms}ms`;
		return `${(ms / 1000).toFixed(1)}s`;
	}

	let connected = $derived(mcpActivityFeed.connected);
	let activeCalls = $derived(mcpActivityFeed.activeCalls);
	let events = $derived(mcpActivityFeed.events);
	let sessionCount = $derived(mcpActivityFeed.sessionCount);
	let totalEvents = $derived(mcpActivityFeed.totalEventsReceived);

	// Elapsed time ticker for active calls
	let now = $state(Date.now());
	$effect(() => {
		if (activeCalls.length === 0) return;
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});

	// Breadcrumbs
	onMount(() => {
		windowManager.setBreadcrumbs('network-monitor', [
			{
				label: 'Desktop',
				icon: 'monitor',
				action: () => windowManager.closeWindow('network-monitor'),
			},
			{ label: 'Network Monitor' },
		]);
	});
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<!-- Status bar -->
	<div class="flex items-center gap-4 border-b border-neon-green/10 px-3 py-2">
		<div class="flex items-center gap-1.5">
			<StatusDot color={connected ? 'green' : 'red'} />
			<span class="text-[11px] text-text-secondary">
				{connected ? 'Connected' : 'Disconnected'}
			</span>
		</div>

		<div class="h-3 w-px bg-border-subtle"></div>

		<div class="flex items-center gap-1.5">
			<span class="text-[11px] text-text-dim">Active:</span>
			<span
				class="text-[11px] tabular-nums {activeCalls.length > 0 ? 'text-neon-cyan' : 'text-text-secondary'}"
			>
				{activeCalls.length}
			</span>
		</div>

		<div class="flex items-center gap-1.5">
			<span class="text-[11px] text-text-dim">Sessions:</span>
			<span class="text-[11px] tabular-nums text-text-secondary">{sessionCount}</span>
		</div>

		<span class="ml-auto text-[10px] tabular-nums text-text-dim">
			{totalEvents} events
		</span>
	</div>

	<WindowTabStrip
		tabs={[
			{ id: 'live', label: 'Live Activity', icon: 'activity' },
			{ id: 'log', label: 'Event Log', icon: 'file-text' },
			{ id: 'connections', label: 'Connections', icon: 'users' },
		]}
		{activeTab}
		onTabChange={(id) => (activeTab = id as typeof activeTab)}
		accent="green"
	/>

	<!-- Tab content -->
	<div class="flex-1 overflow-y-auto">
		{#if activeTab === 'live'}
			<!-- Live Activity -->
			{#if activeCalls.length === 0}
				<EmptyState icon="activity" message="No active MCP tool calls" submessage="Waiting for external clients..." />
			{:else}
				<div class="p-3 space-y-2">
					{#each activeCalls as call (call.call_id)}
						<div class="border border-neon-green/10 p-3 space-y-2">
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-2">
									<span class="text-[11px] font-medium {getToolColor(call.tool_name)}">
										{call.tool_name}
									</span>
									{#if call.client_id}
										<span class="text-[10px] text-text-dim">{call.client_id}</span>
									{/if}
								</div>
								<span class="text-[10px] tabular-nums text-text-dim">
									{formatElapsed(call.startedAt, now)}
								</span>
							</div>

							{#if call.progress != null}
								<div class="flex items-center gap-2">
									<InlineProgress percent={(call.progress ?? 0) * 100} color="green" class="flex-1" />
									<span class="text-[10px] tabular-nums text-neon-green">
										{Math.round((call.progress ?? 0) * 100)}%
									</span>
								</div>
							{/if}

							{#if call.message}
								<p class="text-[10px] text-text-dim truncate">{call.message}</p>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		{:else if activeTab === 'log'}
			<!-- Event Log -->
			{#if events.length === 0}
				<EmptyState icon="file-text" message="No events recorded" />
			{:else}
				<table class="w-full text-[11px]">
					<thead>
						<tr class="border-b border-neon-green/10 text-text-dim">
							<th class="px-3 py-1.5 text-left font-normal">Time</th>
							<th class="px-3 py-1.5 text-left font-normal">Type</th>
							<th class="px-3 py-1.5 text-left font-normal">Tool</th>
							<th class="px-3 py-1.5 text-left font-normal">Message</th>
							<th class="px-3 py-1.5 text-right font-normal">Duration</th>
						</tr>
					</thead>
					<tbody>
						{#each events as event (event.id)}
							<tr class="border-b border-neon-green/5 transition-colors hover:bg-bg-hover">
								<td class="px-3 py-1 tabular-nums text-text-dim whitespace-nowrap">
									{formatTime(event.timestamp)}
								</td>
								<td class="px-3 py-1">
									<span class="{getEventColor(event.event_type)} uppercase text-[10px] tracking-wider">
										{event.event_type.replace('tool_', '')}
									</span>
								</td>
								<td class="px-3 py-1 {getToolColor(event.tool_name)}">
									{event.tool_name ?? '-'}
								</td>
								<td class="px-3 py-1 text-text-secondary truncate max-w-[200px]">
									{event.error ?? event.message ?? '-'}
								</td>
								<td class="px-3 py-1 text-right tabular-nums text-text-dim">
									{formatDuration(event.duration_ms)}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		{:else}
			<!-- Connections -->
			<div class="p-3 space-y-3">
				<div class="border border-neon-green/10 p-3 space-y-3">
					<div class="flex items-center gap-2">
						<Icon name="server" size={14} class="text-neon-green" />
						<span class="text-[12px] text-text-primary">MCP Server</span>
					</div>
					<div class="space-y-2 text-[11px]">
						<div class="flex items-center justify-between">
							<span class="text-text-dim">Status</span>
							<span class={connected ? 'text-neon-green' : 'text-neon-red'}>
								{connected ? 'Connected' : 'Disconnected'}
							</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-text-dim">Active sessions</span>
							<span class="text-text-secondary tabular-nums">{sessionCount}</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-text-dim">Active tool calls</span>
							<span class="text-text-secondary tabular-nums">{activeCalls.length}</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-text-dim">Events received</span>
							<span class="text-text-secondary tabular-nums">{totalEvents}</span>
						</div>
					</div>
				</div>

				<div class="text-[10px] text-text-dim space-y-1">
					<p>MCP clients (Claude Code, IDEs) connect to the MCP server</p>
					<p>at <span class="text-neon-green">localhost:8001</span> via SSE transport.</p>
					<p>Tool calls are relayed to this monitor in real time.</p>
				</div>
			</div>
		{/if}
	</div>

	<!-- Footer -->
	<div class="flex items-center gap-4 border-t border-neon-green/10 px-3 py-1.5">
		<span class="text-[10px] text-text-dim">MCP Server: localhost:8001</span>
		<span class="ml-auto text-[10px] text-text-dim tabular-nums">
			{events.length} buffered
		</span>
	</div>
</div>
