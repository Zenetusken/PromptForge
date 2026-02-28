<script lang="ts">
	import { fetchProjects, createProject, addProjectPrompt, deleteProjectPrompt, type ProjectDetail, type ProjectPrompt } from '$lib/api/client';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { clipboardService } from '$lib/services/clipboardService.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import Icon from './Icon.svelte';
	import { EmptyState } from './ui';
	import { onMount } from 'svelte';

	interface BuiltinTemplate {
		name: string;
		category: string;
		icon: string;
		prompt: string;
		builtin: true;
	}

	interface CustomTemplate {
		name: string;
		category: string;
		icon: string;
		prompt: string;
		builtin: false;
		promptId: string;
		projectId: string;
	}

	type Template = BuiltinTemplate | CustomTemplate;

	const TEMPLATES_PROJECT_NAME = '__templates__';

	const BUILTIN_TEMPLATES: BuiltinTemplate[] = [
		{
			name: 'Code Review',
			category: 'Engineering',
			icon: 'code',
			prompt: 'Review this code for correctness, performance issues, and adherence to best practices. Suggest specific refactors with code examples and explain the reasoning behind each change.',
			builtin: true,
		},
		{
			name: 'API Documentation',
			category: 'Engineering',
			icon: 'file-text',
			prompt: 'Create comprehensive API documentation for a REST endpoint including description, authentication requirements, request/response schemas with examples, error codes, and rate limiting details.',
			builtin: true,
		},
		{
			name: 'Bug Report Analysis',
			category: 'Engineering',
			icon: 'alert-triangle',
			prompt: 'Analyze this bug report and provide: (1) most likely root cause, (2) steps to reproduce, (3) potential fix with code example, (4) regression test suggestion.',
			builtin: true,
		},
		{
			name: 'Marketing Email',
			category: 'Marketing',
			icon: 'mail',
			prompt: 'Write a compelling product launch email for a B2B SaaS audience. Include a subject line, preview text, hero section, three benefit-driven paragraphs, social proof, and a clear call-to-action.',
			builtin: true,
		},
		{
			name: 'User Research Questions',
			category: 'Product',
			icon: 'users',
			prompt: 'Generate 10 open-ended user research questions for a product discovery interview. Questions should explore pain points, current workflows, unmet needs, and willingness to pay. Avoid leading questions.',
			builtin: true,
		},
		{
			name: 'Error Messages',
			category: 'UX',
			icon: 'x-circle',
			prompt: 'Design user-friendly error messages for a web application covering validation failures, network errors, authentication issues, and permission denials. Each message should explain what went wrong and how to fix it.',
			builtin: true,
		},
		{
			name: 'Data Analysis',
			category: 'Analytics',
			icon: 'bar-chart',
			prompt: 'Analyze this dataset and provide: (1) key statistical summaries, (2) notable trends or patterns, (3) potential outliers, (4) actionable insights, (5) recommended visualizations.',
			builtin: true,
		},
		{
			name: 'System Architecture',
			category: 'Engineering',
			icon: 'layers',
			prompt: 'Design a system architecture for this use case. Include: component diagram, data flow, technology stack recommendation, scalability considerations, and failure modes with mitigation strategies.',
			builtin: true,
		},
		{
			name: 'Content Brief',
			category: 'Marketing',
			icon: 'edit',
			prompt: 'Create a comprehensive content brief including target audience, key messages, tone of voice, SEO keywords, content structure outline, internal/external linking strategy, and success metrics.',
			builtin: true,
		},
		{
			name: 'Test Plan',
			category: 'QA',
			icon: 'check-square',
			prompt: 'Create a test plan covering: unit tests, integration tests, edge cases, performance tests, and accessibility checks. Include specific test cases with expected inputs and outputs.',
			builtin: true,
		},
	];

	let searchQuery = $state('');
	let selectedCategory = $state('');
	let customTemplates: CustomTemplate[] = $state([]);
	let templatesProjectId: string | null = $state(null);
	let saving = $state(false);

	// Save-as-template form
	let showSaveForm = $state(false);
	let saveTemplateName = $state('');
	let saveTemplateCategory = $state('Custom');
	let saveTemplatePrompt = $state('');

	let allTemplates = $derived<Template[]>([...customTemplates, ...BUILTIN_TEMPLATES]);

	let categories = $derived([...new Set(allTemplates.map(t => t.category))].sort());

	let filtered = $derived.by(() => {
		return allTemplates.filter(t => {
			if (selectedCategory && t.category !== selectedCategory) return false;
			if (searchQuery) {
				const q = searchQuery.toLowerCase();
				return t.name.toLowerCase().includes(q) || t.prompt.toLowerCase().includes(q) || t.category.toLowerCase().includes(q);
			}
			return true;
		});
	});

	async function loadCustomTemplates() {
		const resp = await fetchProjects({ search: TEMPLATES_PROJECT_NAME, per_page: 1 });
		const proj = resp.items.find(p => p.name === TEMPLATES_PROJECT_NAME);
		if (!proj) return;
		templatesProjectId = proj.id;
		// Fetch full project detail to get prompts
		const { fetchProject } = await import('$lib/api/client');
		const detail = await fetchProject(proj.id);
		if (!detail) return;
		customTemplates = detail.prompts.map(p => parseCustomTemplate(p, detail.id));
	}

	function parseCustomTemplate(p: ProjectPrompt, projectId: string): CustomTemplate {
		// Content format: "NAME\nCATEGORY\nPROMPT_TEXT"
		const lines = p.content.split('\n');
		const name = lines[0] || `Template #${p.order_index + 1}`;
		const category = lines[1] || 'Custom';
		const prompt = lines.slice(2).join('\n') || p.content;
		return {
			name,
			category,
			icon: 'file-text',
			prompt,
			builtin: false,
			promptId: p.id,
			projectId,
		};
	}

	async function ensureTemplatesProject(): Promise<string | null> {
		if (templatesProjectId) return templatesProjectId;
		const project = await createProject({ name: TEMPLATES_PROJECT_NAME, description: 'User-saved prompt templates' });
		if (!project) {
			toastState.show('Failed to create templates storage', 'error');
			return null;
		}
		templatesProjectId = project.id;
		return project.id;
	}

	async function saveTemplate() {
		if (!saveTemplateName.trim() || !saveTemplatePrompt.trim()) return;
		saving = true;
		try {
			const projectId = await ensureTemplatesProject();
			if (!projectId) return;
			// Store as "NAME\nCATEGORY\nPROMPT" format
			const content = `${saveTemplateName.trim()}\n${saveTemplateCategory.trim()}\n${saveTemplatePrompt.trim()}`;
			const result = await addProjectPrompt(projectId, content);
			if (result) {
				customTemplates = [...customTemplates, parseCustomTemplate(result, projectId)];
				toastState.show(`Template "${saveTemplateName}" saved`, 'success');
				showSaveForm = false;
				saveTemplateName = '';
				saveTemplateCategory = 'Custom';
				saveTemplatePrompt = '';
			}
		} finally {
			saving = false;
		}
	}

	async function deleteTemplate(template: CustomTemplate) {
		const ok = await deleteProjectPrompt(template.projectId, template.promptId);
		if (ok) {
			customTemplates = customTemplates.filter(t => t.promptId !== template.promptId);
			toastState.show(`Template "${template.name}" deleted`, 'success');
		}
	}

	function openSaveForm(prompt?: string) {
		saveTemplatePrompt = prompt || '';
		saveTemplateName = '';
		saveTemplateCategory = 'Custom';
		showSaveForm = true;
	}

	function openInIDE(prompt: string) {
		import('$lib/stores/forgeMachine.svelte').then(({ forgeMachine }) => {
			import('$lib/stores/forgeSession.svelte').then(({ forgeSession }) => {
				forgeMachine.restore();
				forgeSession.updateDraft({ text: prompt });
				forgeSession.activate();
				windowManager.openIDE();
				forgeSession.focusTextarea();
			});
		});
	}

	async function exportTemplates() {
		const data = allTemplates.map(({ name, category, prompt }) => ({ name, category, prompt }));
		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = 'promptforge-templates.json';
		a.click();
		URL.revokeObjectURL(url);
	}

	onMount(() => {
		loadCustomTemplates();
	});
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<!-- Header -->
	<div class="flex items-center gap-3 border-b border-neon-cyan/10 px-3 py-2">
		<div class="flex items-center gap-1.5 flex-1 bg-bg-input border border-neon-cyan/10 px-2 py-1">
			<Icon name="search" size={11} class="text-text-dim shrink-0" />
			<input
				id="template-search"
				type="text"
				placeholder="Search templates..."
				class="flex-1 bg-transparent text-xs text-text-primary placeholder:text-text-dim outline-none"
				bind:value={searchQuery}
			/>
		</div>
		<select
			id="template-category"
			class="bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1 outline-none"
			bind:value={selectedCategory}
		>
			<option value="">All Categories</option>
			{#each categories as cat}
				<option value={cat}>{cat}</option>
			{/each}
		</select>
		<button
			class="border border-neon-green/20 px-2 py-1 text-[10px] text-neon-green hover:bg-neon-green/10 transition-colors"
			onclick={() => openSaveForm()}
			title="Save a new template"
		>
			<Icon name="plus" size={11} />
		</button>
		<button
			class="border border-neon-cyan/10 px-2 py-1 text-[10px] text-text-dim hover:text-neon-cyan transition-colors"
			onclick={exportTemplates}
			title="Export all templates"
		>
			<Icon name="download" size={11} />
		</button>
	</div>

	<!-- Save template form -->
	{#if showSaveForm}
		<div class="border-b border-neon-green/10 bg-bg-secondary px-3 py-3 space-y-2">
			<div class="text-[10px] text-neon-green uppercase tracking-wider font-medium">Save Template</div>
			<div class="flex gap-2">
				<input
					id="template-save-name"
					type="text"
					placeholder="Template name"
					class="flex-1 bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1 outline-none"
					bind:value={saveTemplateName}
				/>
				<input
					id="template-save-category"
					type="text"
					placeholder="Category"
					class="w-28 bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1 outline-none"
					bind:value={saveTemplateCategory}
				/>
			</div>
			<textarea
				id="template-save-prompt"
				placeholder="Prompt text..."
				class="w-full bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1.5 outline-none resize-none h-16"
				bind:value={saveTemplatePrompt}
			></textarea>
			<div class="flex items-center gap-2">
				<button
					class="border border-neon-green/30 text-neon-green text-[10px] px-3 py-1 hover:bg-neon-green/10 transition-colors disabled:opacity-30"
					onclick={saveTemplate}
					disabled={saving || !saveTemplateName.trim() || !saveTemplatePrompt.trim()}
				>
					{saving ? 'Saving...' : 'Save'}
				</button>
				<button
					class="text-[10px] text-text-dim hover:text-text-secondary px-2 py-1"
					onclick={() => showSaveForm = false}
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}

	<!-- Template grid -->
	<div class="flex-1 overflow-y-auto p-3">
		{#if filtered.length === 0}
			<EmptyState icon="file-text" message="No templates match your search" />
		{:else}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
				{#each filtered as template (template.builtin ? template.name : template.promptId)}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						class="border border-neon-cyan/10 p-3 space-y-2 hover:border-neon-cyan/20 transition-colors cursor-pointer group"
						ondblclick={() => openInIDE(template.prompt)}
					>
						<div class="flex items-center gap-2">
							<Icon name={template.icon as any} size={12} class="{template.builtin ? 'text-neon-cyan' : 'text-neon-green'} shrink-0" />
							<span class="text-[11px] text-text-primary font-medium flex-1">{template.name}</span>
							{#if !template.builtin}
								<span class="text-[9px] text-neon-green/60 uppercase tracking-wider">custom</span>
							{/if}
							<span class="text-[9px] text-text-dim uppercase tracking-wider">{template.category}</span>
						</div>
						<p class="text-[10px] text-text-secondary line-clamp-2">{template.prompt}</p>
						<div class="flex items-center gap-2 pt-1">
							<button
								class="text-[10px] text-neon-cyan hover:text-neon-cyan/80 transition-colors opacity-0 group-hover:opacity-100"
								onclick={() => openInIDE(template.prompt)}
							>
								Forge
							</button>
							<button
								class="text-[10px] text-text-dim hover:text-text-secondary transition-colors opacity-0 group-hover:opacity-100"
								onclick={async () => {
									await clipboardService.copy(template.prompt, template.name, 'template');
								}}
							>
								Copy
							</button>
							{#if template.builtin}
								<button
									class="text-[10px] text-text-dim hover:text-neon-green transition-colors opacity-0 group-hover:opacity-100"
									onclick={() => openSaveForm(template.prompt)}
								>
									Save as
								</button>
							{:else}
								<button
									class="text-[10px] text-text-dim hover:text-neon-red transition-colors opacity-0 group-hover:opacity-100"
									onclick={() => deleteTemplate(template as CustomTemplate)}
								>
									Delete
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Footer -->
	<div class="flex items-center justify-between border-t border-neon-cyan/10 px-3 py-1.5">
		<span class="text-[10px] text-text-dim">{filtered.length} of {allTemplates.length} templates ({customTemplates.length} custom)</span>
		<span class="text-[10px] text-text-dim">Double-click to forge</span>
	</div>
</div>
