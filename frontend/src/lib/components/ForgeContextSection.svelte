<script lang="ts">
	import { Collapsible } from "bits-ui";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { projectsState } from "$lib/stores/projects.svelte";
	import type { CodebaseContext } from "$lib/api/client";
	import { fetchProject } from "$lib/api/client";
	import { STACK_TEMPLATES } from "$lib/utils/stackTemplates";
	import Icon from "./Icon.svelte";
	import { Tooltip } from "./ui";

	let { compact = false }: { compact?: boolean } = $props();

	// Individual context fields synced to forgeSession.draft.contextProfile
	let ctxLanguage = $state("");
	let ctxFramework = $state("");
	let ctxDescription = $state("");
	let ctxConventions = $state("");
	let ctxPatterns = $state("");
	let ctxCodeSnippets = $state("");
	let ctxTestFramework = $state("");
	let ctxTestPatterns = $state("");
	let ctxDocumentation = $state("");
	let hasContextData = $derived(
		!!(
			ctxLanguage ||
			ctxFramework ||
			ctxDescription ||
			ctxConventions ||
			ctxPatterns ||
			ctxCodeSnippets ||
			ctxTestFramework ||
			ctxTestPatterns ||
			ctxDocumentation
		),
	);

	// Sync context fields from forgeSession.draft.contextProfile when it changes externally
	let lastSyncedContextProfile: CodebaseContext | null = null;
	$effect(() => {
		const cp = forgeSession.draft.contextProfile;
		if (cp !== lastSyncedContextProfile) {
			lastSyncedContextProfile = cp;
			if (cp) {
				ctxLanguage = cp.language ?? "";
				ctxFramework = cp.framework ?? "";
				ctxDescription = cp.description ?? "";
				ctxConventions = cp.conventions?.join("\n") ?? "";
				ctxPatterns = cp.patterns?.join("\n") ?? "";
				ctxCodeSnippets = cp.code_snippets?.join("\n") ?? "";
				ctxTestFramework = cp.test_framework ?? "";
				ctxTestPatterns = cp.test_patterns?.join("\n") ?? "";
				ctxDocumentation = cp.documentation ?? "";
			} else {
				ctxLanguage = "";
				ctxFramework = "";
				ctxDescription = "";
				ctxConventions = "";
				ctxPatterns = "";
				ctxCodeSnippets = "";
				ctxTestFramework = "";
				ctxTestPatterns = "";
				ctxDocumentation = "";
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
		if (ctxLanguage.trim()) ctx.language = ctxLanguage.trim();
		if (ctxFramework.trim()) ctx.framework = ctxFramework.trim();
		if (ctxDescription.trim()) ctx.description = ctxDescription.trim();
		if (ctxConventions.trim()) {
			const items = ctxConventions.split("\n").map((s) => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.conventions = items;
		}
		if (ctxPatterns.trim()) {
			const items = ctxPatterns.split("\n").map((s) => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.patterns = items;
		}
		if (ctxCodeSnippets.trim()) {
			const items = ctxCodeSnippets.split("\n").map((s) => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.code_snippets = items;
		}
		if (ctxDocumentation.trim()) ctx.documentation = ctxDocumentation.trim();
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
		ctxLanguage = ctx.language ?? "";
		ctxFramework = ctx.framework ?? "";
		ctxDescription = ctx.description ?? "";
		ctxConventions = ctx.conventions?.join("\n") ?? "";
		ctxPatterns = ctx.patterns?.join("\n") ?? "";
		ctxCodeSnippets = ctx.code_snippets?.join("\n") ?? "";
		ctxTestFramework = ctx.test_framework ?? "";
		ctxTestPatterns = ctx.test_patterns?.join("\n") ?? "";
		ctxDocumentation = ctx.documentation ?? "";
		forgeSession.updateDraft({
			contextProfile: ctx,
			contextSource: source,
			activeTemplateId: templateId ?? null,
		});
		lastSyncedContextProfile = ctx;
		forgeSession.showContext = true;
	}

	function clearContext() {
		ctxLanguage = "";
		ctxFramework = "";
		ctxDescription = "";
		ctxConventions = "";
		ctxPatterns = "";
		ctxCodeSnippets = "";
		ctxTestFramework = "";
		ctxTestPatterns = "";
		ctxDocumentation = "";
		lastSyncedContextProfile = null;
		forgeSession.updateDraft({
			contextProfile: null,
			contextSource: null,
			activeTemplateId: null,
		});
	}

	async function loadAndApplyProjectContext(projectId: string) {
		const detail = await fetchProject(projectId);
		if (detail?.context_profile) {
			applyContext(detail.context_profile, "project");
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
			if (match?.has_context) {
				lastAutoResolvedProject = currentProject;
				loadAndApplyProjectContext(match.id);
			}
		}
		if (!currentProject) {
			lastAutoResolvedProject = "";
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
		<Tooltip text="Provide codebase metadata for grounded optimization"
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
		{/if}
		{#if hasContextData && !forgeSession.draft.contextSource}
			<span class="collapsible-indicator bg-neon-green"></span>
		{/if}
	</Collapsible.Trigger>
	<Collapsible.Content>
		<div class="ctx-zone px-1.5 pt-0.5 pb-1" data-testid="context-fields">
			<p class="mb-1 text-[9px] leading-snug text-text-dim">
				All fields optional. Providing context grounds the
				optimization in your actual codebase.
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

			<!-- Stack Identity -->
			<div class="ctx-group-label">Stack</div>
			<div class="grid grid-cols-1 gap-1.5 {compact ? '' : 'sm:grid-cols-3'}">
				<div class="ctx-field">
					<label for="pop-ctx-lang" class="ctx-field-label"
						>Language</label
					>
					<input
						id="pop-ctx-lang"
						type="text"
						bind:value={ctxLanguage}
						onchange={syncContextToDraft}
						placeholder="e.g. TypeScript"
						list="pop-ctx-languages"
						data-testid="ctx-language"
						class="ctx-input"
					/>
					<datalist id="pop-ctx-languages">
						<option value="Python"></option>
						<option value="TypeScript"></option>
						<option value="JavaScript"></option>
						<option value="Rust"></option>
						<option value="Go"></option>
						<option value="Java"></option>
						<option value="C#"></option>
						<option value="C++"></option>
						<option value="Ruby"></option>
						<option value="PHP"></option>
						<option value="Swift"></option>
						<option value="Kotlin"></option>
					</datalist>
				</div>
				<div class="ctx-field">
					<label for="pop-ctx-fw" class="ctx-field-label"
						>Framework</label
					>
					<input
						id="pop-ctx-fw"
						type="text"
						bind:value={ctxFramework}
						onchange={syncContextToDraft}
						placeholder="e.g. SvelteKit"
						data-testid="ctx-framework"
						class="ctx-input"
					/>
				</div>
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
			</div>

			<!-- Description -->
			<div class="ctx-field mt-2">
				<label for="pop-ctx-desc" class="ctx-field-label"
					>Description</label
				>
				<textarea
					id="pop-ctx-desc"
					bind:value={ctxDescription}
					onchange={syncContextToDraft}
					placeholder="What does this project do?"
					rows="2"
					data-testid="ctx-description"
					class="ctx-input resize-none"
				></textarea>
			</div>

			<!-- Architecture -->
			<div class="ctx-group-label mt-2">Architecture</div>
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

			<!-- Code Reference -->
			<div class="ctx-field mt-2">
				<label for="pop-ctx-code" class="ctx-field-label"
					>Code Snippets</label
				>
				<textarea
					id="pop-ctx-code"
					bind:value={ctxCodeSnippets}
					onchange={syncContextToDraft}
					placeholder="One per line"
					rows="3"
					data-testid="ctx-code-snippets"
					class="ctx-input ctx-code-well resize-none font-mono text-xs"
				></textarea>
			</div>

			<!-- Testing & Docs -->
			<div class="ctx-group-label mt-2">Testing & Docs</div>
			<div class="grid grid-cols-1 gap-1.5 {compact ? '' : 'sm:grid-cols-2'}">
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
				<div class="ctx-field">
					<label for="pop-ctx-doc" class="ctx-field-label"
						>Documentation</label
					>
					<textarea
						id="pop-ctx-doc"
						bind:value={ctxDocumentation}
						onchange={syncContextToDraft}
						placeholder="Notes, links, references"
						rows="2"
						data-testid="ctx-documentation"
						class="ctx-input resize-none"
					></textarea>
				</div>
			</div>
		</div>
	</Collapsible.Content>
</Collapsible.Root>
