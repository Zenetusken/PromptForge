<script lang="ts">
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptAnalysis } from '$lib/stores/promptAnalysis.svelte';
	import { sessionContext } from '$lib/stores/sessionContext.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { saveActiveTabState, restoreTabState } from '$lib/stores/tabCoherence';
	import { ALL_STRATEGIES } from '$lib/utils/strategies';
	import { FILE_EXTENSIONS, ARTIFACT_KINDS } from '$lib/utils/fileTypes';
	import { DRAG_MIME, decodeDragPayload } from '$lib/utils/dragPayload';
	import { openDocument } from '$lib/utils/documentOpener';
	import ForgeEditor from './ForgeEditor.svelte';
	import Icon from './Icon.svelte';
	import { Tooltip, MetaBadge } from './ui';

	let tabBarDropActive = $state(false);

	function handleTabBarDrop(e: DragEvent) {
		tabBarDropActive = false;
		if (!e.dataTransfer) return;
		const raw = e.dataTransfer.getData(DRAG_MIME);
		if (!raw) return;
		const payload = decodeDragPayload(raw);
		if (payload) {
			e.preventDefault();
			openDocument(payload.descriptor);
		}
	}

	function handleTabBarDragOver(e: DragEvent) {
		if (e.dataTransfer?.types.includes(DRAG_MIME)) {
			e.preventDefault();
			e.dataTransfer.dropEffect = 'copy';
			tabBarDropActive = true;
		}
	}

	function handleTabBarDragLeave() {
		tabBarDropActive = false;
	}

	/** Return the icon name for a tab based on its document kind. */
	function tabIconName(tab: typeof forgeSession.tabs[0]): 'file-text' | 'zap' | 'search' | 'activity' | 'sliders' {
		if (tab.document?.kind === 'prompt') return FILE_EXTENSIONS[tab.document.extension].icon as 'file-text';
		if (tab.document?.kind === 'artifact') return ARTIFACT_KINDS[tab.document.artifactKind].icon as 'zap';
		if (tab.document?.kind === 'sub-artifact') return ARTIFACT_KINDS[tab.document.artifactKind].icon as 'search' | 'activity' | 'sliders';
		return 'file-text';
	}

	/** Return the neon color class for a tab icon based on its document kind. */
	function tabIconColor(tab: typeof forgeSession.tabs[0]): string {
		if (tab.document?.kind === 'prompt') return `text-neon-${FILE_EXTENSIONS[tab.document.extension].color}`;
		if (tab.document?.kind === 'artifact' || tab.document?.kind === 'sub-artifact') return `text-neon-${ARTIFACT_KINDS[tab.document.artifactKind].color}`;
		return '';
	}

	/** Return the display name for a tab, appending file extension when a document is attached. */
	function tabDisplayName(tab: typeof forgeSession.tabs[0]): string {
		const base = tab.name || tab.draft.title || 'Untitled';
		if (!tab.document) return base;
		if (tab.document.kind === 'prompt') {
			return base.endsWith('.md') ? base : `${base}.md`;
		}
		if (tab.document.kind === 'artifact') {
			return base.endsWith('.forge') ? base : `${base}.forge`;
		}
		if (tab.document.kind === 'sub-artifact') {
			return tab.document.name;
		}
		return base;
	}

	let showTournament = $state(false);
	let tournamentStrategies: string[] = $state([]);

	// Auto-refine state
	let autoRefine = $state(false);
	let scoreThreshold = $state(7);

	// Session context toggle
	let useSessionContext = $state(false);

	function exitIDE() {
		saveActiveTabState();
		forgeSession.isActive = false;
		forgeMachine.reset();
		windowManager.closeIDE();
	}

	function switchTab(id: string) {
		if (id === forgeSession.activeTabId) return;
		if (forgeMachine.mode === 'forging') return;
		saveActiveTabState();
		forgeSession.activeTabId = id;
		const target = forgeSession.tabs.find(t => t.id === id);
		if (target) restoreTabState(target);
	}

	function closeTab(id: string, e: MouseEvent) {
		e.stopPropagation();
		const isActive = forgeSession.activeTabId === id;
		if (isActive && forgeMachine.mode === 'forging') return;

		if (forgeSession.tabs.length <= 1) {
			optimizationState.resetForge();
			forgeMachine.reset();
			forgeSession.reset();
			return;
		}
		const idx = forgeSession.tabs.findIndex(t => t.id === id);
		forgeSession.tabs = forgeSession.tabs.filter(t => t.id !== id);
		if (isActive) {
			const nextTab = forgeSession.tabs[Math.max(0, idx - 1)];
			forgeSession.activeTabId = nextTab.id;
			restoreTabState(nextTab);
		}
	}

	function newTab() {
		if (forgeMachine.mode === 'forging') return;
		saveActiveTabState();
		const tab = forgeSession.createTab();
		if (tab) restoreTabState(tab);
	}

	function handleSubmit(): boolean {
		if (!forgeSession.hasText || optimizationState.isRunning) return false;
		if (!forgeSession.validate()) {
			forgeSession.showMetadata = true;
			return false;
		}
		const meta = forgeSession.buildMetadata() ?? {};
		if (autoRefine) {
			meta.max_iterations = 3;
			meta.score_threshold = scoreThreshold / 10;
		}
		if (useSessionContext && sessionContext.hasContext) {
			const hint = sessionContext.buildContextHint();
			if (hint) {
				meta.codebase_context = {
					...meta.codebase_context,
					documentation: [meta.codebase_context?.documentation, hint].filter(Boolean).join('\n'),
				};
			}
		}
		optimizationState.startOptimization(
			forgeSession.draft.text,
			Object.keys(meta).length > 0 ? meta : undefined,
		);
		forgeMachine.forge();
		return true;
	}

	function handleTournament() {
		if (!forgeSession.hasText || tournamentStrategies.length < 2) return;
		if (!forgeSession.validate()) {
			forgeSession.showMetadata = true;
			return;
		}
		optimizationState.startTournament(
			forgeSession.draft.text,
			tournamentStrategies,
			forgeSession.buildMetadata(),
		);
		showTournament = false;
	}

	function toggleTournamentStrategy(s: string) {
		if (tournamentStrategies.includes(s)) {
			tournamentStrategies = tournamentStrategies.filter(x => x !== s);
		} else if (tournamentStrategies.length < 4) {
			tournamentStrategies = [...tournamentStrategies, s];
		}
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
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="flex h-7 shrink-0 items-center border-b bg-bg-secondary px-1.5 {tabBarDropActive ? 'border-neon-cyan/40' : 'border-neon-cyan/10'}"
		ondrop={handleTabBarDrop}
		ondragover={handleTabBarDragOver}
		ondragleave={handleTabBarDragLeave}
	>
		{#each forgeSession.tabs as tab (tab.id)}
			<button
				onclick={() => switchTab(tab.id)}
				class="group flex h-full items-center gap-2 border-b-2 px-2 text-[11px] transition-colors {tab.id === forgeSession.activeTabId ? 'border-neon-cyan text-text-primary bg-bg-primary' : 'border-transparent text-text-dim hover:bg-bg-hover hover:text-text-secondary'}"
			>
				<Icon name={tabIconName(tab)} size={12} class={tab.id === forgeSession.activeTabId ? (tabIconColor(tab) || "text-neon-cyan") : ""} />
				<span class="max-w-[120px] truncate">{tabDisplayName(tab)}</span>
				<div
					role="button"
					tabindex="0"
					onclick={(e) => closeTab(tab.id, e)}
					onkeydown={(e) => e.key === 'Enter' && closeTab(tab.id, e as any)}
					class="rounded-sm p-0.5 opacity-0 hover:bg-bg-input group-hover:opacity-100 transition-opacity {tab.id === forgeSession.activeTabId && forgeMachine.mode === 'forging' ? 'pointer-events-none opacity-20' : ''}"
				>
					<Icon name="x" size={10} />
				</div>
			</button>
		{/each}
		<button onclick={newTab} class="ml-1 flex h-5 w-5 items-center justify-center rounded hover:bg-bg-hover text-text-dim transition-colors" title="New Prompt">
			<Icon name="plus" size={12} />
		</button>
		<div class="ml-auto flex items-center">
			<Tooltip text="Back to dashboard (Esc)" side="bottom">
				<button
					onclick={exitIDE}
					class="flex h-5 items-center gap-1 rounded px-1.5 text-[10px] font-medium text-text-dim transition-colors hover:bg-bg-hover hover:text-text-secondary"
					aria-label="Close IDE workspace"
					data-testid="ide-exit-btn"
				>
					<Icon name="x" size={12} />
				</button>
			</Tooltip>
		</div>
	</div>

	<!-- Editor Area -->
	<div class="relative flex-1 bg-bg-input p-1.5 overflow-hidden flex flex-col">
		<div class="flex-1 rounded border border-neon-cyan/10 bg-bg-secondary p-0.5 relative flex flex-col">
			<ForgeEditor variant="focus" onsubmit={handleSubmit} />
		</div>
	</div>

	<!-- Toolbar: Tournament + Auto-refine -->
	{#if forgeMachine.mode === 'compose' && forgeSession.hasText}
		<div class="flex items-center gap-3 border-t border-neon-cyan/10 bg-bg-secondary px-2 py-1">
			<!-- Auto-refine toggle -->
			<label class="flex items-center gap-1.5 cursor-pointer">
				<input
					id="ide-auto-refine"
					type="checkbox"
					class="accent-neon-cyan"
					bind:checked={autoRefine}
				/>
				<span class="text-[10px] text-text-dim">Auto-refine</span>
			</label>
			{#if autoRefine}
				<label class="flex items-center gap-1">
					<span class="text-[10px] text-text-dim">Min score:</span>
					<input
						id="ide-score-threshold"
						type="range"
						min="5"
						max="9"
						class="w-14 h-1 accent-neon-cyan"
						bind:value={scoreThreshold}
					/>
					<span class="text-[10px] text-neon-cyan tabular-nums">{scoreThreshold}/10</span>
				</label>
			{/if}

			{#if sessionContext.hasContext}
				<label class="flex items-center gap-1.5 cursor-pointer">
					<input
						id="ide-session-context"
						type="checkbox"
						class="accent-neon-purple"
						bind:checked={useSessionContext}
					/>
					<span class="text-[10px] text-text-dim">Session context</span>
				</label>
			{/if}

			<div class="ml-auto">
				<Tooltip text="Run multiple strategies in parallel and compare best results">
					<button
						class="flex items-center gap-1 text-[10px] border border-neon-purple/20 text-neon-purple px-2 py-0.5 hover:bg-neon-purple/10 transition-colors"
						onclick={() => showTournament = !showTournament}
					>
						<Icon name="bar-chart" size={10} />
						Tournament
					</button>
				</Tooltip>
			</div>
		</div>

		<!-- Tournament strategy picker -->
		{#if showTournament}
			<div class="border-t border-neon-purple/10 bg-bg-secondary px-2 py-2 space-y-2">
				<div class="text-[10px] text-neon-purple uppercase tracking-wider font-medium">Select 2-4 strategies</div>
				<div class="flex flex-wrap gap-1.5">
					{#each ALL_STRATEGIES as s}
						<button
							class="text-[10px] px-2 py-0.5 border transition-colors {tournamentStrategies.includes(s) ? 'border-neon-purple text-neon-purple bg-neon-purple/10' : 'border-neon-cyan/10 text-text-dim hover:text-text-secondary'}"
							onclick={() => toggleTournamentStrategy(s)}
						>
							{s}
						</button>
					{/each}
				</div>
				<div class="flex items-center gap-2">
					<button
						class="border border-neon-purple/30 text-neon-purple text-[10px] px-3 py-1 hover:bg-neon-purple/10 transition-colors disabled:opacity-30"
						onclick={handleTournament}
						disabled={tournamentStrategies.length < 2}
					>
						Start Tournament ({tournamentStrategies.length} strategies)
					</button>
					<button
						class="text-[10px] text-text-dim hover:text-text-secondary px-2 py-1"
						onclick={() => showTournament = false}
					>
						Cancel
					</button>
				</div>
			</div>
		{/if}
	{/if}

	<!-- Status Bar -->
	<div class="flex h-5 shrink-0 items-center justify-between border-t border-neon-cyan/10 bg-bg-secondary px-2 text-[10px] text-text-dim">
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
