<script lang="ts">
	import { optimizationState, type OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { forgeSession, createEmptyDraft } from '$lib/stores/forgeSession.svelte';
	import { normalizeScore, getScoreBadgeClass, formatScore } from '$lib/utils/format';
	import { getStrategyColor } from '$lib/utils/strategies';
	import { reforge, chainForge, iterate, type ForgeActionStores } from '$lib/utils/forgeActions';
	import { ALL_DIMENSIONS, DIMENSION_LABELS, DIMENSION_COLORS } from '$lib/utils/scoreDimensions';
	import { historyState } from '$lib/stores/history.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import Icon from './Icon.svelte';
	import CopyButton from './CopyButton.svelte';
	import ConfirmModal from './ConfirmModal.svelte';
	import ForgeIterationTimeline from './ForgeIterationTimeline.svelte';
	import ContextSnapshotPanel from './ContextSnapshotPanel.svelte';
	import ForgeContents from './ForgeContents.svelte';
	import PromptAnatomyHUD from './PromptAnatomyHUD.svelte';
	import ExtensionSlot from '$lib/kernel/components/ExtensionSlot.svelte';

	let result = $derived(optimizationState.forgeResult);

	let activeTab = $state<'optimized' | 'original'>('optimized');

	// Find previous result for comparison (second item in history, since first is current)
	let previousResult = $derived.by(() => {
		if (!result) return null;
		const history = optimizationState.resultHistory;
		const idx = history.findIndex((r) => r.id === result!.id);
		// Return the next item (older) if available
		return idx >= 0 && idx + 1 < history.length ? history[idx + 1] : null;
	});

	const forgeActionStores: ForgeActionStores = { optimizationState, forgeSession, forgeMachine };

	function handleCompareWithPrevious() {
		if (!result || !previousResult) return;
		const prev = previousResult;
		forgeMachine.compare(prev.id, result.id);
	}

	function handleCompareWith(target: OptimizationResultState) {
		if (!result) return;
		forgeMachine.compare(target.id, result.id);
	}

	let confirmDeleteOpen = $state(false);

	async function handleDeleteForge() {
		if (!result) return;
		const id = result.id;
		const ok = await historyState.removeEntry(id);
		confirmDeleteOpen = false;
		if (ok) {
			if (optimizationState.forgeResult?.id === id) optimizationState.forgeResult = null;
			optimizationState.resultHistory = optimizationState.resultHistory.filter(r => r.id !== id);
			// Reset the active tab so stale result content doesn't persist in sessionStorage
			const tab = forgeSession.activeTab;
			tab.resultId = null;
			tab.mode = 'compose';
			tab.document = null;
			tab.draft = createEmptyDraft();
			tab.name = 'Untitled';
			tab.originalText = '';
			forgeMachine.back();
			forgeSession.persistTabs();
			systemBus.emit('history:reload', 'forgeReview', {});
			systemBus.emit('stats:reload', 'forgeReview', {});
			toastState.show('Forge entry deleted', 'success');
		} else {
			toastState.show('Failed to delete forge entry', 'error');
		}
	}

</script>

{#if result}
	<div class="flex flex-1 flex-col overflow-y-auto" data-testid="forge-review">
		<!-- Score header -->
		<div class="px-3 pt-2.5 pb-2">
			<div class="flex items-center gap-2 mb-1.5">
				{#if result.scores.overall}
					<span class="score-circle score-circle-sm {getScoreBadgeClass(result.scores.overall)}">
						{normalizeScore(result.scores.overall)}
					</span>
				{/if}
				<div class="min-w-0 flex-1">
					<h3 class="truncate text-[11px] font-semibold text-text-primary">
						{result.title || 'Optimization complete'}
					</h3>
					<div class="flex items-center gap-1.5 mt-0.5">
						{#if result.strategy}
							{@const sColors = getStrategyColor(result.strategy)}
							<span
								class="rounded-sm px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider {sColors.text}"
								style="background: {sColors.rawRgba.replace('0.35', '0.10')}; border: 1px solid {sColors.rawRgba.replace('0.35', '0.20')};"
							>
								{result.strategy}
							</span>
						{/if}
						{#if result.strategy_confidence}
							<span class="font-mono text-[9px] {result.strategy_confidence >= 0.8 ? 'text-neon-green' : result.strategy_confidence >= 0.6 ? 'text-neon-yellow' : 'text-neon-red'}">
								{Math.round(result.strategy_confidence * 100)}%
							</span>
						{/if}
					</div>
				</div>
				<button
					onclick={() => windowManager.minimizeWindow('ide')}
					class="shrink-0 text-text-dim hover:text-text-primary transition-colors"
					aria-label="Minimize to taskbar"
				>
					<Icon name="minimize-2" size={12} />
				</button>
			</div>

			<!-- Score breakdown bars -->
			<div class="space-y-1">
				{#each ALL_DIMENSIONS as dim}
					{@const score = result.scores[dim]}
					{@const normalized = normalizeScore(score)}
					<div class="flex items-center gap-1.5">
						<span class="w-16 text-[9px] font-medium text-text-dim truncate">{DIMENSION_LABELS[dim]}</span>
						<div class="flex-1 h-1.5 rounded-full bg-bg-primary/60 overflow-hidden">
							<div
								class="h-full rounded-full transition-[width] duration-500"
								style="width: {normalized ?? 0}%; background-color: var(--color-{DIMENSION_COLORS[dim]})"
							></div>
						</div>
						<span
							class="w-5 text-right font-mono text-[9px] font-medium"
							style="color: var(--color-{DIMENSION_COLORS[dim]})"
						>{formatScore(score)}</span>
					</div>
				{/each}
			</div>
		</div>

		<!-- Tabs with sliding indicator -->
		<div class="relative flex border-y border-white/[0.06]">
			<button
				class="flex-1 px-2 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-colors {activeTab === 'optimized' ? 'text-neon-cyan' : 'text-text-dim hover:text-text-secondary'}"
				onclick={() => (activeTab = 'optimized')}
			>
				Optimized
			</button>
			<button
				class="flex-1 px-2 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-colors {activeTab === 'original' ? 'text-text-secondary' : 'text-text-dim hover:text-text-secondary'}"
				onclick={() => (activeTab = 'original')}
			>
				Original
			</button>
			<!-- Sliding underline indicator -->
			<div
				class="absolute bottom-0 h-px transition-all duration-200 ease-out"
				style="left: {activeTab === 'optimized' ? '0%' : '50%'}; width: 50%; background-color: {activeTab === 'optimized' ? 'var(--color-neon-cyan)' : 'var(--color-text-secondary)'};"
			></div>
		</div>

		<!-- Content well -->
		<div class="flex-1 overflow-y-auto p-2">
			<div class="rounded-md border border-white/[0.04] bg-bg-primary/40 p-3">
				<pre class="whitespace-pre-wrap font-mono text-[13px] leading-relaxed text-text-primary selection:bg-neon-cyan/20">{activeTab === 'optimized' ? result.optimized : result.original}</pre>
			</div>
		</div>

		<!-- Strategy reasoning (collapsible) -->
		{#if result.strategy_reasoning}
			<div class="border-t border-white/[0.06]">
				<details class="group">
					<summary class="flex items-center gap-1.5 px-3 py-1.5 cursor-pointer text-[10px] text-text-dim hover:text-text-secondary transition-colors select-none">
						<Icon name="chevron-right" size={10} class="shrink-0 transition-transform group-open:rotate-90" />
						<Icon name="info" size={10} class="shrink-0 text-neon-purple/60" />
						<span class="font-bold uppercase tracking-wider">Strategy Reasoning</span>
					</summary>
					<div class="px-3 pb-2">
						<div class="rounded-md border border-white/[0.04] bg-bg-primary/30 p-2.5">
							<p class="text-[11px] text-text-secondary leading-relaxed">{result.strategy_reasoning}</p>
						</div>
					</div>
				</details>
			</div>
		{/if}

		<!-- Verdict (callout bar) -->
		{#if result.verdict}
			<div class="border-t border-white/[0.06]">
				<details class="group">
					<summary class="flex items-center gap-1.5 px-3 py-1.5 cursor-pointer text-[10px] text-text-dim hover:text-text-secondary transition-colors select-none">
						<Icon name="chevron-right" size={10} class="shrink-0 transition-transform group-open:rotate-90" />
						<Icon name="check" size={10} class="shrink-0 text-neon-green/60" />
						<span class="font-bold uppercase tracking-wider">Verdict</span>
					</summary>
					<div class="px-3 pb-2">
						<div class="border-l border-neon-cyan/30 pl-2.5 py-0.5">
							<p class="text-[11px] italic text-text-secondary leading-relaxed">{result.verdict}</p>
						</div>
					</div>
				</details>
			</div>
		{/if}

		<!-- Prompt Anatomy (collapsible) -->
		{#if result.detected_sections?.length || result.detected_variables?.length}
			<div class="border-t border-white/[0.06]">
				<details class="group">
					<summary class="flex items-center gap-1.5 px-3 py-1.5 cursor-pointer text-[10px] text-text-dim hover:text-text-secondary transition-colors select-none">
						<Icon name="chevron-right" size={10} class="shrink-0 transition-transform group-open:rotate-90" />
						<Icon name="cpu" size={10} class="shrink-0 text-neon-yellow/60" />
						<span class="font-bold uppercase tracking-wider">Prompt Anatomy</span>
					</summary>
					<div class="px-3 pb-2">
						<PromptAnatomyHUD
							sections={result.detected_sections.map(s => ({ label: s.label, lineNumber: s.line_number, type: s.type }))}
							variables={result.detected_variables}
							mode="review"
						/>
					</div>
				</details>
			</div>
		{/if}

		<!-- Project context snapshot (collapsible) -->
		{#if result.codebase_context_snapshot}
			<ContextSnapshotPanel context={result.codebase_context_snapshot} />
		{/if}

		<!-- Forge sub-artifact contents -->
		<ForgeContents {result} />

		<!-- Iteration timeline -->
		<ForgeIterationTimeline
			currentId={result.id}
			onselect={(target) => handleCompareWith(target)}
		/>

		<!-- Actions (sticky bottom bar) -->
		<div class="shrink-0 border-t border-white/[0.06] bg-bg-secondary px-3 py-2 flex flex-wrap gap-1.5">
			<CopyButton text={result.optimized} />
			<span class="w-px h-4 bg-white/[0.08] self-center"></span>
			<button
				onclick={() => iterate(forgeActionStores)}
				class="forge-action-btn"
				aria-label="Load optimized text into composer"
			>
				<Icon name="edit" size={10} />
				Iterate
			</button>
			<button
				onclick={() => reforge(forgeActionStores)}
				class="forge-action-btn"
				aria-label="Re-forge with different settings"
			>
				<Icon name="refresh" size={10} />
				Re-forge
			</button>
			<button
				onclick={() => chainForge(forgeActionStores)}
				class="forge-action-btn text-neon-orange/80 hover:text-neon-orange hover:border-neon-orange/30 hover:bg-neon-orange/5"
				aria-label="Use optimized output as new input"
			>
				<Icon name="git-branch" size={10} />
				Chain
			</button>
			{#if optimizationState.resultHistory.length > 1}
				<span class="w-px h-4 bg-white/[0.08] self-center"></span>
				<button
					onclick={handleCompareWithPrevious}
					class="forge-action-btn {!previousResult ? 'opacity-40 cursor-not-allowed' : ''}"
					disabled={!previousResult}
					aria-label="Compare with previous iteration"
				>
					<Icon name="layers" size={10} />
					Compare
				</button>
			{/if}
			<!-- Extension point: apps can inject actions here -->
			<ExtensionSlot
				slotId="promptforge:review-actions"
				context={{ resultId: result.id, optimizedPrompt: result.optimized }}
			/>
			<span class="w-px h-4 bg-white/[0.08] self-center"></span>
			<button
				onclick={() => (confirmDeleteOpen = true)}
				class="forge-action-btn text-neon-red/60 hover:text-neon-red hover:border-neon-red/30 hover:bg-neon-red/5"
				aria-label="Delete forge result"
			>
				<Icon name="trash-2" size={10} />
				Delete
			</button>
		</div>
	</div>
{:else}
	<div class="flex flex-1 items-center justify-center p-4">
		<p class="text-[11px] text-text-dim">No result to review</p>
	</div>
{/if}

<ConfirmModal
	bind:open={confirmDeleteOpen}
	title="Delete Forge"
	variant="danger"
	message="Permanently delete this forge result? This cannot be undone."
	onconfirm={handleDeleteForge}
/>

