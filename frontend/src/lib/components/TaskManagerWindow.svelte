<script lang="ts">
	import { processScheduler, type ForgeProcess, type ProcessStatus } from '$lib/stores/processScheduler.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { mcpActivityFeed } from '$lib/services/mcpActivityFeed.svelte';
	import { createArtifactDescriptor } from '$lib/utils/fileDescriptor';
	import { toArtifactName } from '$lib/utils/fileTypes';
	import { openDocument } from '$lib/utils/documentOpener';
	import { appRegistry } from '$lib/kernel/services/appRegistry.svelte';
	import { listJobs, cancelJob, type JobRecord } from '$lib/kernel/services/jobClient';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import Icon from './Icon.svelte';
	import { StatusDot, InlineProgress, EmptyState } from './ui';

	/** Look up process type metadata from app registry, falling back to forge defaults. */
	function getProcessTypeMeta(proc: ForgeProcess) {
		const match = appRegistry.allProcessTypes.find(pt => pt.id === proc.processType);
		return match ?? { id: 'forge', label: 'Forge', icon: 'zap', stages: ['analyze', 'strategy', 'optimize', 'validate'] };
	}

	let activeTab: 'processes' | 'jobs' = $state('processes');
	let jobs: JobRecord[] = $state([]);
	let jobsLoading = $state(false);

	async function loadJobs() {
		jobsLoading = true;
		try {
			const data = await listJobs({ limit: 50 });
			jobs = data.jobs;
		} catch {
			// silent — endpoint may not be available yet
		} finally {
			jobsLoading = false;
		}
	}

	// Auto-refresh jobs when tab is active or bus events fire
	$effect(() => {
		if (activeTab === 'jobs') { loadJobs(); }
	});
	$effect(() => {
		const unsub = systemBus.on('kernel:job_completed', () => { if (activeTab === 'jobs') loadJobs(); });
		const unsub2 = systemBus.on('kernel:job_failed', () => { if (activeTab === 'jobs') loadJobs(); });
		const unsub3 = systemBus.on('kernel:job_submitted', () => { if (activeTab === 'jobs') loadJobs(); });
		return () => { unsub(); unsub2(); unsub3(); };
	});

	const JOB_STATUS_COLOR: Record<string, string> = {
		pending: 'text-neon-yellow',
		running: 'text-neon-green',
		completed: 'text-neon-cyan',
		failed: 'text-neon-red',
		cancelled: 'text-text-dim',
	};

	function formatJobDuration(job: JobRecord): string {
		if (!job.started_at) return '-';
		const start = new Date(job.started_at).getTime();
		const end = job.completed_at ? new Date(job.completed_at).getTime() : Date.now();
		const ms = end - start;
		if (ms < 1000) return '<1s';
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}s`;
		return `${Math.floor(s / 60)}m ${s % 60}s`;
	}

	async function handleCancelJob(jobId: string) {
		try {
			await cancelJob(jobId);
			await loadJobs();
		} catch { /* ignore */ }
	}

	let sortBy: 'pid' | 'status' | 'started' = $state('pid');
	let sortAsc = $state(false);

	const STATUS_ORDER: Record<ProcessStatus, number> = {
		running: 0,
		queued: 1,
		paused: 2,
		completed: 3,
		error: 4,
		cancelled: 5,
	};

	const STATUS_COLOR: Record<ProcessStatus, string> = {
		running: 'text-neon-green',
		queued: 'text-neon-yellow',
		paused: 'text-neon-orange',
		completed: 'text-neon-cyan',
		error: 'text-neon-red',
		cancelled: 'text-text-dim',
	};

	let sorted = $derived.by(() => {
		const list = [...processScheduler.processes];
		list.sort((a, b) => {
			let cmp = 0;
			if (sortBy === 'pid') cmp = a.pid - b.pid;
			else if (sortBy === 'status') cmp = STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
			else if (sortBy === 'started') cmp = a.startedAt - b.startedAt;
			return sortAsc ? cmp : -cmp;
		});
		return list;
	});

	let runCount = $derived(processScheduler.runningCount);
	let queueCount = $derived(processScheduler.queue.length);
	let completedCount = $derived(processScheduler.completed.length);
	let totalCount = $derived(processScheduler.processes.length);

	function toggleSort(col: typeof sortBy) {
		if (sortBy === col) { sortAsc = !sortAsc; }
		else { sortBy = col; sortAsc = col === 'pid'; }
	}

	function formatDuration(proc: ForgeProcess): string {
		const end = proc.completedAt ?? Date.now();
		const ms = end - proc.startedAt;
		if (ms < 1000) return '<1s';
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}s`;
		return `${Math.floor(s / 60)}m ${s % 60}s`;
	}

	function handleCancel(proc: ForgeProcess) {
		processScheduler.cancel(proc.pid);
	}

	function handleDismiss(proc: ForgeProcess) {
		processScheduler.dismiss(proc.pid);
	}

	function handleOpenResult(proc: ForgeProcess) {
		if (proc.optimizationId) {
			const descriptor = createArtifactDescriptor(
				proc.optimizationId,
				toArtifactName(proc.title, proc.score),
			);
			openDocument(descriptor);
		}
	}

	function handleRetry(proc: ForgeProcess) {
		if (proc.optimizationId) {
			import('$lib/api/client').then(({ fetchRetry }) => {
				fetchRetry(proc.optimizationId!, () => {}, (err: Error) => console.error(err));
			});
		}
	}
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<!-- Tab bar -->
	<div class="flex items-center border-b border-neon-cyan/10">
		<button
			class="px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors {activeTab === 'processes' ? 'text-neon-cyan border-b border-neon-cyan' : 'text-text-dim hover:text-text-secondary'}"
			onclick={() => { activeTab = 'processes'; }}
		>
			Processes
		</button>
		<button
			class="px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors {activeTab === 'jobs' ? 'text-neon-cyan border-b border-neon-cyan' : 'text-text-dim hover:text-text-secondary'}"
			onclick={() => { activeTab = 'jobs'; }}
		>
			Jobs
		</button>

		<!-- Summary (processes tab) -->
		{#if activeTab === 'processes'}
			<div class="flex items-center gap-4 ml-4">
				<div class="flex items-center gap-1.5">
					<StatusDot color="green" />
					<span class="text-[11px] text-text-secondary">{runCount} running</span>
				</div>
				<div class="flex items-center gap-1.5">
					<StatusDot color="yellow" />
					<span class="text-[11px] text-text-secondary">{queueCount} queued</span>
				</div>
				<div class="flex items-center gap-1.5">
					<StatusDot color="cyan" />
					<span class="text-[11px] text-text-secondary">{completedCount} completed</span>
				</div>
			</div>
			<span class="ml-auto text-[10px] text-text-dim pr-3">{totalCount} total</span>
		{:else}
			<span class="ml-auto text-[10px] text-text-dim pr-3">{jobs.length} jobs</span>
		{/if}

		{#if providerState.health}
			<div class="h-3 w-px bg-border-subtle mr-3"></div>
			<span class="text-[10px] pr-3 {providerState.health.llm_available ? 'text-neon-green' : 'text-neon-red'}">
				{providerState.health.llm_provider || 'LLM'}: {providerState.health.llm_available ? 'OK' : 'Down'}
			</span>
		{/if}
	</div>

	{#if activeTab === 'processes'}
	<!-- Process table -->
	<div class="flex-1 overflow-y-auto">
		{#if sorted.length === 0}
			<EmptyState icon="server" message="No processes" />
		{:else}
			<table class="w-full text-[11px]">
				<thead>
					<tr class="border-b border-neon-cyan/10 text-text-dim">
						<th class="cursor-pointer px-3 py-1.5 text-left font-normal hover:text-neon-cyan" onclick={() => toggleSort('pid')}>
							PID {sortBy === 'pid' ? (sortAsc ? '\u25B2' : '\u25BC') : ''}
						</th>
						<th class="px-3 py-1.5 text-left font-normal">Title</th>
						<th class="px-3 py-1.5 text-left font-normal">Type</th>
						<th class="cursor-pointer px-3 py-1.5 text-left font-normal hover:text-neon-cyan" onclick={() => toggleSort('status')}>
							Status {sortBy === 'status' ? (sortAsc ? '\u25B2' : '\u25BC') : ''}
						</th>
						<th class="px-3 py-1.5 text-left font-normal">Strategy</th>
						<th class="px-3 py-1.5 text-left font-normal">Progress</th>
						<th class="cursor-pointer px-3 py-1.5 text-left font-normal hover:text-neon-cyan" onclick={() => toggleSort('started')}>
							Duration {sortBy === 'started' ? (sortAsc ? '\u25B2' : '\u25BC') : ''}
						</th>
						<th class="px-3 py-1.5 text-right font-normal">Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each sorted as proc (proc.id)}
						{@const ptMeta = getProcessTypeMeta(proc)}
						<tr class="border-b border-neon-cyan/5 transition-colors hover:bg-bg-hover">
							<td class="px-3 py-1.5 tabular-nums text-text-dim">{proc.pid}</td>
							<td class="px-3 py-1.5 truncate max-w-[200px] text-text-primary">{proc.title}</td>
							<td class="px-3 py-1.5">
								<span class="text-[10px] text-text-secondary" title={ptMeta.label}>
									<Icon name={ptMeta.icon as any} size={10} class="inline -mt-px mr-0.5" />{ptMeta.label}
								</span>
							</td>
							<td class="px-3 py-1.5">
								<span class="{STATUS_COLOR[proc.status]} uppercase text-[10px] tracking-wider">{proc.status}</span>
							</td>
							<td class="px-3 py-1.5 text-text-secondary">{proc.strategy ?? '-'}</td>
							<td class="px-3 py-1.5">
								{#if proc.status === 'running'}
									<div class="flex items-center gap-2">
										<InlineProgress percent={proc.progress * 100} class="flex-1 max-w-[80px]" />
										<span class="text-[10px] tabular-nums text-neon-cyan">{Math.round(proc.progress * 100)}%</span>
									</div>
								{:else if proc.status === 'completed'}
									<span class="text-[10px] text-neon-cyan tabular-nums">
										{proc.score != null ? `${proc.score}/10` : 'done'}
									</span>
								{:else if proc.status === 'error'}
									<span class="text-[10px] text-neon-red truncate max-w-[120px] inline-block" title={proc.error ?? ''}>
										{proc.error ?? 'Error'}
									</span>
								{:else}
									<span class="text-[10px] text-text-dim">-</span>
								{/if}
							</td>
							<td class="px-3 py-1.5 tabular-nums text-text-secondary">{formatDuration(proc)}</td>
							<td class="px-3 py-1.5 text-right">
								<div class="flex items-center justify-end gap-1">
									{#if proc.status === 'running' || proc.status === 'queued'}
										<button
											class="px-1.5 py-0.5 text-[10px] border border-neon-red/20 text-neon-red hover:bg-neon-red/10 transition-colors"
											onclick={() => handleCancel(proc)}
											title="Cancel"
										>
											<Icon name="x" size={10} />
										</button>
									{/if}
									{#if proc.status === 'completed' && proc.optimizationId}
										<button
											class="px-1.5 py-0.5 text-[10px] border border-neon-cyan/20 text-neon-cyan hover:bg-neon-cyan/10 transition-colors"
											onclick={() => handleOpenResult(proc)}
											title="Open in IDE"
										>
											<Icon name="terminal" size={10} />
										</button>
									{/if}
									{#if proc.status === 'error' && proc.optimizationId}
										<button
											class="px-1.5 py-0.5 text-[10px] border border-neon-yellow/20 text-neon-yellow hover:bg-neon-yellow/10 transition-colors"
											onclick={() => handleRetry(proc)}
											title="Retry"
										>
											<Icon name="refresh" size={10} />
										</button>
									{/if}
									{#if proc.status !== 'running'}
										<button
											class="px-1.5 py-0.5 text-[10px] border border-text-dim/20 text-text-dim hover:bg-bg-hover transition-colors"
											onclick={() => handleDismiss(proc)}
											title="Dismiss"
										>
											<Icon name="minus" size={10} />
										</button>
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>

	<!-- External (MCP) processes -->
	{#if mcpActivityFeed.activeCalls.length > 0}
		<div class="border-t border-neon-green/10">
			<div class="flex items-center gap-2 px-3 py-1.5">
				<Icon name="activity" size={10} class="text-neon-green" />
				<span class="text-[10px] text-neon-green uppercase tracking-wider">External (MCP)</span>
				<span class="text-[10px] text-text-dim ml-auto">{mcpActivityFeed.activeCalls.length} active</span>
			</div>
			<table class="w-full text-[11px]">
				<tbody>
					{#each mcpActivityFeed.activeCalls as call (call.call_id)}
						<tr class="border-b border-neon-green/5 transition-colors hover:bg-bg-hover">
							<td class="px-3 py-1.5 text-neon-green">{call.tool_name}</td>
							<td class="px-3 py-1.5">
								<span class="text-neon-green uppercase text-[10px] tracking-wider">running</span>
							</td>
							<td class="px-3 py-1.5 text-text-dim">{call.client_id ?? 'MCP client'}</td>
							<td class="px-3 py-1.5">
								{#if call.progress != null}
									<div class="flex items-center gap-2">
										<InlineProgress percent={(call.progress ?? 0) * 100} color="green" class="flex-1 max-w-[80px]" />
										<span class="text-[10px] tabular-nums text-neon-green">
											{Math.round((call.progress ?? 0) * 100)}%
										</span>
									</div>
								{:else}
									<span class="text-[10px] text-text-dim">-</span>
								{/if}
							</td>
							<td class="px-3 py-1.5 tabular-nums text-text-dim text-right">
								{call.message ?? '-'}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	{:else}
	<!-- Jobs table -->
	<div class="flex-1 overflow-y-auto">
		{#if jobsLoading && jobs.length === 0}
			<EmptyState icon="loader" message="Loading jobs..." />
		{:else if jobs.length === 0}
			<EmptyState icon="server" message="No background jobs" />
		{:else}
			<table class="w-full text-[11px]">
				<thead>
					<tr class="border-b border-neon-cyan/10 text-text-dim">
						<th class="px-3 py-1.5 text-left font-normal">ID</th>
						<th class="px-3 py-1.5 text-left font-normal">App</th>
						<th class="px-3 py-1.5 text-left font-normal">Type</th>
						<th class="px-3 py-1.5 text-left font-normal">Status</th>
						<th class="px-3 py-1.5 text-left font-normal">Progress</th>
						<th class="px-3 py-1.5 text-left font-normal">Duration</th>
						<th class="px-3 py-1.5 text-right font-normal">Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each jobs as job (job.id)}
						<tr class="border-b border-neon-cyan/5 transition-colors hover:bg-bg-hover">
							<td class="px-3 py-1.5 text-text-dim font-mono text-[10px]">{job.id.slice(0, 8)}</td>
							<td class="px-3 py-1.5 text-text-secondary">{job.app_id}</td>
							<td class="px-3 py-1.5 text-text-secondary">{job.job_type}</td>
							<td class="px-3 py-1.5">
								<span class="{JOB_STATUS_COLOR[job.status] ?? 'text-text-dim'} uppercase text-[10px] tracking-wider">{job.status}</span>
							</td>
							<td class="px-3 py-1.5">
								{#if job.status === 'running'}
									<div class="flex items-center gap-2">
										<InlineProgress percent={job.progress * 100} class="flex-1 max-w-[80px]" />
										<span class="text-[10px] tabular-nums text-neon-cyan">{Math.round(job.progress * 100)}%</span>
									</div>
								{:else if job.status === 'failed'}
									<span class="text-[10px] text-neon-red truncate max-w-[120px] inline-block" title={job.error ?? ''}>
										{job.error ?? 'Error'}
									</span>
								{:else if job.status === 'completed'}
									<span class="text-[10px] text-neon-cyan">done</span>
								{:else}
									<span class="text-[10px] text-text-dim">-</span>
								{/if}
							</td>
							<td class="px-3 py-1.5 tabular-nums text-text-secondary">{formatJobDuration(job)}</td>
							<td class="px-3 py-1.5 text-right">
								{#if job.status === 'pending' || job.status === 'running'}
									<button
										class="px-1.5 py-0.5 text-[10px] border border-neon-red/20 text-neon-red hover:bg-neon-red/10 transition-colors"
										onclick={() => handleCancelJob(job.id)}
										title="Cancel"
									>
										<Icon name="x" size={10} />
									</button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>
	{/if}

	<!-- Footer: scheduler config + token usage -->
	<div class="flex items-center gap-4 border-t border-neon-cyan/10 px-3 py-1.5">
		<span class="text-[10px] text-text-dim">Max concurrent:</span>
		<span class="text-[10px] text-text-secondary tabular-nums">{processScheduler.maxConcurrent}</span>
		{#if Object.keys(providerState.tokenBudgets).length > 0}
			{@const totalTokens = Object.values(providerState.tokenBudgets).reduce((sum, b) => sum + b.total_tokens_used, 0)}
			<div class="h-3 w-px bg-border-subtle"></div>
			<span class="text-[10px] text-text-dim">Tokens: <span class="text-text-secondary tabular-nums">{totalTokens.toLocaleString()}</span></span>
		{/if}
		<span class="text-[10px] text-text-dim ml-auto">
			{#if processScheduler.rateLimitedUntil > Date.now()}
				Rate limited
			{:else if processScheduler.queue.length > 0}
				Next: PID {processScheduler.queue[0].pid}
			{:else}
				Scheduler idle
			{/if}
		</span>
	</div>
</div>
