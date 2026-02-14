<script module lang="ts">
	let closeActive: (() => void) | null = null;
</script>

<script lang="ts">
	import Icon from './Icon.svelte';

	type Option = { value: string; label: string };

	let {
		value,
		options,
		label,
		onchange,
		testid = ''
	}: {
		value: string;
		options: Option[];
		label: string;
		onchange: (value: string) => void;
		testid?: string;
	} = $props();

	let open = $state(false);
	let triggerEl = $state<HTMLButtonElement | null>(null);
	let menuEl = $state<HTMLDivElement | null>(null);
	let focusedIndex = $state(-1);

	let selectedLabel = $derived(
		options.find((o) => o.value === value)?.label ?? ''
	);

	const closeThis = () => {
		open = false;
	};

	function toggle() {
		if (!open) {
			if (closeActive && closeActive !== closeThis) closeActive();
			open = true;
			closeActive = closeThis;
			focusedIndex = options.findIndex((o) => o.value === value);
		} else {
			open = false;
			if (closeActive === closeThis) closeActive = null;
		}
	}

	function select(val: string) {
		onchange(val);
		open = false;
		if (closeActive === closeThis) closeActive = null;
		triggerEl?.focus();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!open) {
			if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
				e.preventDefault();
				toggle();
			}
			return;
		}

		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				focusedIndex = Math.min(focusedIndex + 1, options.length - 1);
				break;
			case 'ArrowUp':
				e.preventDefault();
				focusedIndex = Math.max(focusedIndex - 1, 0);
				break;
			case 'Enter':
			case ' ':
				e.preventDefault();
				if (focusedIndex >= 0) select(options[focusedIndex].value);
				break;
			case 'Escape':
				e.preventDefault();
				open = false;
				if (closeActive === closeThis) closeActive = null;
				triggerEl?.focus();
				break;
		}
	}

	function handleClickOutside(e: MouseEvent) {
		if (
			open &&
			triggerEl &&
			!triggerEl.contains(e.target as Node) &&
			menuEl &&
			!menuEl.contains(e.target as Node)
		) {
			open = false;
			if (closeActive === closeThis) closeActive = null;
		}
	}
</script>

<svelte:window onclick={handleClickOutside} />

<div class="relative flex-1" data-testid={testid}>
	<button
		bind:this={triggerEl}
		class="select-field w-full text-left"
		onclick={toggle}
		onkeydown={handleKeydown}
		aria-haspopup="listbox"
		aria-expanded={open}
		aria-label={label}
	>
		{selectedLabel}
	</button>

	{#if open}
		<div
			bind:this={menuEl}
			class="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-lg border border-border-subtle bg-bg-card shadow-xl shadow-black/40"
			role="listbox"
			aria-label={label}
		>
			{#each options as option, i}
				<button
					class="w-full px-2.5 py-1.5 text-left text-xs transition-colors
						{option.value === value ? 'text-neon-cyan' : 'text-text-secondary'}
						{focusedIndex === i ? 'bg-bg-hover' : option.value === value ? 'bg-neon-cyan/8' : ''}"
					onclick={() => select(option.value)}
					onmouseenter={() => {
						focusedIndex = i;
					}}
					role="option"
					aria-selected={option.value === value}
				>
					{option.label}
				</button>
			{/each}
		</div>
	{/if}
</div>
