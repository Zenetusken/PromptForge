<script lang="ts">
	import { forgeSession, createEmptyDraft } from '$lib/stores/forgeSession.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptAnalysis } from '$lib/stores/promptAnalysis.svelte';
	import ForgeEditor from './ForgeEditor.svelte';
	import Icon from './Icon.svelte';
	import { Tooltip, MetaBadge } from './ui';

	function exitIDE() {
		forgeSession.isActive = false;
		forgeMachine.reset();
	}

	function switchTab(id: string) {
		forgeSession.activeTabId = id;
	}

	function closeTab(id: string, e: MouseEvent) {
		e.stopPropagation();
		if (forgeSession.tabs.length <= 1) {
			forgeSession.reset();
			return;
		}
		const idx = forgeSession.tabs.findIndex(t => t.id === id);
		forgeSession.tabs = forgeSession.tabs.filter(t => t.id !== id);
		if (forgeSession.activeTabId === id) {
			forgeSession.activeTabId = forgeSession.tabs[Math.max(0, idx - 1)].id;
		}
	}

	function newTab() {
		const tab = { id: crypto.randomUUID(), name: 'Untitled', draft: createEmptyDraft() };
		forgeSession.tabs.push(tab);
		forgeSession.activeTabId = tab.id;
	}

	function handleSubmit(): boolean {
		if (!forgeSession.hasText || optimizationState.isRunning) return false;
		if (!forgeSession.validate()) {
			forgeSession.showMetadata = true;
			return false;
		}
		optimizationState.startOptimization(
			forgeSession.draft.text,
			forgeSession.buildMetadata(),
		);
		forgeMachine.forge();
		return true;
	}

	let wordCount = $derived(forgeSession.draft.text.trim() ? forgeSession.draft.text.trim().split(/\s+/).length : 0);
	let modKey = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.userAgent) ? '⌘' : 'Ctrl+';

	// Sync tab name with draft title
	$effect(() => {
		const title = forgeSession.draft.title.trim();
		if (title && forgeSession.activeTab.name !== title) {
			forgeSession.activeTab.name = title;
		}
	});
</script>

<div class="flex flex-1 flex-col overflow-hidden bg-bg-primary">
	<!-- Tab Bar -->
	<div class="flex h-9 shrink-0 items-center border-b border-neon-cyan/10 bg-bg-secondary px-2">
		{#each forgeSession.tabs as tab}
			<button
				onclick={() => switchTab(tab.id)}
				class="group flex h-full items-center gap-2 border-b-2 px-3 text-xs transition-colors {tab.id === forgeSession.activeTabId ? 'border-neon-cyan text-text-primary bg-bg-primary' : 'border-transparent text-text-dim hover:bg-bg-hover hover:text-text-secondary'}"
			>
				<Icon name="file-text" size={12} class={tab.id === forgeSession.activeTabId ? "text-neon-cyan" : ""} />
				<span class="max-w-[120px] truncate">{tab.name || tab.draft.title || 'Untitled'}</span>
				<div
					role="button"
					tabindex="0"
					onclick={(e) => closeTab(tab.id, e)}
					onkeydown={(e) => e.key === 'Enter' && closeTab(tab.id, e as any)}
					class="rounded-sm p-0.5 opacity-0 hover:bg-bg-input group-hover:opacity-100 transition-opacity"
				>
					<Icon name="x" size={10} />
				</div>
			</button>
		{/each}
		<button onclick={newTab} class="ml-1 flex h-6 w-6 items-center justify-center rounded hover:bg-bg-hover text-text-dim transition-colors" title="New Prompt">
			<Icon name="plus" size={14} />
		</button>
		<div class="ml-auto flex items-center">
			<Tooltip text="Back to dashboard (Esc)" side="bottom">
				<button
					onclick={exitIDE}
					class="flex h-6 items-center gap-1 rounded px-1.5 text-[10px] font-medium text-text-dim transition-colors hover:bg-bg-hover hover:text-text-secondary"
					aria-label="Close IDE workspace"
					data-testid="ide-exit-btn"
				>
					<Icon name="x" size={12} />
				</button>
			</Tooltip>
		</div>
	</div>

	<!-- Editor Area -->
	<div class="relative flex-1 bg-bg-input p-4 sm:p-6 overflow-hidden flex flex-col">
		<div class="flex-1 rounded-lg border border-neon-cyan/10 bg-bg-secondary p-1 shadow-inner relative flex flex-col">
			<ForgeEditor variant="focus" onsubmit={handleSubmit} />
		</div>
	</div>

	<!-- Status Bar -->
	<div class="flex h-6 shrink-0 items-center justify-between border-t border-neon-cyan/10 bg-bg-secondary px-3 text-[10px] text-text-dim">
		<span class="font-mono tabular-nums">{forgeSession.charCount} chars · {wordCount} words</span>
		<span>
			{#if promptAnalysis.heuristic}
				<MetaBadge type="task" value={promptAnalysis.heuristic.taskType} size="xs" />
			{/if}
		</span>
		<span class="font-mono text-text-dim/40">
			{#if forgeMachine.mode === 'compose'}{modKey}⏎ forge{/if}
		</span>
	</div>
</div>
