<script lang="ts">
	import { promptState } from '$lib/stores/prompt.svelte';
	import type { OptimizeMetadata } from '$lib/api/client';
	import Icon from './Icon.svelte';

	let {
		onsubmit,
		disabled = false
	}: {
		onsubmit: (prompt: string, metadata?: OptimizeMetadata) => void;
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

	function buildMetadata(): OptimizeMetadata | undefined {
		const meta: OptimizeMetadata = {};
		if (title.trim()) meta.title = title.trim();
		if (project.trim()) meta.project = project.trim();
		if (tagsInput.trim()) {
			const tags = tagsInput.split(',').map(t => t.trim()).filter(Boolean);
			if (tags.length > 0) meta.tags = tags;
		}
		return Object.keys(meta).length > 0 ? meta : undefined;
	}

	function handleSubmit() {
		if (prompt.trim() && !disabled) {
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

	$effect(() => {
		const storeText = promptState.text;
		if (storeText !== lastSyncedFromStore) {
			lastSyncedFromStore = storeText;
			prompt = storeText;
			if (storeText && textareaEl) {
				textareaEl.focus();
			}
		}
	});
</script>

<div class="prompt-container relative rounded-2xl border border-text-dim/15 bg-bg-card shadow-sm shadow-black/30 transition-[border-color,box-shadow] duration-300 focus-within:border-neon-cyan/30">
	<!-- Top edge glow line -->
	<div class="glow-line absolute -top-px left-8 right-8 h-px opacity-0 transition-opacity duration-500"></div>

	<div class="p-5">
		<textarea
			data-testid="prompt-textarea"
			bind:this={textareaEl}
			bind:value={prompt}
			onkeydown={handleKeydown}
			{disabled}
			placeholder="Describe what you want your prompt to do..."
			aria-label="Enter your prompt for optimization"
			rows="5"
			class="w-full resize-y bg-transparent text-[15px] leading-relaxed text-text-primary outline-none placeholder:text-text-dim disabled:opacity-50"
		></textarea>
	</div>

	<!-- Metadata Section -->
	<div class="border-t border-border-subtle">
		<button
			type="button"
			onclick={() => showMetadata = !showMetadata}
			class="flex w-full items-center gap-2 px-5 py-2.5 text-xs text-text-dim transition-colors hover:text-text-secondary"
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
			<div class="animate-fade-in px-5 pb-4" data-testid="metadata-fields">
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

	<!-- Bottom bar -->
	<div class="flex items-center justify-between border-t border-border-subtle px-5 py-3">
		<div class="flex items-center gap-4">
			<span class="font-mono text-[11px] tabular-nums text-text-dim" data-testid="char-count">
				{charCount} <span class="text-text-dim/50">chars</span>
			</span>
			<span class="hidden text-[11px] text-text-dim/40 sm:inline">
				Ctrl+Enter to submit
			</span>
		</div>

		<button
			data-testid="forge-button"
			onclick={handleSubmit}
			disabled={disabled || !prompt.trim()}
			aria-label={disabled ? 'Optimization in progress' : 'Forge It! — Optimize your prompt'}
			class="btn-primary px-7 py-2.5 font-display text-sm tracking-wide"
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
	</div>
</div>

<style>
	.prompt-container:focus-within {
		animation: neon-pulse-border 3s ease-in-out infinite;
	}

	.prompt-container:focus-within .glow-line {
		opacity: 1;
		background: linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.4), rgba(168, 85, 247, 0.3), transparent);
	}

	@keyframes neon-pulse-border {
		0%, 100% {
			box-shadow: 0 0 10px rgba(0, 229, 255, 0.05), 0 0 20px rgba(0, 229, 255, 0.02);
			border-color: rgba(0, 229, 255, 0.2);
		}
		50% {
			box-shadow: 0 0 20px rgba(0, 229, 255, 0.1), 0 0 40px rgba(0, 229, 255, 0.04);
			border-color: rgba(0, 229, 255, 0.35);
		}
	}
</style>
