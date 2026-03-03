<script lang="ts">
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptAnalysis } from '$lib/stores/promptAnalysis.svelte';
	import { sessionContext } from '$lib/stores/sessionContext.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { saveActiveTabState, restoreTabState, closeIDE } from '$lib/stores/tabCoherence';
	import { processScheduler } from '$lib/stores/processScheduler.svelte';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { settingsState } from '$lib/stores/settings.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { ALL_STRATEGIES } from '$lib/utils/strategies';
	import { reforge, chainForge, iterate, type ForgeActionStores } from '$lib/utils/forgeActions';
	import { getScoreBadgeClass, formatScore } from '$lib/utils/format';
	import { SECTION_COLORS, type DetectedSection } from '$lib/utils/promptParser';
	import { FILE_EXTENSIONS, ARTIFACT_KINDS } from '$lib/utils/fileTypes';
	import { DRAG_MIME, decodeDragPayload } from '$lib/utils/dragPayload';
	import { openDocument } from '$lib/utils/documentOpener';
	import ForgeEditor from './ForgeEditor.svelte';
	import Icon from './Icon.svelte';
	import { Tooltip, MetaBadge } from './ui';

	let forgeEditorRef: ForgeEditor | undefined = $state();

	let tabBarDropActive = $state(false);
	let cursorLine = $state(1);
	let cursorCol = $state(1);
	let selectedChars = $state(0);

	function handleCursorChange(line: number, col: number) {
		cursorLine = line;
		cursorCol = col;
	}

	function handleSelectionChange(chars: number) {
		selectedChars = chars;
	}

	/** Delegate jumpToLine to the inner ForgeEditor. */
	export function jumpToLine(lineNumber: number) {
		forgeEditorRef?.jumpToLine(lineNumber);
	}

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

	function handleAbortForge() {
		optimizationState.reset();
		forgeMachine.reset();
		// Persist cleaned tab state so stale forging data doesn't survive reload
		saveActiveTabState();
	}

	let showTournament = $state(false);
	let tournamentStrategies: string[] = $state([]);

	// Auto-refine state
	let autoRefine = $state(false);
	let scoreThreshold = $state(7);

	// Session context toggle
	let useSessionContext = $state(false);

	function exitIDE() {
		closeIDE();
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

	let variableCount = $derived(promptAnalysis.variables.length);
	let modKey = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.userAgent) ? '⌘' : 'Ctrl+';

	// Sync tab name with draft title (revert to "Untitled N" when cleared)
	$effect(() => {
		const tab = forgeSession.activeTab;
		if (!tab) return;
		const title = forgeSession.draft.title.trim();
		if (title) {
			if (tab.name !== title) tab.name = title;
		} else if (!/^Untitled(?: \d+)?$/.test(tab.name)) {
			// Title cleared — revert to a unique Untitled name
			const taken = new Set(forgeSession.tabs.filter(t => t.id !== tab.id).map(t => t.name));
			let n = 1;
			while (taken.has(`Untitled ${n}`)) n++;
			tab.name = `Untitled ${n}`;
		}
	});

	// §1: Auto-focus editor on IDE entry and tab switch
	$effect(() => {
		const _ = forgeSession.activeTabId;
		if (forgeEditorRef && forgeMachine.mode === 'compose') {
			queueMicrotask(() => forgeEditorRef?.focus());
		}
	});

	// §2: Derived current pipeline stage for forging toolbar
	let currentStage = $derived.by(() => {
		const steps = optimizationState.currentRun?.steps;
		if (!steps) return null;
		return steps.find(s => s.status === 'running') ?? steps.findLast(s => s.status === 'complete');
	});

	// §3c: Cursor-aware section breadcrumb
	let currentSection = $derived.by(() => {
		const secs = promptAnalysis.sections;
		if (secs.length === 0) return null;
		let match: DetectedSection | null = null;
		for (const s of secs) {
			if (s.lineNumber <= cursorLine) match = s;
			else break;
		}
		return match;
	});

	// §4c: Strategy recommendation quick-pick
	let showStrategyPicker = $state(false);
	let hasRecommendations = $derived(promptAnalysis.recommendedStrategies.length > 0);

	// §F1: Save prompt to project
	let saveFlash = $state(false);

	async function handleSave() {
		if (!forgeSession.hasText || forgeMachine.mode === 'forging') return;
		const draft = forgeSession.draft;
		const projectName = draft.project?.trim();
		if (!projectName) {
			toastState.show('Set a project name first', 'info');
			forgeSession.showMetadata = true;
			return;
		}
		const project = projectsState.allItems.find(p => p.name === projectName);
		if (!project) {
			toastState.show(`Project "${projectName}" not found`, 'error');
			return;
		}
		try {
			if (draft.promptId) {
				await projectsState.updatePrompt(project.id, draft.promptId, draft.text);
			} else {
				const prompt = await projectsState.addPrompt(project.id, draft.text);
				if (prompt) {
					forgeSession.updateDraft({ promptId: prompt.id });
				}
			}
			// Clear modified indicator
			const tab = forgeSession.activeTab;
			if (tab) tab.originalText = draft.text;
			// Flash save icon green
			saveFlash = true;
			setTimeout(() => { saveFlash = false; }, 800);
			toastState.show('Saved', 'success', 2000);
		} catch {
			toastState.show('Save failed', 'error');
		}
	}

	// Listen for save bus event (from Ctrl+S in layout)
	$effect(() => {
		const unsub = systemBus.on('forge:save', () => { handleSave(); });
		return unsub;
	});

	// §F2: Standalone analyze
	let isStandaloneAnalyzing = $derived(optimizationState.isAnalyzing);

	function handleAnalyzeOnly() {
		if (!forgeSession.hasText || optimizationState.isRunning) return;
		optimizationState.runNodeAnalyze({
			prompt: forgeSession.draft.text,
			codebase_context: forgeSession.draft.contextProfile,
		});
	}

	// §F3: Review toolbar — shared forge actions
	const forgeActionStores: ForgeActionStores = { optimizationState, forgeSession, forgeMachine };

	// §F5: Context popover
	let showContextPopover = $state(false);

	let contextCharCount = $derived.by(() => {
		const ctx = forgeSession.draft.contextProfile;
		if (!ctx) return 0;
		return JSON.stringify(ctx).length;
	});

	// Shared click-outside + Escape dismiss helper for popovers
	function createDismissEffect(isOpen: () => boolean, close: () => void): void {
		$effect(() => {
			if (!isOpen()) return;
			const onKeydown = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
			const timer = setTimeout(() => window.addEventListener('click', close), 0);
			window.addEventListener('keydown', onKeydown);
			return () => {
				clearTimeout(timer);
				window.removeEventListener('click', close);
				window.removeEventListener('keydown', onKeydown);
			};
		});
	}
	createDismissEffect(() => showContextPopover, () => { showContextPopover = false; });
	createDismissEffect(() => showStrategyPicker, () => { showStrategyPicker = false; });

	// §F7: Default strategy indicator
	let isDefaultStrategy = $derived(
		settingsState.defaultStrategy !== 'auto' &&
		forgeSession.draft.strategy === settingsState.defaultStrategy
	);

	// Dismiss strategy picker when forge starts or recommendations disappear
	$effect(() => {
		if (forgeMachine.mode !== 'compose' || promptAnalysis.recommendedStrategies.length === 0) {
			showStrategyPicker = false;
		}
	});
