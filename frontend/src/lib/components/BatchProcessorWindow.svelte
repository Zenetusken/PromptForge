<script lang="ts">
	import { fetchOptimize } from '$lib/api/client';
	import { processScheduler } from '$lib/stores/processScheduler.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { settingsState } from '$lib/stores/settings.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { ALL_STRATEGIES } from '$lib/utils/strategies';
	import { safeNumber } from '$lib/utils/safe';
	import { InlineProgress, StatusDot } from './ui';

	type BatchItemStatus = 'pending' | 'queued' | 'running' | 'completed' | 'error';

	interface BatchItem {
		id: string;
		prompt: string;
		strategy: string;
		status: BatchItemStatus;
		score: number | null;
		error: string | null;
		optimizationId: string | null;
		processId: string | null;
	}

	let items: BatchItem[] = $state([]);
	let bulkText = $state('');
	let strategy = $state(settingsState.defaultStrategy);
	let isRunning = $state(false);

	const strategies = ['', ...ALL_STRATEGIES];

	let completedCount = $derived(items.filter(i => i.status === 'completed').length);
	let errorCount = $derived(items.filter(i => i.status === 'error').length);
	let finishedCount = $derived(completedCount + errorCount);
	let avgScore = $derived.by(() => {
		const scores = items.filter(i => i.score != null).map(i => i.score!);
		if (scores.length === 0) return null;
		return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10;
	});

	// Track batch group for bus event correlation
	let batchGroupId = $state('');

	function parsePrompts() {
		const lines = bulkText
			.split(/\n---\n|\n\n/)
			.map(l => l.trim())
			.filter(l => l.length > 0);

		items = lines.slice(0, 20).map((prompt) => ({
			id: crypto.randomUUID(),
			prompt,
			strategy,
			status: 'pending' as BatchItemStatus,
			score: null,
			error: null,
			optimizationId: null,
			processId: null,
		}));
	}

	function runBatch() {
		const pending = items.filter(i => i.status === 'pending' || i.status === 'error');
		if (pending.length === 0 || isRunning) return;
		isRunning = true;
		batchGroupId = crypto.randomUUID();

		for (const item of pending) {
			const meta = {
				strategy: strategy || undefined,
				tags: ['batch'],
			};

			const proc = processScheduler.spawn({
				title: `Batch: ${item.prompt.slice(0, 40)}`,
				priority: 'batch' as const,
				promptHash: batchGroupId,
				metadata: meta,
				onExecute: () => {
					item.status = 'running';
					items = [...items];

					fetchOptimize(
						item.prompt,
						(event) => {
							if (event.type === 'result') {
								const data = event.data || {};
								item.status = 'completed';
								item.score = safeNumber(data.overall_score) ? Math.round(safeNumber(data.overall_score) * 10) : null;
								item.optimizationId = (data.id as string) ?? null;
								items = [...items];
								processScheduler.complete(proc.id, {
									score: item.score,
									strategy: (data.strategy as string) ?? null,
									optimizationId: item.optimizationId,
								});
								checkBatchDone();
							} else if (event.type === 'error') {
								item.status = 'error';
								item.error = event.error ?? 'Failed';
								items = [...items];
								processScheduler.fail(proc.id, item.error ?? undefined);
								checkBatchDone();
							}
						},
						(err) => {
							item.status = 'error';
							item.error = err.message;
							items = [...items];
							processScheduler.fail(proc.id, err.message);
							checkBatchDone();
						},
						meta,
						providerState.getLLMHeaders()
					);
				},
			});

			item.processId = proc.id;
			item.status = proc.status === 'running' ? 'running' : 'queued';
		}
		items = [...items];
	}

	function checkBatchDone() {
		const allDone = items.every(i => i.status === 'completed' || i.status === 'error' || i.status === 'pending');
		if (allDone) {
			isRunning = false;
		}
	}

	function cancelBatch() {
		for (const item of items) {
			if (item.processId && (item.status === 'running' || item.status === 'queued')) {
				const proc = processScheduler.findById(item.processId);
				if (proc) processScheduler.cancel(proc.pid);
				item.status = 'error';
				item.error = 'Cancelled';
			}
		}
		items = [...items];
		isRunning = false;
	}

	function clearBatch() {
		items = [];
		bulkText = '';
		isRunning = false;
	}

	function exportResults() {
		const data = items
			.filter(i => i.status === 'completed')
			.map(i => ({
				prompt: i.prompt.slice(0, 200),
				score: i.score,
				strategy: i.strategy || 'auto',
				optimization_id: i.optimizationId,
			}));

		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `batch-results-${Date.now()}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}

	const STATUS_COLOR: Record<BatchItemStatus, string> = {
		pending: 'text-text-dim',
		queued: 'text-neon-yellow',
		running: 'text-neon-yellow',
		completed: 'text-neon-green',
		error: 'text-neon-red',
	};
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	{#if items.length === 0}
		<!-- Input mode -->
		<div class="flex-1 p-3 space-y-3">
			<h3 class="section-heading">Batch Processor</h3>
			<p class="text-[11px] text-text-secondary">
				Enter multiple prompts separated by blank lines or <code class="text-neon-cyan">---</code>. Max 20 prompts.
			</p>
			<textarea
				id="batch-prompts"
				aria-label="Batch prompts"
				class="w-full h-48 bg-bg-input border border-neon-cyan/10 text-xs text-text-primary p-3 outline-none resize-none focus:border-neon-cyan/30 font-mono"
				placeholder="First prompt here...

Second prompt here...

---

Third prompt here..."
				bind:value={bulkText}
			></textarea>
			<div class="flex items-center gap-3">
				<label class="flex items-center gap-2">
					<span class="text-[11px] text-text-secondary">Strategy:</span>
					<select
						id="batch-strategy"
						class="bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1 outline-none focus:border-neon-cyan/30"
						bind:value={strategy}
					>
						{#each strategies as s (s)}
							<option value={s}>{s || 'Auto-select'}</option>
						{/each}
					</select>
				</label>
				<button
					class="ml-auto border border-neon-cyan/20 px-3 py-1.5 text-[11px] text-neon-cyan hover:bg-neon-cyan/10 transition-colors disabled:opacity-30"
					onclick={parsePrompts}
					disabled={!bulkText.trim()}
				>
					Parse Prompts
				</button>
			</div>
		</div>
	{:else}
		<!-- Progress mode -->
		<div class="flex items-center gap-4 border-b border-neon-cyan/10 px-3 py-2">
			<span class="text-[11px] text-text-secondary">{items.length} prompts</span>
			<span class="text-[11px] text-neon-green">{completedCount} done</span>
			{#if errorCount > 0}
				<span class="text-[11px] text-neon-red">{errorCount} failed</span>
			{/if}
			{#if avgScore != null}
				<span class="text-[11px] text-neon-cyan">avg {avgScore}/10</span>
			{/if}

			<div class="flex items-center gap-2 ml-auto">
				{#if !isRunning && completedCount > 0}
					<button
						class="border border-neon-cyan/20 px-2 py-1 text-[10px] text-neon-cyan hover:bg-neon-cyan/10 transition-colors"
						onclick={exportResults}
					>
						Export JSON
					</button>
				{/if}
				{#if isRunning}
					<button
						class="border border-neon-red/20 px-2 py-1 text-[10px] text-neon-red hover:bg-neon-red/10 transition-colors"
						onclick={cancelBatch}
					>
						Cancel
					</button>
				{:else}
					<button
						class="border border-text-dim/20 px-2 py-1 text-[10px] text-text-dim hover:bg-bg-hover transition-colors"
						onclick={clearBatch}
					>
						Clear
					</button>
					{#if completedCount < items.length}
						<button
							class="border border-neon-cyan/20 px-2 py-1 text-[10px] text-neon-cyan hover:bg-neon-cyan/10 transition-colors"
							onclick={runBatch}
						>
							{completedCount > 0 ? 'Resume' : 'Start'}
						</button>
					{/if}
				{/if}
			</div>
		</div>

		<!-- Overall progress bar -->
		<InlineProgress percent={items.length > 0 ? (finishedCount / items.length * 100) : 0} />

		<!-- Items list -->
		<div class="flex-1 overflow-y-auto">
			{#each items as item, i (item.id)}
				<div class="flex items-center gap-3 px-3 py-2 border-b border-neon-cyan/5">
					<span class="text-[10px] text-text-dim tabular-nums w-5">#{i + 1}</span>
					<span class="text-[11px] text-text-primary flex-1 truncate">{item.prompt.slice(0, 80)}{item.prompt.length > 80 ? '...' : ''}</span>
					<span class="{STATUS_COLOR[item.status]} text-[10px] uppercase tracking-wider w-16 text-right">
						{#if item.status === 'running'}
							<span class="inline-flex items-center gap-1"><StatusDot color="yellow" class="status-dot-pulse" />forging</span>
						{:else}
							{item.status}
						{/if}
					</span>
					{#if item.score != null}
						<span class="text-[10px] text-neon-cyan tabular-nums w-8 text-right">{item.score}/10</span>
					{:else}
						<span class="w-8"></span>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
