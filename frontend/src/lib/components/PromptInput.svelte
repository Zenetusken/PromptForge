<script lang="ts">
	import { promptState } from '$lib/stores/prompt.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import type { OptimizeMetadata } from '$lib/api/client';
	import { checkDuplicateTitle } from '$lib/api/client';
	import Icon from './Icon.svelte';
	import ProviderSelector from './ProviderSelector.svelte';
	import { Collapsible } from 'bits-ui';
	import { Separator, Tooltip } from './ui';

	let {
		onsubmit,
		oncancel,
		disabled = false
	}: {
		onsubmit: (prompt: string, metadata?: OptimizeMetadata) => void;
		oncancel?: () => void;
		disabled?: boolean;
	} = $props();

	let prompt = $state('');
	let charCount = $derived(prompt.length);
	let textareaEl: HTMLTextAreaElement | undefined = $state();

	// Track the last value synced from the store to avoid infinite loops
	let lastSyncedFromStore = '';

	// Metadata fields
	let showMetadata = $state(false);
	let title = $state('');
	let project = $state('');
	let tagsInput = $state('');
	let version = $state('');

	// Source action from project navigation (consumed once then cleared)
	let sourceAction: 'optimize' | 'reiterate' | null = $state(null);

	// Prompt ID from project detail (consumed once then cleared)
	let promptId = $state('');

	// Validation errors (only shown when sourceAction is set)
	let validationErrors: Record<string, string> = $state({});

	// Duplicate title warning (non-blocking)
	let duplicateTitleWarning = $state(false);
	let duplicateCheckTimer: ReturnType<typeof setTimeout> | undefined;

	// Strategy override
	let showAdvanced = $state(false);
	let selectedStrategy = $state('auto');
	let selectedSecondary = $state<string[]>([]);

	const STRATEGY_OPTIONS: { value: string; label: string; description: string; category?: string }[] = [
		{ value: 'auto', label: 'Auto', description: 'AI selects the best framework combination' },
		{ value: 'co-star', label: 'CO-STAR', description: 'Context, Objective, Style, Tone, Audience, Response', category: 'Frameworks' },
		{ value: 'risen', label: 'RISEN', description: 'Role, Instructions, Steps, End-goal, Narrowing', category: 'Frameworks' },
		{ value: 'role-task-format', label: 'Role-Task-Format', description: 'Role + task description + output format', category: 'Frameworks' },
		{ value: 'chain-of-thought', label: 'Chain of Thought', description: 'Step-by-step reasoning scaffolding', category: 'Techniques' },
		{ value: 'few-shot-scaffolding', label: 'Few-Shot', description: 'Input/output example pairs', category: 'Techniques' },
		{ value: 'step-by-step', label: 'Step by Step', description: 'Numbered sequential instructions', category: 'Techniques' },
		{ value: 'structured-output', label: 'Structured Output', description: 'JSON, markdown, table format spec', category: 'Techniques' },
		{ value: 'constraint-injection', label: 'Constraint Injection', description: 'Explicit do/don\'t rules and boundaries', category: 'Techniques' },
		{ value: 'context-enrichment', label: 'Context Enrichment', description: 'Background info, domain context', category: 'Techniques' },
		{ value: 'persona-assignment', label: 'Persona Assignment', description: 'Expert role with domain expertise', category: 'Techniques' },
	];

	// Group strategies by category for rendering (static — STRATEGY_OPTIONS is const)
	const strategyCategories = (() => {
		const ungrouped = STRATEGY_OPTIONS.filter(o => !o.category);
		const categoryMap = new Map<string, typeof STRATEGY_OPTIONS>();
		for (const opt of STRATEGY_OPTIONS) {
			if (opt.category) {
				if (!categoryMap.has(opt.category)) categoryMap.set(opt.category, []);
				categoryMap.get(opt.category)!.push(opt);
			}
		}
		return { ungrouped, categories: [...categoryMap.entries()] };
	})();

	function toggleSecondary(value: string) {
		if (selectedSecondary.includes(value)) {
			selectedSecondary = selectedSecondary.filter(v => v !== value);
		} else if (selectedSecondary.length < 2) {
			selectedSecondary = [...selectedSecondary, value];
		} else {
			// Replace oldest selection
			selectedSecondary = [selectedSecondary[1], value];
		}
	}

	// Clear secondaries that match the new primary when it changes
	$effect(() => {
		if (selectedStrategy !== 'auto') {
			selectedSecondary = selectedSecondary.filter(v => v !== selectedStrategy);
		}
	});

	// Debounced duplicate title check
	$effect(() => {
		const currentTitle = title;
		const currentProject = project;
		clearTimeout(duplicateCheckTimer);
		duplicateTitleWarning = false;
		if (currentTitle.trim() && currentProject.trim()) {
			duplicateCheckTimer = setTimeout(async () => {
				const isDup = await checkDuplicateTitle(currentTitle.trim(), currentProject.trim());
				duplicateTitleWarning = isDup;
			}, 500);
		}
	});

	function validateFields(): boolean {
		const errors: Record<string, string> = {};

		// Validation only applies when navigating from a project
		if (!sourceAction) return true;

		if (!project.trim()) errors.project = 'Project is required';
		if (!title.trim()) errors.title = 'Title is required';
		if (!version.trim()) {
			errors.version = 'Version is required';
		} else if (!/^v\d+$/i.test(version.trim())) {
			errors.version = 'Must be v<number> (e.g. v1)';
		}

		if (tagsInput.trim()) {
			const tags = tagsInput.split(',').map(t => t.trim()).filter(Boolean);
			if (new Set(tags).size < tags.length) {
				errors.tags = 'Duplicate tags found';
			}
		}

		validationErrors = errors;
		return Object.keys(errors).length === 0;
	}

	function buildMetadata(): OptimizeMetadata | undefined {
		const meta: OptimizeMetadata = {};
		if (title.trim()) meta.title = title.trim();
		if (project.trim()) meta.project = project.trim();
		if (tagsInput.trim()) {
			const tags = tagsInput.split(',').map(t => t.trim()).filter(Boolean);
			if (tags.length > 0) meta.tags = tags;
		}
		if (version.trim()) meta.version = version.trim();
		if (providerState.selectedProvider) meta.provider = providerState.selectedProvider;
		if (selectedStrategy !== 'auto') meta.strategy = selectedStrategy;
		if (selectedSecondary.length > 0) meta.secondary_frameworks = selectedSecondary;
		if (promptId) {
			meta.prompt_id = promptId;
		}
		return Object.keys(meta).length > 0 ? meta : undefined;
	}

	function handleSubmit() {
		if (prompt.trim() && !disabled) {
			// Strip project metadata if the project is archived
			if (project.trim()) {
				const archivedProject = projectsState.allItems.find(
					(p) => p.name === project.trim() && p.status === 'archived'
				);
				if (archivedProject) {
					project = '';
					promptId = '';
					sourceAction = null;
					toastState.show('Project is archived — submitting without project link', 'info');
				}
			}

			if (!validateFields()) return;

			onsubmit(prompt.trim(), buildMetadata());
			// Clear source action after successful submit
			sourceAction = null;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
			e.preventDefault();
			handleSubmit();
		}
	}

	$effect(() => {
		if (textareaEl) {
			textareaEl.focus();
		}
	});

	// Auto-resize textarea to fit content, capped at 300px
	function autoResize() {
		if (!textareaEl) return;
		textareaEl.style.height = 'auto';
		textareaEl.style.height = Math.min(textareaEl.scrollHeight, 300) + 'px';
	}

	$effect(() => {
		if (prompt !== undefined && textareaEl) {
			// Schedule auto-resize after DOM update
			queueMicrotask(autoResize);
		}
	});

	$effect(() => {
		const storeText = promptState.text;
		if (storeText !== lastSyncedFromStore) {
			lastSyncedFromStore = storeText;
			prompt = storeText;
			// Auto-fill project name from store (e.g. when "Optimize" clicked from project detail)
			if (promptState.projectName) {
				project = promptState.projectName;
				promptState.projectName = '';
			}
			// Carry prompt_id linkage from project detail
			if (promptState.promptId) {
				promptId = promptState.promptId;
				promptState.promptId = '';
			}
			// Carry title from store
			if (promptState.title) {
				title = promptState.title;
				promptState.title = '';
			}
			// Carry tags from store
			if (promptState.tags.length > 0) {
				tagsInput = promptState.tags.join(', ');
				promptState.tags = [];
			}
			// Carry version from store
			if (promptState.version) {
				version = promptState.version;
				promptState.version = '';
			}
			// Carry source action and auto-expand metadata
			if (promptState.sourceAction) {
				sourceAction = promptState.sourceAction;
				promptState.sourceAction = null;
				showMetadata = true;
			}
			if (storeText && textareaEl) {
				textareaEl.focus();
			}
		}
	});