</script>

<div class="flex flex-1 flex-col overflow-hidden bg-bg-primary">
	<!-- Tab Bar -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="flex h-7 shrink-0 items-center border-b bg-bg-secondary px-1.5 {tabBarDropActive ? 'border-neon-cyan/30' : 'border-white/[0.06]'}"
		ondrop={handleTabBarDrop}
		ondragover={handleTabBarDragOver}
		ondragleave={handleTabBarDragLeave}
	>
		{#each forgeSession.tabs as tab (tab.id)}
			{@const isModified = (tab.draft.text !== tab.originalText) && (tab.draft.text !== '' || tab.originalText !== '')}
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
					class="rounded-sm p-0.5 hover:bg-bg-input transition-opacity {tab.id === forgeSession.activeTabId && forgeMachine.mode === 'forging' ? 'pointer-events-none opacity-20' : ''} {isModified ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}"
				>
					{#if isModified}
						<span class="group-hover:hidden text-text-secondary text-[14px] leading-none">·</span>
						<span class="hidden group-hover:inline"><Icon name="x" size={10} /></span>
					{:else}
						<Icon name="x" size={10} />
					{/if}
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

	<!-- Breadcrumb Bar -->
	<div class="flex h-5 shrink-0 items-center gap-1.5 overflow-hidden border-b border-white/[0.06] bg-bg-secondary px-3">
		<Icon name="file-text" size={11} class="text-neon-cyan/50 shrink-0" />
		{#if forgeSession.draft.project}
			<span class="text-[11px] font-mono text-text-dim">{forgeSession.draft.project}</span>
			<span class="text-[11px] font-mono text-text-dim/30">/</span>
		{/if}
		{#if forgeSession.draft.title}
			<span class="text-[11px] font-mono text-text-secondary">{forgeSession.draft.title}{forgeSession.activeTab.document?.kind === 'artifact' ? '.forge' : '.md'}</span>
		{:else}
			<span class="text-[11px] font-mono text-text-dim/40">Untitled</span>
		{/if}
		<!-- §3c: Section breadcrumb (cursor-aware) -->
		{#if currentSection}
			<Icon name="chevron-right" size={9} class="text-text-dim/30 shrink-0" />
			<span class="text-[10px] font-mono truncate max-w-[120px]"
				  style="color: var(--color-{SECTION_COLORS[currentSection.type]})">
				{currentSection.label}
			</span>
		{/if}
		{#if forgeSession.draft.sourceAction}
			<span class="rounded-sm px-1 py-px text-[9px] font-medium {forgeSession.draft.sourceAction === 'optimize' ? 'border border-neon-purple/20 text-neon-purple/80' : 'border border-neon-cyan/20 text-neon-cyan/80'}">
				{forgeSession.draft.sourceAction === 'optimize' ? 'Optimizing' : 'Reiterating'}
			</span>
		{/if}
		<!-- §3a: Version badge -->
		{#if forgeSession.draft.version}
			<span class="rounded-sm border border-neon-green/20 px-1 py-px text-[9px] font-mono font-medium text-neon-green/70">
				{forgeSession.draft.version}
			</span>
		{/if}
		<!-- §3b: Tags display (first 2) -->
		{#if forgeSession.draft.tags}
			{@const tagList = forgeSession.draft.tags.split(',').map(t => t.trim()).filter(Boolean).slice(0, 2)}
			{#each tagList as tag}
				<span class="rounded-sm border border-neon-indigo/15 px-1 py-px text-[8px] font-mono text-neon-indigo/50">#{tag}</span>
			{/each}
		{/if}
		{#if forgeSession.draft.promptId}
			<Tooltip text="Linked to project prompt">
				<Icon name="link" size={10} class="text-neon-green/60 shrink-0" />
			</Tooltip>
		{/if}
		<!-- §3d: Context status indicator (clickable popover) -->
		{#if forgeSession.hasContext}
			<div class="relative shrink-0">
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<button
					class="flex items-center text-neon-teal/60 hover:text-neon-teal transition-colors"
					onclick={(e) => { e.stopPropagation(); showContextPopover = !showContextPopover; }}
					title="Context: {forgeSession.draft.contextSource ?? 'manual'}"
				>
					<Icon name="server" size={10} />
				</button>
				{#if showContextPopover}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div class="absolute top-5 left-0 z-50 w-48 border border-neon-teal/20 bg-bg-secondary" onclick={(e) => e.stopPropagation()}>
						<div class="px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-neon-teal/60 border-b border-neon-teal/10">
							Context
						</div>
						<div class="px-2 py-1.5 space-y-1">
							<div class="flex items-center gap-1.5">
								<span class="text-[9px] text-text-dim">Source:</span>
								<span class="text-[10px] text-text-secondary font-mono">{forgeSession.draft.contextSource ?? 'manual'}</span>
							</div>
							{#if forgeSession.draft.contextProfile?.language}
								<div class="flex items-center gap-1.5">
									<span class="text-[9px] text-text-dim">Language:</span>
									<span class="rounded-sm border border-neon-cyan/15 px-1 py-px text-[9px] font-mono text-neon-cyan/70">{forgeSession.draft.contextProfile.language}</span>
								</div>
							{/if}
							{#if forgeSession.draft.contextProfile?.framework}
								<div class="flex items-center gap-1.5">
									<span class="text-[9px] text-text-dim">Framework:</span>
									<span class="rounded-sm border border-neon-purple/15 px-1 py-px text-[9px] font-mono text-neon-purple/70">{forgeSession.draft.contextProfile.framework}</span>
								</div>
							{/if}
							<div class="flex items-center gap-1.5">
								<span class="text-[9px] text-text-dim">Size:</span>
								<span class="text-[10px] text-text-secondary font-mono tabular-nums">{contextCharCount.toLocaleString()} chars</span>
							</div>
						</div>
						<div class="flex items-center gap-1 border-t border-white/[0.06] px-2 py-1">
							<button
								class="text-[9px] text-neon-red/70 hover:text-neon-red transition-colors"
								onclick={() => { forgeSession.updateDraft({ contextProfile: null, contextSource: null }); showContextPopover = false; }}
							>
								Clear
							</button>
							<button
								class="ml-auto text-[9px] text-text-dim hover:text-text-secondary transition-colors"
								onclick={() => { forgeSession.showContext = true; showContextPopover = false; }}
							>
								Configure
							</button>
						</div>
					</div>
				{/if}
			</div>
		{/if}
		<!-- §F1: Save button -->
		<Tooltip text="Save to project ({modKey}S)">
			<button
				class="shrink-0 transition-colors {saveFlash ? 'text-neon-green' : 'text-text-dim/40 hover:text-text-secondary'}"
				onclick={handleSave}
				disabled={!forgeSession.hasText || forgeMachine.mode === 'forging'}
				aria-label="Save prompt"
			>
				<Icon name="download" size={11} />
			</button>
		</Tooltip>
	</div>

	<!-- §5: Validation Error Bar -->
	{#if Object.keys(forgeSession.validationErrors).length > 0}
		<div class="flex items-center gap-2 border-b border-neon-red/20 bg-neon-red/[0.03] px-3 py-0.5">
			<Icon name="alert-circle" size={11} class="text-neon-red shrink-0" />
			<span class="text-[10px] text-neon-red truncate">
				{Object.values(forgeSession.validationErrors).join(' · ')}
			</span>
			<button onclick={() => forgeSession.validationErrors = {}}
					class="ml-auto shrink-0 text-neon-red/50 hover:text-neon-red transition-colors">
				<Icon name="x" size={10} />
			</button>
		</div>
	{/if}

	<!-- Editor Area -->
	<div class="relative flex-1 bg-bg-secondary overflow-hidden flex flex-col">
		<ForgeEditor bind:this={forgeEditorRef} variant="focus" onsubmit={handleSubmit} oncursorchange={handleCursorChange} onselectionchange={handleSelectionChange} />
	</div>

	<!-- §F6: Analysis inline bar -->
	{#if optimizationState.analysisResult && forgeMachine.mode === 'compose'}
		{@const analysis = optimizationState.analysisResult}
		<div class="flex items-center gap-2 border-t border-neon-orange/10 bg-neon-orange/[0.02] px-2 py-0.5">
			{#if analysis.task_type}
				<MetaBadge type="task" value={analysis.task_type} size="xs" />
			{/if}
			{#if analysis.complexity}
				<MetaBadge type="complexity" value={analysis.complexity} size="xs" />
			{/if}
			{#if analysis.weaknesses?.length}
				<span class="text-[9px] font-mono text-neon-red/70">{analysis.weaknesses.length} weakness{analysis.weaknesses.length !== 1 ? 'es' : ''}</span>
			{/if}
			{#if analysis.strengths?.length}
				<span class="text-[9px] font-mono text-neon-green/70">{analysis.strengths.length} strength{analysis.strengths.length !== 1 ? 's' : ''}</span>
			{/if}
			{#if analysis.step_duration_ms}
				<span class="text-[9px] font-mono text-text-dim tabular-nums">{(analysis.step_duration_ms / 1000).toFixed(1)}s</span>
			{/if}
			<button onclick={() => optimizationState.clearAnalysis()} class="ml-auto shrink-0 text-text-dim/50 hover:text-text-secondary transition-colors">
				<Icon name="x" size={10} />
			</button>
		</div>
	{/if}

	<!-- Toolbar: Tournament + Auto-refine -->
	{#if forgeMachine.mode === 'forging'}
		<div class="flex items-center justify-between border-t border-white/[0.06] bg-bg-secondary px-2 py-1">
			<div class="flex items-center gap-2">
				{#if optimizationState.error}
					<Icon name="alert-triangle" size={12} class="text-neon-red" />
					<span class="text-[10px] font-medium text-neon-red truncate max-w-[300px]">{optimizationState.error}</span>
					{#if optimizationState.retryAfter}
						<span class="text-[10px] font-medium text-neon-yellow tabular-nums">retry in {optimizationState.retryAfter}s</span>
					{/if}
				{:else}
					<Icon name="loader" size={12} class="animate-spin text-neon-purple" />
					<span class="text-[10px] font-medium text-neon-purple uppercase tracking-wider">
						{currentStage?.label ?? 'Forging...'}
					</span>
					{#if optimizationState.currentIteration > 0}
						<span class="text-[9px] font-mono text-text-dim tabular-nums">iter {optimizationState.currentIteration}/3</span>
					{/if}
					{#if processScheduler.runningCount > 1}
						<span class="text-[9px] font-mono text-text-dim tabular-nums">{processScheduler.runningCount} running</span>
					{/if}
				{/if}
			</div>
			<button
				onclick={handleAbortForge}
				class="flex items-center gap-1 text-[10px] border border-neon-red/20 text-neon-red px-2 py-0.5 hover:bg-neon-red/10 transition-colors"
				aria-label="Abort forge"
			>
				<Icon name="x" size={10} />
				Abort
			</button>
		</div>
	{:else if forgeMachine.mode === 'compose' && forgeSession.hasText}
		<div class="flex items-center gap-3 border-t border-white/[0.06] bg-bg-secondary px-2 py-1">
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

			<div class="ml-auto flex items-center gap-1.5">
				<!-- §F2: Analyze Only button -->
				<Tooltip text="Analyze prompt without optimizing">
					<button
						class="flex items-center gap-1 text-[10px] border border-neon-cyan/20 text-neon-cyan px-2 py-0.5 hover:bg-neon-cyan/10 transition-colors disabled:opacity-30"
						onclick={handleAnalyzeOnly}
						disabled={!forgeSession.hasText || optimizationState.isRunning}
					>
						{#if isStandaloneAnalyzing}
							<Icon name="loader" size={10} class="animate-spin" />
							Analyzing...
						{:else}
							<Icon name="search" size={10} />
							Analyze
						{/if}
					</button>
				</Tooltip>
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
	{:else if forgeMachine.mode === 'review'}
		<!-- §F3: Review mode toolbar -->
		<div class="flex items-center gap-2 border-t border-white/[0.06] bg-bg-secondary px-2 py-1">
			<button
				onclick={() => forgeMachine.back()}
				class="flex items-center gap-1 text-[10px] text-text-dim hover:text-text-secondary transition-colors"
			>
				<Icon name="chevron-left" size={10} />
				Compose
			</button>
			{#if optimizationState.forgeResult?.scores?.overall != null}
				<span class="rounded-sm px-1.5 py-px text-[10px] font-mono font-medium tabular-nums {getScoreBadgeClass(optimizationState.forgeResult.scores.overall)}">
					{formatScore(optimizationState.forgeResult.scores.overall)}
				</span>
			{/if}
			<div class="ml-auto flex items-center gap-1.5">
				<Tooltip text="Re-forge with same original prompt">
					<button
						onclick={() => reforge(forgeActionStores)}
						class="flex items-center gap-1 text-[10px] border border-neon-cyan/20 text-neon-cyan px-2 py-0.5 hover:bg-neon-cyan/10 transition-colors"
					>
						<Icon name="refresh" size={10} />
						Re-forge
					</button>
				</Tooltip>
				<Tooltip text="Chain: use optimized output as new input">
					<button
						onclick={() => chainForge(forgeActionStores)}
						class="flex items-center gap-1 text-[10px] border border-neon-orange/20 text-neon-orange px-2 py-0.5 hover:bg-neon-orange/10 transition-colors"
					>
						<Icon name="git-branch" size={10} />
						Chain
					</button>
				</Tooltip>
				<Tooltip text="Load optimized prompt into editor for manual edits">
					<button
						onclick={() => iterate(forgeActionStores)}
						class="flex items-center gap-1 text-[10px] border border-neon-purple/20 text-neon-purple px-2 py-0.5 hover:bg-neon-purple/10 transition-colors"
					>
						<Icon name="edit" size={10} />
						Iterate
					</button>
				</Tooltip>
			</div>
		</div>
	{/if}

	<!-- Status Bar -->
	<div class="relative flex h-6 shrink-0 items-center border-t border-white/[0.06] bg-bg-secondary px-2 text-[10px] text-text-dim">
		<!-- Left: cursor position + metrics -->
		<span class="font-mono tabular-nums">Ln {cursorLine}</span>
		<span class="mx-1.5 inline-block h-2.5 w-px bg-white/[0.06]"></span>
		<span class="font-mono tabular-nums">{forgeSession.wordCount} word{forgeSession.wordCount !== 1 ? 's' : ''} · {forgeSession.charCount.toLocaleString()} chars</span>
		{#if selectedChars > 0}
			<span class="ml-1.5 font-mono tabular-nums text-neon-cyan">{selectedChars} sel</span>
		{/if}
		{#if variableCount > 0}
			<span class="ml-1.5 font-mono tabular-nums text-neon-teal/60">{variableCount} var{variableCount !== 1 ? 's' : ''}</span>
		{/if}

		<span class="flex-1"></span>

		<!-- Right: analysis + task type + strategy + shortcut -->
		<!-- §4a: Analysis spinner (only during cold-start, not re-analysis) -->
		{#if promptAnalysis.isAnalyzing && !promptAnalysis.heuristic}
			<span class="inline-block h-1.5 w-1.5 rounded-full bg-neon-orange/60 animate-pulse mr-1.5" title="Analyzing..."></span>
		{/if}
		<!-- §4b: Matched keywords tooltip on task type badge -->
		{#if promptAnalysis.heuristic}
			<Tooltip text="{promptAnalysis.heuristic.matchedKeywords.length > 0
				? 'Keywords: ' + promptAnalysis.heuristic.matchedKeywords.slice(0, 5).join(', ')
				: 'No keyword matches'}" side="top">
				<span class="inline-flex items-center gap-0.5">
					<MetaBadge type="task" value={promptAnalysis.heuristic.taskType} size="xs" showTooltip={false} />
					<span class="font-mono text-[9px] text-text-dim/50 tabular-nums">{Math.round(promptAnalysis.heuristic.confidence * 100)}%</span>
				</span>
			</Tooltip>
		{/if}
		<!-- §4c: Strategy recommendation quick-pick -->
		{#if forgeSession.draft.strategy && forgeSession.draft.strategy !== 'auto'}
			<span class="mx-1.5 inline-block h-2.5 w-px bg-white/[0.06]"></span>
			{#if hasRecommendations}
				<button class="inline-flex items-center gap-0.5 font-mono text-neon-purple/60 hover:text-neon-purple transition-colors" onclick={() => showStrategyPicker = !showStrategyPicker}>
					{forgeSession.draft.strategy}
					<Icon name="chevron-up" size={10} class={showStrategyPicker ? 'rotate-180' : ''} />
				</button>
			{:else}
				<span class="font-mono text-neon-purple/60">{forgeSession.draft.strategy}</span>
			{/if}
			<!-- §F7: Default strategy indicator -->
			{#if isDefaultStrategy}
				<span class="text-[8px] font-mono text-text-dim/40">(default)</span>
			{/if}
		{:else if hasRecommendations}
			<span class="mx-1.5 inline-block h-2.5 w-px bg-white/[0.06]"></span>
			<button class="inline-flex items-center gap-0.5 font-mono text-text-dim/60 hover:text-text-secondary transition-colors" onclick={() => showStrategyPicker = !showStrategyPicker}>
				auto
				<Icon name="chevron-up" size={10} class={showStrategyPicker ? 'rotate-180' : ''} />
			</button>
		{/if}
		<!-- §F4: Secondary strategies badge -->
		{#if forgeSession.draft.secondaryStrategies.length > 0}
			<Tooltip text="Secondary: {forgeSession.draft.secondaryStrategies.join(', ')}">
				<span class="ml-1 rounded-sm border border-neon-cyan/20 px-1 py-px text-[8px] font-mono font-medium text-neon-cyan/70">
					+{forgeSession.draft.secondaryStrategies.length}
				</span>
			</Tooltip>
		{/if}
		{#if forgeMachine.mode === 'compose'}
			<span class="mx-1.5 inline-block h-2.5 w-px bg-white/[0.06]"></span>
			<span class="font-mono text-text-dim/40">{modKey}⏎ forge</span>
		{/if}

		<!-- Strategy picker popover -->
		{#if showStrategyPicker && promptAnalysis.recommendedStrategies.length > 0}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="absolute bottom-7 right-4 z-50 w-56 border border-neon-purple/20 bg-bg-secondary" onclick={(e) => e.stopPropagation()}>
				<div class="px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-neon-purple/60 border-b border-neon-purple/10">
					Recommended Strategies
				</div>
				{#each promptAnalysis.recommendedStrategies as rec}
					<button
						class="flex w-full items-center gap-1.5 px-2 py-1 text-[10px] text-text-secondary hover:bg-bg-hover transition-colors"
						onclick={() => { forgeSession.updateDraft({ strategy: rec.name }); showStrategyPicker = false; }}
					>
						<Icon name="zap" size={9} class="text-neon-purple/60 shrink-0" />
						<span class="font-mono truncate">{rec.label}</span>
						<span class="ml-auto font-mono text-[9px] text-text-dim tabular-nums">{Math.round(rec.compositeScore * 100)}%</span>
					</button>
				{/each}
				<div class="border-t border-white/[0.06]">
					<button
						class="flex w-full items-center gap-1.5 px-2 py-1 text-[10px] text-text-dim hover:bg-bg-hover transition-colors"
						onclick={() => { forgeSession.updateDraft({ strategy: 'auto' }); showStrategyPicker = false; }}
					>
						<Icon name="refresh" size={9} class="text-text-dim/40 shrink-0" />
						<span class="font-mono">Auto-select</span>
					</button>
				</div>
				<!-- §F4: Secondary strategy section -->
				<div class="border-t border-neon-cyan/10">
					<div class="px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-neon-cyan/50">
						Secondary (max 2)
					</div>
					{#each promptAnalysis.recommendedStrategies.filter(r => r.name !== forgeSession.draft.strategy) as rec}
						{@const isActive = forgeSession.draft.secondaryStrategies.includes(rec.name)}
						<button
							class="flex w-full items-center gap-1.5 px-2 py-1 text-[10px] transition-colors {isActive ? 'text-neon-cyan bg-neon-cyan/[0.05]' : 'text-text-dim hover:bg-bg-hover hover:text-text-secondary'}"
							onclick={() => forgeSession.toggleSecondaryStrategy(rec.name)}
						>
							<Icon name={isActive ? 'check' : 'plus'} size={9} class="shrink-0 {isActive ? 'text-neon-cyan' : 'text-text-dim/40'}" />
							<span class="font-mono truncate">{rec.label}</span>
						</button>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>
