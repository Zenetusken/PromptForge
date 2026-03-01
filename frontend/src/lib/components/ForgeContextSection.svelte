<script lang="ts">
	import { Collapsible } from "bits-ui";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { projectsState } from "$lib/stores/projects.svelte";
	import type { CodebaseContext } from "$lib/api/client";
	import { fetchProject, fetchContextPreview } from "$lib/api/client";
	import { knowledge } from "$lib/kernel/services/knowledge.svelte";
	import { toLines } from "$lib/utils/safe";
	import { STACK_TEMPLATES } from "$lib/utils/stackTemplates";
	import Icon from "./Icon.svelte";
	import ContextSnapshotPanel from "./ContextSnapshotPanel.svelte";
	import { Tooltip } from "./ui";

	// Kernel knowledge profile for the matched project
	let kbLanguage = $state('');
	let kbFramework = $state('');
	let kbDescription = $state('');
	let kbSourceCount = $state(0);

	// Source count from the matched project (fallback)
	let sourceCount = $derived.by(() => {
		if (kbSourceCount > 0) return kbSourceCount;
		const currentProject = forgeSession.draft.project.trim();
		if (!currentProject) return 0;
		const match = projectsState.allItems.find((p) => p.name === currentProject);
		return match?.source_count ?? 0;
	});

	let { compact = false }: { compact?: boolean } = $props();

	// Pre-forge context preview
	let previewData = $state<CodebaseContext | null>(null);
	let previewOpen = $state(false);
	let previewLoading = $state(false);
	let previewFieldCount = $state(0);
	let previewRenderedChars = $state(0);

	async function handlePreview() {
		if (previewOpen) {
			previewOpen = false;
			return;
		}
		previewLoading = true;
		try {
			const project = forgeSession.draft.project.trim() || null;
			const ctx = forgeSession.draft.contextProfile || null;
			const result = await fetchContextPreview(project, ctx);
			previewData = result.context;
			previewFieldCount = result.field_count;
			previewRenderedChars = result.rendered_chars;
			previewOpen = true;
		} catch {
			previewData = null;
			previewOpen = false;
		} finally {
			previewLoading = false;
		}
	}

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
		kbDescription = "";
		kbSourceCount = 0;
		lastSyncedContextProfile = null;
		forgeSession.updateDraft({
			contextProfile: null,
			contextSource: null,
			activeTemplateId: null,
		});
	}

	async function loadAndApplyProjectContext(projectId: string) {
		// Load kernel knowledge profile for the summary card
		let kernelProfile: import("$lib/kernel/types").KnowledgeProfile | null = null;
		try {
			kernelProfile = await knowledge.getProfile('promptforge', projectId);
			if (kernelProfile) {
				kbLanguage = kernelProfile.language ?? '';
				kbFramework = kernelProfile.framework ?? '';
				kbDescription = kernelProfile.description ?? '';
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
			const match = projectsState.allItems.find(
				(p) => p.name === currentProject,
			);
			if (match && (match.has_context || match.source_count > 0)) {
				lastAutoResolvedProject = currentProject;
				loadAndApplyProjectContext(match.id);
			}
		}
		if (!currentProject) {
			lastAutoResolvedProject = "";
			kbLanguage = "";
			kbFramework = "";
			kbDescription = "";
			kbSourceCount = 0;
		}
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
		{#if forgeSession.draft.contextSource === "project"}
			<span
				class="ml-1.5 rounded-full bg-neon-green/10 px-1.5 py-0.5 text-[10px] leading-none text-neon-green"
				>from project</span
			>
		{:else if forgeSession.draft.contextSource === "template"}
			<span
				class="ml-1.5 rounded-full bg-neon-green/10 px-1.5 py-0.5 text-[10px] leading-none text-neon-green"
				>from template</span
			>
		{:else if forgeSession.draft.contextSource === "workspace"}
			<span
				class="ml-1.5 rounded-full bg-neon-green/10 px-1.5 py-0.5 text-[10px] leading-none text-neon-green"
				>from workspace</span
			>
		{/if}
		{#if hasContextData && !forgeSession.draft.contextSource}
			<span class="collapsible-indicator bg-neon-green"></span>
		{/if}
	</Collapsible.Trigger>
	<Collapsible.Content>
		<div class="ctx-zone px-1.5 pt-0.5 pb-1" data-testid="context-fields">
			<!-- Project Summary Card (read-only, from kernel knowledge profile) -->
			{#if kbLanguage || kbFramework || kbDescription || sourceCount > 0}
				<div class="mb-2 rounded-sm border border-neon-purple/15 bg-neon-purple/[0.03] px-2 py-1.5">
					<div class="flex items-center gap-1.5 mb-1">
						<Icon name="cpu" size={10} class="text-neon-purple/70" />
						<span class="text-[9px] font-medium text-neon-purple/80">Project Knowledge</span>
					</div>
					<div class="flex flex-wrap items-center gap-1.5">
						{#if kbLanguage}
							<span class="rounded-sm border border-neon-purple/20 bg-neon-purple/8 px-1.5 py-px text-[9px] text-neon-purple/80">{kbLanguage}</span>
						{/if}
						{#if kbFramework}
							<span class="rounded-sm border border-neon-purple/20 bg-neon-purple/8 px-1.5 py-px text-[9px] text-neon-purple/80">{kbFramework}</span>
						{/if}
						{#if sourceCount > 0}
							<span class="flex items-center gap-1 text-[9px] text-text-dim">
								<Icon name="file-text" size={9} class="text-neon-cyan/60" />
								{sourceCount} source{sourceCount !== 1 ? 's' : ''}
							</span>
						{/if}
					</div>
					{#if kbDescription}
						<p class="mt-1 text-[9px] text-text-secondary leading-snug line-clamp-2">{kbDescription}</p>
					{/if}
				</div>
			{/if}

			<p class="mb-1 text-[9px] leading-snug text-text-dim">
				Optional technical hints for this forge. Project identity is set in the Projects window.
			</p>

			<!-- Stack Template Picker -->
			<div class="mb-1 flex flex-wrap items-center gap-1">
				{#each STACK_TEMPLATES as tmpl (tmpl.id)}
					<button
						type="button"
						class="ctx-template-chip {forgeSession.draft.activeTemplateId ===
						tmpl.id
							? 'bg-neon-green/12 border-neon-green/35 text-neon-green'
							: 'border-border-subtle text-text-dim hover:border-neon-green/25 hover:text-neon-green/80'}"
						title={tmpl.description}
						onclick={() =>
							applyContext(tmpl.context, "template", tmpl.id)}
						>{tmpl.name}</button
					>
				{/each}
				{#if hasContextData}
					<button
						type="button"
						class="ctx-template-chip border-neon-red/15 text-neon-red/40 hover:border-neon-red/30 hover:text-neon-red/70"
						onclick={clearContext}>Clear all</button
					>
				{/if}
			</div>

			<!-- Technical Hints -->
			<div class="ctx-group-label">Technical Hints</div>
			<div class="grid grid-cols-1 gap-1.5 {compact ? '' : 'sm:grid-cols-2'}">
				<div class="ctx-field">
					<label for="pop-ctx-conv" class="ctx-field-label"
						>Conventions</label
					>
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
					<label for="pop-ctx-pat" class="ctx-field-label"
						>Patterns</label
					>
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

			<div class="grid grid-cols-1 gap-1.5 mt-1.5 {compact ? '' : 'sm:grid-cols-2'}">
				<div class="ctx-field">
					<label for="pop-ctx-tf" class="ctx-field-label"
						>Test Framework</label
					>
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
					<label for="pop-ctx-tp" class="ctx-field-label"
						>Test Patterns</label
					>
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

			<!-- Pre-forge context preview -->
			<div class="mt-2 pt-1.5 border-t border-white/[0.04]">
				<button
					type="button"
					class="flex items-center gap-1 rounded-sm border border-neon-cyan/20 px-2 py-0.5 text-[10px] text-neon-cyan hover:bg-neon-cyan/8 transition-colors disabled:opacity-30"
					onclick={handlePreview}
					disabled={previewLoading}
				>
					<Icon name="eye" size={10} />
					{previewLoading ? 'Loading...' : previewOpen ? 'Hide Preview' : 'Preview Resolved Context'}
				</button>
				{#if previewOpen && previewData}
					<div class="mt-1.5">
						<div class="text-[9px] text-text-dim mb-1">
							Resolved {previewFieldCount}/9 fields &middot; ~{previewRenderedChars >= 1000 ? `${(previewRenderedChars / 1000).toFixed(1)}K` : previewRenderedChars} chars
						</div>
						<ContextSnapshotPanel context={previewData} />
					</div>
				{:else if previewOpen && !previewData}
					<p class="mt-1 text-[9px] text-text-dim italic">No context resolved. Set a project name or add hints above.</p>
				{/if}
			</div>
		</div>
	</Collapsible.Content>
</Collapsible.Root>
