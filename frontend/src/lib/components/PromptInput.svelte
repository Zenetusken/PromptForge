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

<div class="prompt-input-container rounded-xl border border-text-dim/20 bg-bg-card p-4 transition-all duration-300 focus-within:border-neon-cyan/60" style="transition: border-color 0.3s, box-shadow 0.3s;">
	<textarea
		data-testid="prompt-textarea"
		bind:this={textareaEl}
		bind:value={prompt}
		onkeydown={handleKeydown}
		{disabled}
		placeholder="Paste your prompt here... PromptForge will handle the rest."
		aria-label="Enter your prompt for optimization"
		rows="6"
		class="w-full resize-y bg-transparent font-mono text-sm leading-relaxed text-text-primary outline-none placeholder:text-text-dim disabled:opacity-50"
	></textarea>

	<div class="mt-3 flex items-center justify-between border-t border-text-dim/10 pt-3">
		<div class="flex items-center gap-4">
			<span class="font-mono text-xs text-text-dim" data-testid="char-count">
				{charCount} chars
			</span>
			<span class="text-xs text-text-dim">
				Ctrl+Enter to submit
			</span>
		</div>

		<button
			data-testid="forge-button"
			onclick={handleSubmit}
			disabled={disabled || !prompt.trim()}
			aria-label={disabled ? 'Optimization in progress' : 'Forge It! — Optimize your prompt'}
			class="rounded-lg px-6 py-2 font-semibold text-bg-primary transition-all duration-200 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
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

<style>
	.prompt-input-container:focus-within {
		animation: neon-pulse-border 2s ease-in-out infinite;
		box-shadow: 0 0 10px rgba(0, 240, 255, 0.2), 0 0 20px rgba(0, 240, 255, 0.1);
	}

	@keyframes neon-pulse-border {
		0%, 100% {
			box-shadow: 0 0 5px rgba(0, 240, 255, 0.2), 0 0 10px rgba(0, 240, 255, 0.1);
			border-color: rgba(0, 240, 255, 0.6);
		}
		50% {
			box-shadow: 0 0 15px rgba(0, 240, 255, 0.4), 0 0 25px rgba(0, 240, 255, 0.15);
			border-color: rgba(0, 240, 255, 0.8);
		}
	}
</style>
