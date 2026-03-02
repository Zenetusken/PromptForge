<script lang="ts">
	import { Collapsible } from "bits-ui";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { projectsState } from "$lib/stores/projects.svelte";
	import type { CodebaseContext } from "$lib/api/client";
	import { fetchProject, fetchContextPreview } from "$lib/api/client";
	import { knowledge } from "$lib/kernel/services/knowledge.svelte";
	import { toLines, formatChars } from "$lib/utils/safe";
	import { STACK_TEMPLATES } from "$lib/utils/stackTemplates";
	import Icon from "./Icon.svelte";
	import { Tooltip } from "./ui";

	// Kernel knowledge profile for the matched project
	let kbLanguage = $state('');
	let kbFramework = $state('');
	let kbSourceCount = $state(0);

	// Source count from the matched project (fallback)
	let sourceCount = $derived.by(() => {
		if (kbSourceCount > 0) return kbSourceCount;
		const currentProject = forgeSession.draft.project.trim();
		if (!currentProject) return 0;
		const match = projectsState.allItems.find((p) => p.name === currentProject);
		return match?.source_count ?? 0;
	});

	// Auto-fetch resolved context preview
	let previewData = $state<CodebaseContext | null>(null);
	let previewLoading = $state(false);
	let previewFieldCount = $state(0);
	let previewRenderedChars = $state(0);

	// Auto-fetch effect: debounced, fires when section is open and inputs change
	let fetchTimer: ReturnType<typeof setTimeout> | undefined;
	let fetchController: AbortController | null = null;
	$effect(() => {
		// Track dependencies
		const isOpen = forgeSession.showContext;
		const project = forgeSession.draft.project;
		const ctx = forgeSession.draft.contextProfile;

		if (!isOpen) return;

		// Debounce 600ms
		clearTimeout(fetchTimer);
		fetchController?.abort();
		fetchTimer = setTimeout(async () => {
			const controller = new AbortController();
			fetchController = controller;
			previewLoading = true;
			try {
				const p = project?.trim() || null;
				const result = await fetchContextPreview(p, ctx || null, controller.signal);
				if (controller.signal.aborted) return;
				previewData = result.context;
				previewFieldCount = result.field_count;
				previewRenderedChars = result.rendered_chars;
			} catch {
				if (!controller.signal.aborted) {
					previewData = null;
					previewFieldCount = 0;
					previewRenderedChars = 0;
				}
			} finally {
				if (!controller.signal.aborted) previewLoading = false;
			}
		}, 600);

		return () => {
			clearTimeout(fetchTimer);
			fetchController?.abort();
		};
	});

	/** Truncate a verbose context value at a natural break for summary display. */
	function shortLabel(s: string, max = 25): string {
		if (s.length <= max) return s;
		for (const br of [', ', ' + ', ' / ']) {
			const idx = s.indexOf(br);
			if (idx > 0 && idx <= max) return s.slice(0, idx);
		}
		return s.slice(0, max) + '\u2026';
	}

	// Compact resolved summary text
	let resolvedSummary = $derived.by(() => {
		if (!previewData) return null;
		const parts: string[] = [];
		if (previewData.language) parts.push(shortLabel(previewData.language));
		if (previewData.framework) parts.push(shortLabel(previewData.framework));
		const testFw = previewData.test_framework;
		if (testFw) parts.push(shortLabel(testFw));
		const sc = previewData.sources?.length ?? 0;
		if (sc > 0) parts.push(`${sc} source${sc !== 1 ? 's' : ''}`);
		const nc = previewData.conventions?.length ?? 0;
		if (nc > 0) parts.push(`${nc} conv`);
		const np = previewData.patterns?.length ?? 0;
		if (np > 0) parts.push(`${np} pat`);
		const ntp = previewData.test_patterns?.length ?? 0;
		if (ntp > 0) parts.push(`${ntp} test pat`);

		return parts.length > 0 ? parts.join(' \u00b7 ') : null;
	});

	// Technical hint fields synced to forgeSession.draft.contextProfile
	let ctxConventions = $state("");
	let ctxPatterns = $state("");
	let ctxTestFramework = $state("");
	let ctxTestPatterns = $state("");
	let hasContextData = $derived(
		!!(ctxConventions || ctxPatterns || ctxTestFramework || ctxTestPatterns),
	);

	// Sync context fields from forgeSession.draft.contextProfile when it changes externally
	let lastSyncedContextProfile: CodebaseContext | null = null;
	$effect(() => {
		const cp = forgeSession.draft.contextProfile;
		if (cp !== lastSyncedContextProfile) {
			lastSyncedContextProfile = cp;
			if (cp) {
				ctxConventions = toLines(cp.conventions);
				ctxPatterns = toLines(cp.patterns);
				ctxTestFramework = cp.test_framework ?? "";
				ctxTestPatterns = toLines(cp.test_patterns);
			} else {
				ctxConventions = "";
				ctxPatterns = "";
				ctxTestFramework = "";
				ctxTestPatterns = "";
			}
		}
	});

	export function syncContextToDraft() {
		if (!hasContextData) {
			lastSyncedContextProfile = null;
			forgeSession.updateDraft({ contextProfile: null, contextSource: null, activeTemplateId: null });
			return;
		}
		const ctx: CodebaseContext = {};
		if (ctxConventions.trim()) {
			const items = ctxConventions.split("\n").map((s) => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.conventions = items;
		}
		if (ctxPatterns.trim()) {
			const items = ctxPatterns.split("\n").map((s) => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.patterns = items;
		}
		if (ctxTestFramework.trim()) ctx.test_framework = ctxTestFramework.trim();
		if (ctxTestPatterns.trim()) {
			const items = ctxTestPatterns.split("\n").map((s) => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.test_patterns = items;
		}
		const profile = Object.keys(ctx).length > 0 ? ctx : null;
		lastSyncedContextProfile = profile;
		forgeSession.updateDraft({ contextProfile: profile });
	}

	function applyContext(
		ctx: CodebaseContext,
		source: "project" | "template",
		templateId?: string,
	) {
		ctxConventions = toLines(ctx.conventions);
		ctxPatterns = toLines(ctx.patterns);
		ctxTestFramework = ctx.test_framework ?? "";
		ctxTestPatterns = toLines(ctx.test_patterns);
		forgeSession.updateDraft({
			contextProfile: ctx,
			contextSource: source,
			activeTemplateId: templateId ?? null,
		});
		lastSyncedContextProfile = ctx;
		forgeSession.showContext = true;
	}

	function clearContext() {
		ctxConventions = "";
		ctxPatterns = "";
		ctxTestFramework = "";
		ctxTestPatterns = "";
		kbLanguage = "";
		kbFramework = "";
		kbSourceCount = 0;
		previewData = null;
		previewFieldCount = 0;
		previewRenderedChars = 0;
		lastSyncedContextProfile = null;
		forgeSession.updateDraft({
			contextProfile: null,
			contextSource: null,
			activeTemplateId: null,
		});
	}

	async function loadAndApplyProjectContext(projectId: string) {
		// Load kernel knowledge profile for identity badges
		let kernelProfile: import("$lib/kernel/types").KnowledgeProfile | null = null;
		try {
			kernelProfile = await knowledge.getProfile('promptforge', projectId);
			if (kernelProfile) {
				kbLanguage = kernelProfile.language ?? '';
				kbFramework = kernelProfile.framework ?? '';
				// Count sources from cached data
				const sources = knowledge.getCachedSources('promptforge', projectId);
				kbSourceCount = sources.length;
			}
		} catch {
			// Fallback — no kernel profile available
		}

		// Load legacy context profile for hint fields
		const detail = await fetchProject(projectId);
		if (detail?.context_profile) {
			applyContext(detail.context_profile, "project");
		} else if (kernelProfile) {
			// Build hint context from kernel metadata when legacy is absent
			const meta = kernelProfile.metadata ?? {};
			const ctx: CodebaseContext = {};
			if (Array.isArray(meta.conventions)) ctx.conventions = meta.conventions as string[];
			if (Array.isArray(meta.patterns)) ctx.patterns = meta.patterns as string[];
			if (typeof meta.test_patterns === 'object' && Array.isArray(meta.test_patterns))
				ctx.test_patterns = meta.test_patterns as string[];
			if (kernelProfile.test_framework) ctx.test_framework = kernelProfile.test_framework;
			if (Object.keys(ctx).length > 0) {
				applyContext(ctx, "project");
			}
		}
	}

	// Auto-resolve context when project field changes
	let lastAutoResolvedProject = "";
	$effect(() => {
		const currentProject = forgeSession.draft.project.trim();
		if (
			currentProject &&
			currentProject !== lastAutoResolvedProject &&
			!forgeSession.draft.contextSource
		) {
			// Ensure project list is loaded for lookup
			if (!projectsState.allItemsLoaded) {
				projectsState.loadAllProjects();
				return; // Will re-fire when allItems populates
			}
			const match = projectsState.allItems.find(
				(p) => p.name === currentProject,
			);
			if (match) {
				lastAutoResolvedProject = currentProject;
				loadAndApplyProjectContext(match.id);
			}
		}
		if (!currentProject) {
			lastAutoResolvedProject = "";
			kbLanguage = "";
			kbFramework = "";
			kbSourceCount = 0;
		}
	});

	// Template select handler
	function handleTemplateSelect(e: Event) {
		const select = e.target as HTMLSelectElement;
		const tmplId = select.value;
		if (!tmplId) {
			// Deselect template but keep current fields
			forgeSession.updateDraft({ activeTemplateId: null, contextSource: null });
			return;
		}
		const tmpl = STACK_TEMPLATES.find((t) => t.id === tmplId);
		if (tmpl) applyContext(tmpl.context, "template", tmpl.id);
	}

	// Collapsible trigger badge
	let triggerBadge = $derived.by(() => {
		if (previewFieldCount > 0) {
			return `${previewFieldCount} fields \u00b7 ${formatChars(previewRenderedChars)}`;
		}
		return null;
	});
</script>

<Collapsible.Root bind:open={forgeSession.showContext}>
	<Collapsible.Trigger
		class="collapsible-toggle"
		style="--toggle-accent: var(--color-neon-green)"
		data-testid="context-toggle"
	>
		<Icon
			name="chevron-right"
			size={12}
			class="transition-transform duration-200 {forgeSession.showContext
				? 'rotate-90'
				: ''}"
		/>
		<Tooltip text="Provide project context for grounded optimization"
			><span>Context</span></Tooltip
		>
		{#if triggerBadge}
			<span class="ml-1.5 text-[10px] leading-none text-neon-green/60">{triggerBadge}</span>
		{:else if hasContextData}
			<span class="collapsible-indicator bg-neon-green"></span>
		{/if}
	</Collapsible.Trigger>
	<Collapsible.Content>
		<div class="ctx-zone px-1.5 pt-0.5 pb-1" data-testid="context-fields">
			<!-- A. Identity Line — kernel language/framework badges (+ source count if badges present) -->
			{#if kbLanguage || kbFramework}
				<div class="mb-1.5 flex flex-wrap items-center gap-1.5">
					{#if kbLanguage}
						<Tooltip text={kbLanguage}>
							<span class="rounded-sm border border-neon-purple/20 bg-neon-purple/8 px-1.5 py-px text-[9px] text-neon-purple/80 max-w-[140px] truncate inline-block">{kbLanguage}</span>
						</Tooltip>
					{/if}
					{#if kbFramework}
						<Tooltip text={kbFramework}>
							<span class="rounded-sm border border-neon-purple/20 bg-neon-purple/8 px-1.5 py-px text-[9px] text-neon-purple/80 max-w-[140px] truncate inline-block">{kbFramework}</span>
						</Tooltip>
					{/if}
					{#if sourceCount > 0}
						<span class="flex items-center gap-1 text-[9px] text-text-dim">
							<Icon name="file-text" size={9} class="text-neon-cyan/60" />
							{sourceCount} source{sourceCount !== 1 ? 's' : ''}
						</span>
					{/if}
				</div>
			{/if}

			<!-- B. Editable Fields — flat, no sub-collapsible -->
			<div class="grid grid-cols-1 gap-1.5">
				<div class="ctx-field">
					<label for="pop-ctx-conv" class="ctx-field-label">Conventions</label>
					<textarea
						id="pop-ctx-conv"
						bind:value={ctxConventions}
						onchange={syncContextToDraft}
						placeholder="One per line"
						rows="3"
						data-testid="ctx-conventions"
						class="ctx-input resize-none"
					></textarea>
				</div>
				<div class="ctx-field">
					<label for="pop-ctx-pat" class="ctx-field-label">Patterns</label>
					<textarea
						id="pop-ctx-pat"
						bind:value={ctxPatterns}
						onchange={syncContextToDraft}
						placeholder="One per line"
						rows="3"
						data-testid="ctx-patterns"
						class="ctx-input resize-none"
					></textarea>
				</div>
			</div>

			<div class="grid grid-cols-1 gap-1.5 mt-1.5">
				<div class="ctx-field">
					<label for="pop-ctx-tf" class="ctx-field-label">Test Framework</label>
					<input
						id="pop-ctx-tf"
						type="text"
						bind:value={ctxTestFramework}
						onchange={syncContextToDraft}
						placeholder="e.g. vitest"
						data-testid="ctx-test-framework"
						class="ctx-input"
					/>
				</div>
				<div class="ctx-field">
					<label for="pop-ctx-tp" class="ctx-field-label">Test Patterns</label>
					<textarea
						id="pop-ctx-tp"
						bind:value={ctxTestPatterns}
						onchange={syncContextToDraft}
						placeholder="One per line"
						rows="2"
						data-testid="ctx-test-patterns"
						class="ctx-input resize-none"
					></textarea>
				</div>
			</div>

			<!-- C. Action Row — template select + clear -->
			<div class="mt-1.5 flex items-center gap-1.5">
				<select
					class="ctx-input flex-1 text-[10px] py-0.5"
					value={forgeSession.draft.activeTemplateId ?? ''}
					onchange={handleTemplateSelect}
				>
					<option value="">No template</option>
					{#each STACK_TEMPLATES as tmpl (tmpl.id)}
						<option value={tmpl.id}>{tmpl.name}</option>
					{/each}
				</select>
				{#if hasContextData}
					<button
						type="button"
						class="shrink-0 text-[9px] text-text-dim hover:text-neon-red/70 transition-colors"
						onclick={clearContext}
					>Clear</button>
				{/if}
			</div>

			<!-- D. Resolved Preview — auto-loading compact summary -->
			{#if previewData && resolvedSummary}
				<div class="mt-1.5 pt-1.5 border-t border-white/[0.04]">
					<div class="flex items-center gap-1.5">
						<span class="text-[9px] font-medium uppercase tracking-wider text-text-dim/50">Resolved</span>
						<span class="text-[9px] text-text-dim">
							{previewFieldCount} fields &middot; {formatChars(previewRenderedChars)} chars
						</span>
						{#if previewLoading}
							<span class="text-[9px] text-neon-cyan/50 animate-pulse">updating...</span>
						{/if}
					</div>
					<p class="text-[9px] text-text-dim leading-snug mt-0.5">{resolvedSummary}</p>
				</div>
			{:else if previewLoading}
				<div class="mt-1.5 pt-1.5 border-t border-white/[0.04]">
					<span class="text-[9px] text-text-dim/50 animate-pulse">Resolving context...</span>
				</div>
			{/if}
		</div>
	</Collapsible.Content>
</Collapsible.Root>
