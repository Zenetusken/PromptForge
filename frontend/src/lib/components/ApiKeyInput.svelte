<script lang="ts">
	import type { ValidationResult } from '$lib/stores/provider.svelte';
	import Icon from './Icon.svelte';
	import { Tooltip } from './ui';

	let {
		maskedKey = '',
		validating = false,
		validationResult = undefined,
		onKeySet,
		onKeyClear
	}: {
		maskedKey?: string;
		validating?: boolean;
		validationResult?: ValidationResult;
		onKeySet: (key: string) => void;
		onKeyClear: () => void;
	} = $props();

	let editing = $state(false);
	let inputValue = $state('');
	let showPassword = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();

	function startEditing() {
		editing = true;
		inputValue = '';
		showPassword = false;
		// Focus after Svelte renders the input
		requestAnimationFrame(() => inputEl?.focus());
	}

	function handleSubmit() {
		const trimmed = inputValue.trim();
		if (trimmed) {
			onKeySet(trimmed);
			editing = false;
			inputValue = '';
			showPassword = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleSubmit();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			editing = false;
			inputValue = '';
		}
	}

	function handleClear(e: MouseEvent) {
		e.stopPropagation();
		onKeyClear();
	}
</script>

{#if maskedKey && !editing}
	<!-- Stored key display -->
	<div class="flex items-center gap-1.5 rounded-md bg-neon-green/4 ring-1 ring-neon-green/12 px-1.5 py-0.5">
		{#if validating}
			<Icon name="spinner" size={10} class="text-neon-cyan animate-spin" />
		{:else if validationResult?.valid}
			<Icon name="check" size={10} class="text-neon-green" />
		{:else if validationResult && !validationResult.valid}
			<Tooltip text={validationResult.error ?? 'Validation failed'}><span><Icon name="alert-circle" size={10} class="text-neon-red" /></span></Tooltip>
		{:else}
			<Icon name="key" size={10} class="text-neon-green" />
		{/if}
		<span class="font-mono text-[11px] text-neon-green">{maskedKey}</span>
		<Tooltip text="Remove saved API key">
		<button
			type="button"
			onclick={handleClear}
			class="ml-0.5 rounded p-0.5 text-text-dim hover:bg-neon-red/10 hover:text-neon-red transition-colors"
			aria-label="Clear API key"
		>
			<Icon name="x" size={10} />
		</button>
		</Tooltip>
	</div>
	{#if validationResult && !validationResult.valid && validationResult.error}
		<div class="text-[11px] text-neon-red mt-0.5">{validationResult.error}</div>
	{/if}
{:else if editing}
	<!-- Key input form -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="flex items-center gap-1 mt-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
		<div class="relative flex-1">
			<input
				bind:this={inputEl}
				type={showPassword ? 'text' : 'password'}
				bind:value={inputValue}
				onkeydown={handleKeydown}
				placeholder="Paste API key..."
				class="w-full rounded border border-border-subtle bg-bg-input/80 px-2 py-1 pr-7 font-mono text-[11px] text-text-primary placeholder:text-text-dim/50 focus:border-neon-cyan/30 focus:shadow-[0_0_8px_rgba(0,229,255,0.15),0_0_16px_rgba(0,229,255,0.05)] focus:outline-none"
			/>
			<button
				type="button"
				onclick={() => (showPassword = !showPassword)}
				class="absolute right-1 top-1/2 -translate-y-1/2 text-text-dim hover:text-text-secondary transition-colors"
				aria-label={showPassword ? 'Hide key' : 'Show key'}
			>
				<Icon name={showPassword ? 'eye-off' : 'eye'} size={10} />
			</button>
		</div>
		<button
			type="button"
			onclick={handleSubmit}
			disabled={!inputValue.trim()}
			class="rounded bg-neon-cyan/15 px-2 py-1 text-[11px] font-medium text-neon-cyan hover:bg-neon-cyan/25 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
		>
			Set
		</button>
		<button
			type="button"
			onclick={() => { editing = false; inputValue = ''; }}
			class="rounded p-1 text-text-dim hover:text-text-secondary transition-colors"
			aria-label="Cancel"
		>
			<Icon name="x" size={10} />
		</button>
	</div>
{:else}
	<!-- Add key affordance -->
	<button
		type="button"
		onclick={(e) => { e.stopPropagation(); startEditing(); }}
		class="flex items-center gap-1 rounded-md bg-neon-cyan/5 ring-1 ring-neon-cyan/15 px-2 py-0.5 text-[11px] text-neon-cyan/70 hover:text-neon-cyan transition-colors"
	>
		<Icon name="key" size={10} />
		<span>Add API key</span>
	</button>
{/if}