</script>

<div class="prompt-container relative rounded-xl border border-text-dim/15 bg-bg-card shadow-sm shadow-black/30 transition-[border-color,box-shadow] duration-300">
	<!-- Top edge glow line -->
	<div class="glow-line absolute -top-px left-8 right-8 h-px opacity-0 transition-opacity duration-500"></div>

	<div class="px-4 pt-3 pb-2">
		<textarea
			data-testid="prompt-textarea"
			bind:this={textareaEl}
			bind:value={prompt}
			onkeydown={handleKeydown}
			{disabled}
			placeholder="Describe what you want your prompt to do..."
			aria-label="Enter your prompt for optimization"
			rows="3"
			class="w-full resize-none bg-transparent text-[15px] leading-relaxed text-text-primary outline-none placeholder:text-text-dim disabled:opacity-50"
			style="max-height: 300px; overflow-y: auto;"
		></textarea>
	</div>

	<!-- Metadata Section -->
	<Separator />
	<Collapsible.Root bind:open={showMetadata}>
		<Collapsible.Trigger
			class="collapsible-toggle"
			style="--toggle-accent: var(--color-neon-cyan)"
			data-testid="metadata-toggle"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="transition-transform duration-200 {showMetadata ? 'rotate-90' : ''}"
			/>
			<Tooltip text="Add title, tags, and project"><span>Metadata</span></Tooltip>
			{#if title || project || tagsInput || version}
				<span class="collapsible-indicator bg-neon-cyan"></span>
			{/if}
		</Collapsible.Trigger>
		<Collapsible.Content>
			<div class="px-4 pt-1 pb-3" data-testid="metadata-fields">
				<div class="grid grid-cols-1 gap-2 sm:grid-cols-4">
					<div>
						<input
							type="text"
							bind:value={title}
							placeholder="Title"
							aria-label="Optimization title"
							data-testid="metadata-title"
							class="input-field w-full py-2 text-sm {validationErrors.title ? 'border-neon-red/50' : ''}"
						/>
						{#if validationErrors.title}
							<p class="mt-0.5 text-[10px] text-neon-red">{validationErrors.title}</p>
						{/if}
						{#if duplicateTitleWarning}
							<p class="mt-0.5 text-[10px] text-neon-yellow">Title already exists in this project</p>
						{/if}
					</div>
					<div class="max-w-[100px]">
						<input
							type="text"
							bind:value={version}
							placeholder="Version"
							aria-label="Version"
							data-testid="metadata-version"
							class="input-field w-full py-2 text-sm {validationErrors.version ? 'border-neon-red/50' : ''}"
						/>
						{#if validationErrors.version}
							<p class="mt-0.5 text-[10px] text-neon-red">{validationErrors.version}</p>
						{/if}
					</div>
					<div>
						<input
							type="text"
							bind:value={project}
							placeholder="Project"
							aria-label="Project name"
							data-testid="metadata-project"
							disabled={!!sourceAction}
							class="input-field w-full py-2 text-sm {validationErrors.project ? 'border-neon-red/50' : ''} {sourceAction ? 'opacity-60 cursor-not-allowed' : ''}"
						/>
						{#if validationErrors.project}
							<p class="mt-0.5 text-[10px] text-neon-red">{validationErrors.project}</p>
						{/if}
					</div>
					<div>
						<input
							type="text"
							bind:value={tagsInput}
							placeholder="Tags (comma-separated)"
							aria-label="Tags"
							data-testid="metadata-tags"
							class="input-field w-full py-2 text-sm {validationErrors.tags ? 'border-neon-red/50' : ''}"
						/>
						{#if validationErrors.tags}
							<p class="mt-0.5 text-[10px] text-neon-red">{validationErrors.tags}</p>
						{/if}
					</div>
				</div>
			</div>
		</Collapsible.Content>
	</Collapsible.Root>

	<!-- Advanced Section (Strategy Override) -->
	<Separator />
	<Collapsible.Root bind:open={showAdvanced}>
		<Collapsible.Trigger
			class="collapsible-toggle"
			style="--toggle-accent: var(--color-neon-purple)"
			data-testid="advanced-toggle"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="transition-transform duration-200 {showAdvanced ? 'rotate-90' : ''}"
			/>
			<Tooltip text="Override automatic strategy selection"><span>Strategy</span></Tooltip>
			{#if selectedStrategy !== 'auto'}
				<span class="collapsible-indicator bg-neon-purple"></span>
				<span class="chip bg-neon-purple/10 text-neon-purple">
					{selectedStrategy}
				</span>
				{#if selectedSecondary.length > 0}
					<Tooltip text="{selectedSecondary.length} secondary {selectedSecondary.length === 1 ? 'framework' : 'frameworks'} selected">
						<span class="chip bg-neon-cyan/10 text-neon-cyan">
							+{selectedSecondary.length}
						</span>
					</Tooltip>
				{/if}
			{/if}
		</Collapsible.Trigger>
		<Collapsible.Content>
			<div class="px-4 pb-3" data-testid="advanced-fields">
				<!-- Ungrouped (Auto) -->
				{#each strategyCategories.ungrouped as option}
					<label
						class="mb-1.5 flex cursor-pointer items-start gap-2.5 rounded-lg px-3 py-2 transition-colors focus-within:ring-2 focus-within:ring-neon-cyan/40
							{selectedStrategy === option.value ? 'bg-neon-purple/8 border border-neon-purple/20' : 'border border-transparent hover:bg-bg-hover/40'}"
					>
						<input
							type="radio"
							name="strategy"
							value={option.value}
							bind:group={selectedStrategy}
							class="mt-0.5 accent-neon-purple"
							data-testid="strategy-option-{option.value}"
						/>
						<div class="min-w-0">
							<span class="text-sm font-medium {selectedStrategy === option.value ? 'text-neon-purple' : 'text-text-primary'}">
								{option.label}
							</span>
							<p class="text-[11px] text-text-dim">{option.description}</p>
						</div>
					</label>
				{/each}

				<!-- Category groups -->
				{#each strategyCategories.categories as [categoryName, categoryOptions]}
					<div class="mt-2 mb-1">
						<span class="text-[10px] font-semibold uppercase tracking-wider text-text-dim/60">
							{categoryName}
						</span>
					</div>
					<div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
						{#each categoryOptions as option}
							<label
								class="flex cursor-pointer items-start gap-2.5 rounded-lg px-3 py-2 transition-colors focus-within:ring-2 focus-within:ring-neon-cyan/40
									{selectedStrategy === option.value ? 'bg-neon-purple/8 border border-neon-purple/20' : 'border border-transparent hover:bg-bg-hover/40'}"
							>
								<input
									type="radio"
									name="strategy"
									value={option.value}
									bind:group={selectedStrategy}
									class="mt-0.5 accent-neon-purple"
									data-testid="strategy-option-{option.value}"
								/>
								<div class="min-w-0">
									<span class="text-sm font-medium {selectedStrategy === option.value ? 'text-neon-purple' : 'text-text-primary'}">
										{option.label}
									</span>
									<p class="text-[11px] text-text-dim">{option.description}</p>
								</div>
							</label>
						{/each}
					</div>
				{/each}

				{#if selectedStrategy !== 'auto'}
					<div class="mt-3 border-t border-border-subtle pt-2">
						<p class="mb-1.5 text-[11px] text-text-dim">
							Secondary frameworks <span class="text-text-dim/50">(optional, max 2)</span>
						</p>
						<div class="flex flex-wrap gap-1.5">
							{#each STRATEGY_OPTIONS.filter(o => o.value !== 'auto' && o.value !== selectedStrategy) as option}
								<Tooltip text={option.description}><button
									type="button"
									onclick={() => toggleSecondary(option.value)}
									data-testid="secondary-{option.value}"
									class="chip chip-interactive transition-colors
										{selectedSecondary.includes(option.value)
											? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/30'
											: 'bg-bg-hover/30 text-text-dim border border-transparent hover:text-text-secondary hover:bg-bg-hover/50'}"
								>
									{selectedSecondary.includes(option.value) ? '+ ' : ''}{option.label}
								</button></Tooltip>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		</Collapsible.Content>
	</Collapsible.Root>

	<!-- ARIA live region for strategy changes -->
	<div class="sr-only" role="status" aria-live="polite">
		{#if selectedStrategy !== 'auto'}
			Strategy selected: {STRATEGY_OPTIONS.find(o => o.value === selectedStrategy)?.label}
			{#if selectedSecondary.length > 0}
				with {selectedSecondary.length} secondary {selectedSecondary.length === 1 ? 'framework' : 'frameworks'}
			{/if}
		{/if}
	</div>

	<!-- Bottom bar -->
	<Separator />
	<div class="flex flex-col gap-2 px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between">
		<div class="flex items-center gap-3">
			{#if providerState.providersLoaded && providerState.providers.length > 1}
				<ProviderSelector />
			{/if}
			<Tooltip text="Prompt character count">
				<span class="font-mono text-[11px] tabular-nums text-text-dim/50" data-testid="char-count">
					{charCount} <span class="text-text-dim/30">chars</span>
				</span>
			</Tooltip>
		</div>

		<div class="flex items-center gap-3 self-end sm:self-auto">
			<kbd class="hidden rounded border border-text-dim/20 bg-bg-secondary/80 px-1.5 py-0.5 font-mono text-[10px] text-text-dim/60 sm:inline-block">
				{(typeof navigator !== 'undefined' && /Mac|iPhone/.test(navigator.userAgent) ? '\u2318' : 'Ctrl') + '+\u23CE'}
			</kbd>
			{#if disabled && oncancel}
				<button
					data-testid="cancel-button"
					onclick={oncancel}
					aria-label="Cancel optimization"
					class="inline-flex items-center gap-2 rounded-[10px] border border-neon-red/30 bg-neon-red/10 px-5 py-2 font-display text-sm font-bold tracking-wide text-neon-red transition-colors hover:bg-neon-red/20"
				>
					<Icon name="x" size={16} />
					Cancel
				</button>
			{:else}
				<Tooltip text="Optimize this prompt">
				<button
					data-testid="forge-button"
					onclick={handleSubmit}
					disabled={disabled || !prompt.trim()}
					aria-label={disabled ? 'Optimization in progress' : 'Forge It! — Optimize your prompt'}
					class="btn-primary px-5 py-2 font-display text-sm tracking-wide"
				>
					{#if disabled}
						<span class="flex items-center gap-2">
							<Icon name="spinner" size={16} class="animate-spin" />
							Forging...
						</span>
					{:else}
						Forge It!
					{/if}
				</button>
				</Tooltip>
			{/if}
		</div>
	</div>
</div>

<style>
	.prompt-container:has(textarea:focus) {
		box-shadow: 0 0 15px color-mix(in srgb, var(--color-neon-cyan) 7%, transparent),
					0 0 30px color-mix(in srgb, var(--color-neon-cyan) 3%, transparent);
		border-color: color-mix(in srgb, var(--color-neon-cyan) 25%, transparent);
	}

	.prompt-container:has(textarea:focus) .glow-line {
		opacity: 1;
		background: linear-gradient(90deg,
			transparent,
			color-mix(in srgb, var(--color-neon-cyan) 40%, transparent),
			color-mix(in srgb, var(--color-neon-purple) 30%, transparent),
			transparent);
	}
</style>
