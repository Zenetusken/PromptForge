<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		onselect,
		onopen,
		oncontextmenu,
		active = false,
		children,
		testId,
	}: {
		onselect?: () => void;
		onopen?: () => void;
		oncontextmenu?: (e: MouseEvent) => void;
		active?: boolean;
		children: Snippet;
		testId?: string;
	} = $props();

	function handleClick(e: MouseEvent) {
		e.stopPropagation();
		onselect?.();
	}

	function handleDblClick() {
		onopen?.();
	}

	function handleContextMenu(e: MouseEvent) {
		if (oncontextmenu) {
			e.preventDefault();
			e.stopPropagation();
			onselect?.();
			oncontextmenu(e);
		}
	}
</script>

<button
	class="cv-auto flex w-full items-center gap-3 px-3 py-2 text-left transition-colors rounded-sm {active ? 'bg-neon-cyan/10' : 'hover:bg-bg-hover'}"
	onclick={handleClick}
	ondblclick={handleDblClick}
	oncontextmenu={handleContextMenu}
	data-testid={testId}
>
	{@render children()}
</button>
