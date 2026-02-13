<script lang="ts">
	let {
		onsubmit,
		disabled = false
	}: {
		onsubmit: (prompt: string) => void;
		disabled?: boolean;
	} = $props();

	let prompt = $state('');
	let charCount = $derived(prompt.length);
	let textareaEl: HTMLTextAreaElement | undefined = $state();

	function handleSubmit() {
		if (prompt.trim() && !disabled) {
			onsubmit(prompt.trim());
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
</script>

<div class="rounded-xl border border-text-dim/20 bg-bg-card p-4 transition-colors focus-within:border-neon-cyan/40">
	<textarea
		bind:this={textareaEl}
		bind:value={prompt}
		onkeydown={handleKeydown}
		{disabled}
		placeholder="Paste your prompt here... PromptForge will handle the rest."
		rows="6"
		class="w-full resize-none bg-transparent font-mono text-sm leading-relaxed text-text-primary outline-none placeholder:text-text-dim disabled:opacity-50"
	></textarea>

	<div class="mt-3 flex items-center justify-between border-t border-text-dim/10 pt-3">
		<div class="flex items-center gap-4">
			<span class="font-mono text-xs text-text-dim">
				{charCount} chars
			</span>
			<span class="text-xs text-text-dim">
				Ctrl+Enter to submit
			</span>
		</div>

		<button
			onclick={handleSubmit}
			disabled={disabled || !prompt.trim()}
			class="rounded-lg px-6 py-2 font-semibold text-bg-primary transition-all disabled:cursor-not-allowed disabled:opacity-40"
			style="background: linear-gradient(135deg, var(--color-neon-cyan), var(--color-neon-purple)); box-shadow: 0 0 20px rgba(0, 240, 255, 0.2);"
		>
			{#if disabled}
				<span class="flex items-center gap-2">
					<svg
						class="h-4 w-4 animate-spin"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
					>
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
					</svg>
					Forging...
				</span>
			{:else}
				Forge It!
			{/if}
		</button>
	</div>
</div>
