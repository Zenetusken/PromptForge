<script module lang="ts">
	let closeActive: (() => void) | null = null;
</script>

<script lang="ts">
	import Icon from './Icon.svelte';

	type Option = { value: string; label: string; group?: string };
	type RenderItem =
		| { kind: 'option'; option: Option; optionIndex: number }
		| { kind: 'header'; group: string; count: number; expanded: boolean };

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
	let expandedGroups: Set<string> = $state(new Set());

	let selectedLabel = $derived(
		options.find((o) => o.value === value)?.label ?? ''
	);

	// Ordered unique group names
	let groups = $derived.by(() => {
		const seen = new Set<string>();
		const result: string[] = [];
		for (const opt of options) {
			if (opt.group && !seen.has(opt.group)) {
				seen.add(opt.group);
				result.push(opt.group);
			}
		}
		return result;
	});

	let hasGroups = $derived(groups.length > 0);

	// Items per group
	let groupCounts = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const opt of options) {
			if (opt.group) counts[opt.group] = (counts[opt.group] || 0) + 1;
		}
		return counts;
	});

	// Build the mixed render list: ungrouped options + (header + children) per group
	let renderItems: RenderItem[] = $derived.by(() => {
		if (!hasGroups) {
			return options.map((opt, i) => ({ kind: 'option' as const, option: opt, optionIndex: i }));
		}
		const items: RenderItem[] = [];
		for (let i = 0; i < options.length; i++) {
			if (!options[i].group) {
				items.push({ kind: 'option', option: options[i], optionIndex: i });
			}
		}
		for (const group of groups) {
			const expanded = expandedGroups.has(group);
			items.push({ kind: 'header', group, count: groupCounts[group], expanded });
			if (expanded) {
				for (let i = 0; i < options.length; i++) {
					if (options[i].group === group) {
						items.push({ kind: 'option', option: options[i], optionIndex: i });
					}
				}
			}
		}
		return items;
	});

	const closeThis = () => {
		open = false;
	};

	function toggle() {
		if (!open) {
			if (closeActive && closeActive !== closeThis) closeActive();
			open = true;
			closeActive = closeThis;

			// Auto-expand the group containing the current selection
			if (hasGroups) {
				const selected = options.find((o) => o.value === value);
				if (selected?.group && !expandedGroups.has(selected.group)) {
					expandedGroups = new Set([...expandedGroups, selected.group]);
				}
			}

			// Focus the selected item in the render list
			focusedIndex = renderItems.findIndex(
				(item) => item.kind === 'option' && item.option.value === value
			);
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

	function toggleGroup(group: string) {
		const next = new Set(expandedGroups);
		if (next.has(group)) {
			next.delete(group);
		} else {
			next.add(group);
		}
		expandedGroups = next;
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
				focusedIndex = Math.min(focusedIndex + 1, renderItems.length - 1);
				break;
			case 'ArrowUp':
				e.preventDefault();
				focusedIndex = Math.max(focusedIndex - 1, 0);
				break;
			case 'Enter':
			case ' ':
				e.preventDefault();
				if (focusedIndex >= 0 && focusedIndex < renderItems.length) {
					const item = renderItems[focusedIndex];
					if (item.kind === 'header') {
						toggleGroup(item.group);
					} else {
						select(item.option.value);
					}
				}
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
			class="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-y-auto rounded-lg border border-border-subtle bg-bg-card shadow-xl shadow-black/40"
			role="listbox"
			aria-label={label}
		>
			{#each renderItems as item, i}
				{#if item.kind === 'header'}
					<button
						class="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wider transition-colors
							{focusedIndex === i ? 'bg-bg-hover text-text-secondary' : 'text-text-dim/60 hover:text-text-dim'}"
						onclick={() => toggleGroup(item.group)}
						onmouseenter={() => { focusedIndex = i; }}
						role="option"
						aria-selected={false}
					>
						<Icon name={item.expanded ? 'chevron-down' : 'chevron-right'} size={10} class="shrink-0" />
						{item.group}
						<span class="font-normal text-text-dim/40">({item.count})</span>
					</button>
				{:else}
					<button
						class="w-full py-1.5 text-left text-xs transition-colors
							{item.option.group ? 'pl-6 pr-2.5' : 'px-2.5'}
							{item.option.value === value ? 'text-neon-cyan' : 'text-text-secondary'}
							{focusedIndex === i ? 'bg-bg-hover' : item.option.value === value ? 'bg-neon-cyan/8' : ''}"
						onclick={() => select(item.option.value)}
						onmouseenter={() => { focusedIndex = i; }}
						role="option"
						aria-selected={item.option.value === value}
					>
						{item.option.label}
					</button>
				{/if}
			{/each}
		</div>
	{/if}
</div>
