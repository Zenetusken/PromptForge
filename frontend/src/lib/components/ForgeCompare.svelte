<script lang="ts">
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { optimizationState, mapToResultState, type OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { fetchOptimization } from '$lib/api/client';
	import { normalizeScore, getScoreBadgeClass } from '$lib/utils/format';
	import ForgeScoreDelta from './ForgeScoreDelta.svelte';
	import ForgeCompareActions from './ForgeCompareActions.svelte';
	import Icon from './Icon.svelte';

	// Resolve slot data from resultHistory by ID, with async server fallback
	function resolveSlotSync(id: string | null): OptimizationResultState | null {
		if (!id) return null;
		return optimizationState.resultHistory.find((r) => r.id === id) ?? null;
	}

	// Async-fetched fallback slots (populated when resultHistory misses)
	let fetchedSlotA: OptimizationResultState | null = $state(null);
	let fetchedSlotB: OptimizationResultState | null = $state(null);
	let loadingSlotA = $state(false);
	let loadingSlotB = $state(false);
	let errorSlotA = $state(false);
	let errorSlotB = $state(false);

	let slotA = $derived(resolveSlotSync(forgeMachine.comparison.slotA) ?? fetchedSlotA);
	let slotB = $derived(resolveSlotSync(forgeMachine.comparison.slotB) ?? fetchedSlotB);

	/** Fetch a comparison slot from the server when not in resultHistory cache.
	 *  Staleness guards prevent writes from outdated requests. */
	function fetchSlotIfMissing(
		slotKey: 'slotA' | 'slotB',
		setFetched: (v: OptimizationResultState | null) => void,
		setLoading: (v: boolean) => void,
		setError: (v: boolean) => void,
	) {
		const id = forgeMachine.comparison[slotKey];
		setError(false);
		if (!id) { setFetched(null); setLoading(false); return; }
		if (!resolveSlotSync(id)) {
			setFetched(null);
			setLoading(true);
			fetchOptimization(id).then(item => {
				if (forgeMachine.comparison[slotKey] !== id) return;
				if (item) setFetched(mapToResultState({ ...item }, item.raw_prompt));
			}).catch(() => {
				if (forgeMachine.comparison[slotKey] !== id) return;
				setError(true);
			}).finally(() => {
				if (forgeMachine.comparison[slotKey] === id) setLoading(false);
			});
		}
	}

	// Fetch missing slots from server (guards against stale async responses)
	$effect(() => fetchSlotIfMissing('slotA', v => fetchedSlotA = v, v => loadingSlotA = v, v => errorSlotA = v));
	$effect(() => fetchSlotIfMissing('slotB', v => fetchedSlotB = v, v => loadingSlotB = v, v => errorSlotB = v));

	let hasBothSlots = $derived(slotA !== null && slotB !== null);

	// Prompt text tab state for each slot
	let viewingA = $state<'optimized' | 'original'>('optimized');
	let viewingB = $state<'optimized' | 'original'>('optimized');
</script>

{#if hasBothSlots && slotA && slotB}
	<div class="flex flex-1 flex-col overflow-hidden" data-testid="forge-compare">
		<!-- Header -->
		<div class="flex items-center gap-2 px-2 py-1.5 border-b border-neon-cyan/8">
			<Icon name="layers" size={12} class="text-neon-purple shrink-0" />
			<span class="text-[10px] font-bold uppercase tracking-wider text-text-primary">Compare</span>
			<div class="flex-1"></div>
			<button
				onclick={() => windowManager.minimizeWindow('ide')}
				class="text-[9px] text-text-dim hover:text-text-primary transition-colors"
				aria-label="Minimize to taskbar"
			>
				<Icon name="minimize-2" size={12} />
			</button>
			<button
				onclick={() => forgeMachine.back()}
				class="text-[9px] text-text-dim hover:text-neon-cyan transition-colors"
			>
				Close
			</button>
		</div>

		<!-- Two-column layout -->
		<div class="flex flex-1 overflow-hidden">
			<!-- Slot A (reference) -->
			<div class="flex-1 flex flex-col border-r border-neon-cyan/8 overflow-hidden">
				<div class="flex items-center gap-1.5 px-2 py-1.5 bg-bg-primary/30 border-b border-neon-cyan/5">
					<span class="text-[8px] font-bold uppercase tracking-wider text-text-dim">A — Reference</span>
					{#if slotA.scores.overall}
						<span class="ml-auto score-circle score-circle-xs {getScoreBadgeClass(slotA.scores.overall)}">
							{normalizeScore(slotA.scores.overall)}
						</span>
					{/if}
				</div>
				{#if slotA.strategy}
					<div class="px-2 py-1 border-b border-neon-cyan/5">
						<span class="rounded-sm bg-neon-green/10 border border-neon-green/20 px-1 py-0.5 text-[7px] font-bold uppercase tracking-wider text-neon-green">
							{slotA.strategy}
						</span>
					</div>
				{/if}
				<!-- Tab toggle -->
				<div class="flex border-b border-neon-cyan/5">
					<button
						class="flex-1 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider {viewingA === 'optimized' ? 'text-neon-cyan bg-neon-cyan/5' : 'text-text-dim'}"
						onclick={() => (viewingA = 'optimized')}
					>Opt</button>
					<button
						class="flex-1 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider {viewingA === 'original' ? 'text-text-secondary bg-bg-hover/30' : 'text-text-dim'}"
						onclick={() => (viewingA = 'original')}
					>Orig</button>
				</div>
				<div class="flex-1 overflow-y-auto px-2 py-1.5">
					<pre class="whitespace-pre-wrap font-mono text-[9px] leading-snug text-text-primary">{viewingA === 'optimized' ? slotA.optimized : slotA.original}</pre>
				</div>
			</div>

			<!-- Slot B (candidate) -->
			<div class="flex-1 flex flex-col overflow-hidden">
				<div class="flex items-center gap-1.5 px-2 py-1.5 bg-bg-primary/30 border-b border-neon-cyan/5">
					<span class="text-[8px] font-bold uppercase tracking-wider text-neon-cyan">B — Current</span>
					{#if slotB.scores.overall}
						<span class="ml-auto score-circle score-circle-xs {getScoreBadgeClass(slotB.scores.overall)}">
							{normalizeScore(slotB.scores.overall)}
						</span>
					{/if}
				</div>
				{#if slotB.strategy}
					<div class="px-2 py-1 border-b border-neon-cyan/5">
						<span class="rounded-sm bg-neon-green/10 border border-neon-green/20 px-1 py-0.5 text-[7px] font-bold uppercase tracking-wider text-neon-green">
							{slotB.strategy}
						</span>
					</div>
				{/if}
				<!-- Tab toggle -->
				<div class="flex border-b border-neon-cyan/5">
					<button
						class="flex-1 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider {viewingB === 'optimized' ? 'text-neon-cyan bg-neon-cyan/5' : 'text-text-dim'}"
						onclick={() => (viewingB = 'optimized')}
					>Opt</button>
					<button
						class="flex-1 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider {viewingB === 'original' ? 'text-text-secondary bg-bg-hover/30' : 'text-text-dim'}"
						onclick={() => (viewingB = 'original')}
					>Orig</button>
				</div>
				<div class="flex-1 overflow-y-auto px-2 py-1.5">
					<pre class="whitespace-pre-wrap font-mono text-[9px] leading-snug text-text-primary">{viewingB === 'optimized' ? slotB.optimized : slotB.original}</pre>
				</div>
			</div>
		</div>

		<!-- Score delta -->
		<div class="px-2 py-1.5 border-t border-neon-cyan/8">
			<span class="text-[8px] uppercase tracking-wider text-text-dim/50 font-bold mb-1 block">Score Delta (B − A)</span>
			<ForgeScoreDelta scoresA={slotA.scores} scoresB={slotB.scores} />
		</div>

		<!-- Actions -->
		<ForgeCompareActions {slotA} {slotB} />
	</div>
{:else if loadingSlotA || loadingSlotB}
	<!-- Loading: fetching slot data from server -->
	<div class="flex flex-1 flex-col items-center justify-center p-4 gap-3" data-testid="forge-compare-loading">
		<Icon name="spinner" size={20} class="text-neon-purple animate-spin" />
		<p class="text-[11px] text-text-dim text-center">Loading comparison data...</p>
	</div>
{:else if errorSlotA || errorSlotB}
	<!-- Error: fetch failed -->
	<div class="flex flex-1 flex-col items-center justify-center p-4 gap-3" data-testid="forge-compare-error">
		<div class="flex h-10 w-10 items-center justify-center rounded-full bg-neon-red/10">
			<Icon name="alert-triangle" size={20} class="text-neon-red" />
		</div>
		<p class="text-[11px] text-text-dim text-center">Failed to load comparison data</p>
		<button
			onclick={() => forgeMachine.back()}
			class="text-[10px] text-neon-cyan hover:text-neon-cyan/80 transition-colors"
		>
			Back to review
		</button>
	</div>
{:else}
	<!-- Fallback: missing slot data -->
	<div class="flex flex-1 flex-col items-center justify-center p-4 gap-3" data-testid="forge-compare-empty">
		<div class="flex h-10 w-10 items-center justify-center rounded-full bg-neon-purple/10">
			<Icon name="layers" size={20} class="text-neon-purple" />
		</div>
		<p class="text-[11px] text-text-dim text-center">No comparison data available</p>
		<button
			onclick={() => forgeMachine.back()}
			class="text-[10px] text-neon-cyan hover:text-neon-cyan/80 transition-colors"
		>
			Back to compose
		</button>
	</div>
{/if}

<style>
	.score-circle-xs {
		width: 22px;
		height: 22px;
		font-size: 8px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 9999px;
		font-weight: 700;
		font-family: ui-monospace, monospace;
	}
</style>
