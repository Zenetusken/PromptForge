<script lang="ts">
	import Icon from './Icon.svelte';

	let {
		id = '',
		label,
		icon,
		color = 'cyan',
		selected = false,
		dragging = false,
		editing = false,
		renameable = false,
		binIndicator = false,
		binEmpty = true,
		onselect,
		ondblclick,
		oncontextmenu,
		onmousedown,
		onlabelclick,
		onrename,
	}: {
		id?: string;
		label: string;
		icon: string;
		color?: string;
		selected?: boolean;
		dragging?: boolean;
		editing?: boolean;
		renameable?: boolean;
		binIndicator?: boolean;
		binEmpty?: boolean;
		onselect?: () => void;
		ondblclick?: () => void;
		oncontextmenu?: (e: MouseEvent) => void;
		onmousedown?: (e: MouseEvent) => void;
		onlabelclick?: () => void;
		onrename?: (newLabel: string) => void;
	} = $props();

	const colorMap: Record<string, { text: string; bg: string; bgHover: string }> = {
		cyan: { text: 'text-neon-cyan', bg: 'bg-neon-cyan/8', bgHover: 'hover:bg-neon-cyan/15' },
		purple: { text: 'text-neon-purple', bg: 'bg-neon-purple/8', bgHover: 'hover:bg-neon-purple/15' },
		green: { text: 'text-neon-green', bg: 'bg-neon-green/8', bgHover: 'hover:bg-neon-green/15' },
		red: { text: 'text-neon-red', bg: 'bg-neon-red/8', bgHover: 'hover:bg-neon-red/15' },
		yellow: { text: 'text-neon-yellow', bg: 'bg-neon-yellow/8', bgHover: 'hover:bg-neon-yellow/15' },
		blue: { text: 'text-neon-blue', bg: 'bg-neon-blue/8', bgHover: 'hover:bg-neon-blue/15' },
	};

	let colors = $derived(colorMap[color] ?? colorMap.cyan);

	let iconColorClass = $derived(
		binIndicator
			? (binEmpty ? 'text-text-dim' : 'text-neon-red')
			: colors.text
	);

	let renameValue = $state('');
	let committed = false;

	// Sync renameValue when entering edit mode
	$effect(() => {
		if (editing) {
			renameValue = label;
			committed = false;
		}
	});

	function handleIconClick(e: MouseEvent) {
		e.stopPropagation();
		onselect?.();
	}

	function handleContextMenu(e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		onselect?.();
		oncontextmenu?.(e);
	}

	function handleMouseDown(e: MouseEvent) {
		if (e.button === 0) {
			onmousedown?.(e);
		}
	}

	function handleLabelClick(e: MouseEvent) {
		if (!renameable) return;
		e.stopPropagation();
		onlabelclick?.();
	}

	function commitRename() {
		if (committed) return;
		committed = true;
		onrename?.(renameValue);
	}

	function handleLabelKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			commitRename();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			// Cancel: commit original label to exit edit mode
			if (committed) return;
			committed = true;
			onrename?.(label);
		}
	}

	function handleInputMount(el: HTMLInputElement) {
		el.focus();
		el.select();
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="flex flex-col items-center w-[76px] h-[84px] pt-1 gap-1"
	data-testid={id ? `desktop-icon-${id}` : undefined}
>
	<!-- ICON GRAPHIC: 40x40 interactive square -->
	<button
		type="button"
		class="icon-graphic flex h-10 w-10 items-center justify-center rounded-lg
			border border-border-subtle {colors.bg} {colors.bgHover}
			transition-all duration-150 hover:scale-105
			{selected ? 'ring-1 ring-neon-cyan/30 bg-neon-cyan/10' : ''}
			{dragging ? 'opacity-30' : ''}"
		onclick={handleIconClick}
		ondblclick={ondblclick}
		oncontextmenu={handleContextMenu}
		onmousedown={handleMouseDown}
	>
		<Icon name={icon as any} size={20} class={iconColorClass} />
	</button>

	<!-- LABEL: separate clickable/editable text -->
	{#if editing}
		<input
			class="desktop-icon-label-input"
			type="text"
			maxlength={40}
			bind:value={renameValue}
			onfocusout={commitRename}
			onkeydown={handleLabelKeydown}
			use:handleInputMount
		/>
	{:else}
		<span
			class="desktop-icon-label"
			onclick={handleLabelClick}
			oncontextmenu={handleContextMenu}
		>
			{label}
		</span>
	{/if}
</div>
