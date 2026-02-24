<script lang="ts">
	import type { CodebaseContext } from '$lib/api/client';
	import { STACK_TEMPLATES } from '$lib/utils/stackTemplates';

	let {
		value = {},
		onsave,
		readonly = false,
		showTemplates = true,
	}: {
		value: CodebaseContext;
		onsave: (ctx: CodebaseContext) => void;
		readonly?: boolean;
		showTemplates?: boolean;
	} = $props();

	// Local editable copies
	let language = $state('');
	let framework = $state('');
	let description = $state('');
	let conventions = $state('');
	let patterns = $state('');
	let codeSnippets = $state('');
	let testFramework = $state('');
	let testPatterns = $state('');
	let documentation = $state('');

	// Normalize array-or-string fields (MCP may send strings instead of arrays)
	function toLines(val: string | string[] | undefined): string {
		if (!val) return '';
		if (Array.isArray(val)) return val.join('\n');
		return String(val);
	}

	// Sync from prop on mount / when value changes
	$effect(() => {
		language = value.language ?? '';
		framework = value.framework ?? '';
		description = value.description ?? '';
		conventions = toLines(value.conventions);
		patterns = toLines(value.patterns);
		codeSnippets = toLines(value.code_snippets);
		testFramework = value.test_framework ?? '';
		testPatterns = toLines(value.test_patterns);
		documentation = value.documentation ?? '';
	});

	let activeTemplateId: string | null = $state(null);

	let hasData = $derived(
		!!(language || framework || description || conventions ||
		   patterns || codeSnippets || testFramework || testPatterns || documentation)
	);

	let isDirty = $derived.by(() => {
		const current = buildContext();
		return JSON.stringify(current) !== JSON.stringify(cleanContext(value));
	});

	function cleanContext(ctx: CodebaseContext): CodebaseContext {
		const cleaned: CodebaseContext = {};
		if (ctx.language) cleaned.language = ctx.language;
		if (ctx.framework) cleaned.framework = ctx.framework;
		if (ctx.description) cleaned.description = ctx.description;
		const conv = toLines(ctx.conventions);
		if (conv) cleaned.conventions = conv.split('\n').filter(Boolean);
		const pat = toLines(ctx.patterns);
		if (pat) cleaned.patterns = pat.split('\n').filter(Boolean);
		const snip = toLines(ctx.code_snippets);
		if (snip) cleaned.code_snippets = snip.split('\n').filter(Boolean);
		if (ctx.test_framework) cleaned.test_framework = ctx.test_framework;
		const tp = toLines(ctx.test_patterns);
		if (tp) cleaned.test_patterns = tp.split('\n').filter(Boolean);
		if (ctx.documentation) cleaned.documentation = ctx.documentation;
		return cleaned;
	}

	function buildContext(): CodebaseContext {
		const ctx: CodebaseContext = {};
		if (language.trim()) ctx.language = language.trim();
		if (framework.trim()) ctx.framework = framework.trim();
		if (description.trim()) ctx.description = description.trim();
		if (conventions.trim()) {
			const items = conventions.split('\n').map(s => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.conventions = items;
		}
		if (patterns.trim()) {
			const items = patterns.split('\n').map(s => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.patterns = items;
		}
		if (codeSnippets.trim()) {
			const items = codeSnippets.split('\n').map(s => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.code_snippets = items;
		}
		if (testFramework.trim()) ctx.test_framework = testFramework.trim();
		if (testPatterns.trim()) {
			const items = testPatterns.split('\n').map(s => s.trim()).filter(Boolean);
			if (items.length > 0) ctx.test_patterns = items;
		}
		if (documentation.trim()) ctx.documentation = documentation.trim();
		return ctx;
	}

	function handleSave() {
		onsave(buildContext());
	}

	function handleClear() {
		language = '';
		framework = '';
		description = '';
		conventions = '';
		patterns = '';
		codeSnippets = '';
		testFramework = '';
		testPatterns = '';
		documentation = '';
		activeTemplateId = null;
	}

	function applyTemplate(ctx: CodebaseContext, templateId?: string) {
		language = ctx.language ?? '';
		framework = ctx.framework ?? '';
		description = ctx.description ?? '';
		conventions = toLines(ctx.conventions);
		patterns = toLines(ctx.patterns);
		codeSnippets = toLines(ctx.code_snippets);
		testFramework = ctx.test_framework ?? '';
		testPatterns = toLines(ctx.test_patterns);
		documentation = ctx.documentation ?? '';
		activeTemplateId = templateId ?? null;
	}
</script>

<div class="ctx-editor space-y-2">
	{#if showTemplates && !readonly}
		<div class="flex flex-wrap items-center gap-1.5">
			{#each STACK_TEMPLATES as tmpl (tmpl.id)}
				<button
					type="button"
					class="ctx-template-chip {activeTemplateId === tmpl.id
						? 'bg-neon-green/12 border-neon-green/35 text-neon-green'
						: 'border-border-subtle text-text-dim hover:border-neon-green/25 hover:text-neon-green/80'}"
					title={tmpl.description}
					onclick={() => applyTemplate(tmpl.context, tmpl.id)}
				>{tmpl.name}</button>
			{/each}
		</div>
	{/if}

	<!-- ─── Stack Identity ─── -->
	<div>
		<div class="ctx-group-label">Stack</div>
		<div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
			<div class="ctx-field">
				<label for="cpe-lang" class="ctx-field-label">Language</label>
				<input
					id="cpe-lang"
					type="text"
					bind:value={language}
					placeholder="e.g. TypeScript"
					aria-label="Programming language"
					{readonly}
					class="ctx-input"
				/>
			</div>
			<div class="ctx-field">
				<label for="cpe-fw" class="ctx-field-label">Framework</label>
				<input
					id="cpe-fw"
					type="text"
					bind:value={framework}
					placeholder="e.g. SvelteKit"
					aria-label="Framework"
					{readonly}
					class="ctx-input"
				/>
			</div>
			<div class="ctx-field">
				<label for="cpe-tf" class="ctx-field-label">Test Framework</label>
				<input
					id="cpe-tf"
					type="text"
					bind:value={testFramework}
					placeholder="e.g. vitest"
					aria-label="Test framework"
					{readonly}
					class="ctx-input"
				/>
			</div>
		</div>
	</div>

	<!-- ─── Description ─── -->
	<div class="ctx-field">
		<label for="cpe-desc" class="ctx-field-label">Description</label>
		<textarea
			id="cpe-desc"
			bind:value={description}
			placeholder="What does this project do?"
			aria-label="Project description"
			rows="2"
			{readonly}
			class="ctx-input resize-none"
		></textarea>
	</div>

	<!-- ─── Architecture ─── -->
	<div>
		<div class="ctx-group-label">Architecture</div>
		<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
			<div class="ctx-field">
				<label for="cpe-conv" class="ctx-field-label">Conventions</label>
				<textarea
					id="cpe-conv"
					bind:value={conventions}
					placeholder="One per line"
					aria-label="Coding conventions"
					rows="3"
					{readonly}
					class="ctx-input resize-none"
				></textarea>
			</div>
			<div class="ctx-field">
				<label for="cpe-pat" class="ctx-field-label">Patterns</label>
				<textarea
					id="cpe-pat"
					bind:value={patterns}
					placeholder="One per line"
					aria-label="Design patterns"
					rows="3"
					{readonly}
					class="ctx-input resize-none"
				></textarea>
			</div>
		</div>
	</div>

	<!-- ─── Code Reference ─── -->
	<div class="ctx-field">
		<label for="cpe-code" class="ctx-field-label">Code Snippets</label>
		<textarea
			id="cpe-code"
			bind:value={codeSnippets}
			placeholder="One per line"
			aria-label="Code snippets"
			rows="3"
			{readonly}
			class="ctx-input ctx-code-well resize-none font-mono text-xs"
		></textarea>
	</div>

	<!-- ─── Testing & Docs ─── -->
	<div>
		<div class="ctx-group-label">Testing & Docs</div>
		<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
			<div class="ctx-field">
				<label for="cpe-tp" class="ctx-field-label">Test Patterns</label>
				<textarea
					id="cpe-tp"
					bind:value={testPatterns}
					placeholder="One per line"
					aria-label="Test patterns"
					rows="2"
					{readonly}
					class="ctx-input resize-none"
				></textarea>
			</div>
			<div class="ctx-field">
				<label for="cpe-doc" class="ctx-field-label">Documentation</label>
				<textarea
					id="cpe-doc"
					bind:value={documentation}
					placeholder="Notes, links, references"
					aria-label="Documentation"
					rows="2"
					{readonly}
					class="ctx-input resize-none"
				></textarea>
			</div>
		</div>
	</div>

	{#if !readonly}
		<div class="flex items-center gap-1.5 pt-0.5">
			<button
				type="button"
				class="rounded-md bg-neon-green/15 px-2 py-0.5 text-[11px] font-medium text-neon-green transition-all hover:bg-neon-green/25 disabled:opacity-40"
				disabled={!isDirty}
				onclick={handleSave}
			>Save Context</button>
			{#if hasData}
				<button
					type="button"
					class="ctx-template-chip border-neon-red/15 text-neon-red/40 hover:border-neon-red/30 hover:text-neon-red/70"
					onclick={handleClear}
				>Clear all</button>
			{/if}
			{#if isDirty}
				<span class="text-[10px] text-neon-yellow/60">Unsaved changes</span>
			{/if}
		</div>
	{/if}
</div>
