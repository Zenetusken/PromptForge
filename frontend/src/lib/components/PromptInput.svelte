<script lang="ts">
	import { promptState } from '$lib/stores/prompt.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import type { OptimizeMetadata } from '$lib/api/client';
	import Icon from './Icon.svelte';
	import ProviderSelector from './ProviderSelector.svelte';

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

	// Prompt ID from project detail (consumed once then cleared)
	let promptId = $state('');

	// Strategy override
	let showAdvanced = $state(false);
	let selectedStrategy = $state('auto');
	let selectedSecondary = $state<string[]>([]);

	const STRATEGY_OPTIONS: { value: string; label: string; description: string }[] = [
		{ value: 'auto', label: 'Auto', description: 'AI selects the best framework combination' },
		{ value: 'co-star', label: 'CO-STAR', description: 'Context, Objective, Style, Tone, Audience, Response' },
		{ value: 'risen', label: 'RISEN', description: 'Role, Instructions, Steps, End-goal, Narrowing' },
		{ value: 'chain-of-thought', label: 'Chain of Thought', description: 'Step-by-step reasoning scaffolding' },
		{ value: 'few-shot-scaffolding', label: 'Few-Shot', description: 'Input/output example pairs' },
		{ value: 'role-task-format', label: 'Role-Task-Format', description: 'Role + task description + output format' },
		{ value: 'structured-output', label: 'Structured Output', description: 'JSON, markdown, table format spec' },
		{ value: 'step-by-step', label: 'Step by Step', description: 'Numbered sequential instructions' },
		{ value: 'constraint-injection', label: 'Constraint Injection', description: 'Explicit do/don\'t rules and boundaries' },
		{ value: 'context-enrichment', label: 'Context Enrichment', description: 'Background info, domain context' },
		{ value: 'persona-assignment', label: 'Persona Assignment', description: 'Expert role with domain expertise' },
	];

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

	function buildMetadata(): OptimizeMetadata | undefined {
		const meta: OptimizeMetadata = {};
		if (title.trim()) meta.title = title.trim();
		if (project.trim()) meta.project = project.trim();
		if (tagsInput.trim()) {
			const tags = tagsInput.split(',').map(t => t.trim()).filter(Boolean);
			if (tags.length > 0) meta.tags = tags;
		}
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
					toastState.show('Project is archived — submitting without project link', 'info');
				}
			}
			onsubmit(prompt.trim(), buildMetadata());
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
			if (storeText && textareaEl) {
				textareaEl.focus();
			}
		}
	});
</script>

<div class="prompt-container relative rounded-xl border border-text-dim/15 bg-bg-card shadow-sm shadow-black/30 transition-[border-color,box-shadow] duration-300 focus-within:border-neon-cyan/30">
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
	<div class="border-t border-border-subtle">
		<button
			type="button"
			onclick={() => showMetadata = !showMetadata}
			class="flex w-full items-center gap-2 px-4 py-2 text-xs text-text-dim transition-colors hover:text-text-secondary"
			data-testid="metadata-toggle"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="transition-transform duration-200 {showMetadata ? 'rotate-90' : ''}"
			/>
			<span class="tracking-wide">Metadata</span>
			{#if title || project || tagsInput}
				<span class="h-1 w-1 rounded-full bg-neon-cyan"></span>
			{/if}
		</button>
		{#if showMetadata}
			<div class="animate-fade-in px-4 pb-3" data-testid="metadata-fields">
				<div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
					<input
						type="text"
						bind:value={title}
						placeholder="Title"
						aria-label="Optimization title"
						data-testid="metadata-title"
						class="input-field py-2 text-sm"
					/>
					<input
						type="text"
						bind:value={project}
						placeholder="Project"
						aria-label="Project name"
						data-testid="metadata-project"
						class="input-field py-2 text-sm"
					/>
					<input
						type="text"
						bind:value={tagsInput}
						placeholder="Tags (comma-separated)"
						aria-label="Tags"
						data-testid="metadata-tags"
						class="input-field py-2 text-sm"
					/>
				</div>
			</div>
		{/if}
	</div>

	<!-- Advanced Section (Strategy Override) -->
	<div class="border-t border-border-subtle">
		<button
			type="button"
			onclick={() => showAdvanced = !showAdvanced}
			class="flex w-full items-center gap-2 px-4 py-2 text-xs text-text-dim transition-colors hover:text-text-secondary"
			data-testid="advanced-toggle"
		>
			<Icon
				name="chevron-right"
				size={12}
				class="transition-transform duration-200 {showAdvanced ? 'rotate-90' : ''}"
			/>
			<span class="tracking-wide">Strategy</span>
			{#if selectedStrategy !== 'auto'}
				<span class="h-1 w-1 rounded-full bg-neon-purple"></span>
				<span class="rounded-full bg-neon-purple/10 px-1.5 py-0.5 font-mono text-[10px] text-neon-purple">
					{selectedStrategy}
				</span>
				{#if selectedSecondary.length > 0}
					<span class="rounded-full bg-neon-cyan/10 px-1.5 py-0.5 font-mono text-[10px] text-neon-cyan">
						+{selectedSecondary.length}
					</span>
				{/if}
			{/if}
		</button>
		{#if showAdvanced}
			<div class="animate-fade-in px-4 pb-3" data-testid="advanced-fields">
				<div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
					{#each STRATEGY_OPTIONS as option}
						<label
							class="flex cursor-pointer items-start gap-2.5 rounded-lg px-3 py-2 transition-colors
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

				{#if selectedStrategy !== 'auto'}
					<div class="mt-3 border-t border-border-subtle pt-2">
						<p class="mb-1.5 text-[11px] text-text-dim">
							Secondary frameworks <span class="text-text-dim/50">(optional, max 2)</span>
						</p>
						<div class="flex flex-wrap gap-1.5">
							{#each STRATEGY_OPTIONS.filter(o => o.value !== 'auto' && o.value !== selectedStrategy) as option}
								<button
									type="button"
									onclick={() => toggleSecondary(option.value)}
									data-testid="secondary-{option.value}"
									class="rounded-full px-2.5 py-1 font-mono text-[10px] transition-colors
										{selectedSecondary.includes(option.value)
											? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/30'
											: 'bg-bg-hover/30 text-text-dim border border-transparent hover:text-text-secondary hover:bg-bg-hover/50'}"
								>
									{selectedSecondary.includes(option.value) ? '+ ' : ''}{option.label}
								</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Bottom bar -->
	<div class="flex items-center justify-between border-t border-border-subtle px-4 py-2.5">
		<div class="flex items-center gap-3">
			{#if providerState.providersLoaded && providerState.providers.length > 1}
				<ProviderSelector />
			{/if}
			<span class="font-mono text-[11px] tabular-nums text-text-dim/40" data-testid="char-count">
				{charCount} <span class="text-text-dim/25">chars</span>
			</span>
		</div>

		<div class="flex items-center gap-3">
			<kbd class="hidden rounded border border-border-subtle bg-bg-secondary/50 px-1.5 py-0.5 font-mono text-[10px] text-text-dim/50 sm:inline-block">
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
			{/if}
		</div>
	</div>
</div>

<style>
	.prompt-container:focus-within {
		box-shadow: 0 0 15px rgba(0, 229, 255, 0.07), 0 0 30px rgba(0, 229, 255, 0.03);
		border-color: rgba(0, 229, 255, 0.25);
	}

	.prompt-container:focus-within .glow-line {
		opacity: 1;
		background: linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.4), rgba(168, 85, 247, 0.3), transparent);
	}

</style>
