<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { DragPayload } from '$lib/utils/dragPayload';
	import { DRAG_MIME, encodeDragPayload, decodeDragPayload } from '$lib/utils/dragPayload';

	let {
		onselect,
		onopen,
		oncontextmenu,
		ondrop: onDropHandler,
		active = false,
		dropTarget = false,
		children,
		testId,
		dragPayload,
	}: {
		onselect?: (e: MouseEvent) => void;
		onopen?: () => void;
		oncontextmenu?: (e: MouseEvent) => void;
		ondrop?: (payload: DragPayload) => void;
		active?: boolean;
		dropTarget?: boolean;
		children: Snippet;
		testId?: string;
		dragPayload?: DragPayload;
	} = $props();

	let dragOver = $state(false);

	function handleClick(e: MouseEvent) {
		e.stopPropagation();
		onselect?.(e);
	}

	function handleDblClick() {
		onopen?.();
	}

	function handleContextMenu(e: MouseEvent) {
		if (oncontextmenu) {
			e.preventDefault();
			e.stopPropagation();
			// Don't call onselect here — parent handles selection preservation for multi-select
			oncontextmenu(e);
		}
	}

	function handleDragStart(e: DragEvent) {
		if (!dragPayload || !e.dataTransfer) return;
		e.dataTransfer.setData(DRAG_MIME, encodeDragPayload(dragPayload));
		e.dataTransfer.effectAllowed = 'copyMove';
	}

	function handleRowDragOver(e: DragEvent) {
		if (!dropTarget || !onDropHandler || !e.dataTransfer?.types.includes(DRAG_MIME)) return;
		e.preventDefault();
		e.dataTransfer.dropEffect = 'move';
		dragOver = true;
	}

	function handleRowDragLeave() {
		dragOver = false;
	}

	function handleRowDrop(e: DragEvent) {
		dragOver = false;
		if (!dropTarget || !onDropHandler) return;
		e.preventDefault();
		e.stopPropagation();
		const raw = e.dataTransfer?.getData(DRAG_MIME);
		if (!raw) return;
		const payload = decodeDragPayload(raw);
		if (!payload) return;
		// Prevent dropping on self
		if (dragPayload && payload.descriptor.id === dragPayload.descriptor.id) return;
		onDropHandler(payload);
	}
</script>

<button
	class="cv-auto flex w-full items-center gap-3 px-3 py-2 text-left transition-colors rounded-sm {active ? 'bg-neon-cyan/10' : dragOver ? 'bg-neon-cyan/10 ring-1 ring-neon-cyan/30' : 'hover:bg-bg-hover'}"
	onclick={handleClick}
	ondblclick={handleDblClick}
	oncontextmenu={handleContextMenu}
	draggable={!!dragPayload}
	ondragstart={handleDragStart}
	ondragover={handleRowDragOver}
	ondragleave={handleRowDragLeave}
	ondrop={handleRowDrop}
	data-testid={testId}
>
	{@render children()}
</button>
