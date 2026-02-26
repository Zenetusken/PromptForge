<script lang="ts">
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { SNAP_LAYOUTS, type SnapLayout, type SnapSlotId } from '$lib/stores/snapLayout';

	let { windowId }: { windowId: string } = $props();

	let hoveredLayout: SnapLayout | null = $state(null);
	let hoveredSlotId: SnapSlotId | null = $state(null);

	function handleSlotClick(layout: SnapLayout, slotId: SnapSlotId) {
		windowManager.closeLayoutPicker();
		windowManager.assignToSlot(windowId, layout.id, slotId);

		// Trigger snap assist for remaining slots if layout has > 1 slot
		if (layout.slots.length > 1) {
			const filled: Record<string, string> = { [slotId]: windowId };
			windowManager.startSnapAssist(layout.id, filled);
		}
	}

	/** Convert fractional slot to absolute positioning within the thumbnail. */
	function slotStyle(slot: { x: number; y: number; width: number; height: number }): string {
		const gap = 3; // px gap between slots
		const halfGap = gap / 2;
		return `position: absolute; left: calc(${slot.x * 100}% + ${slot.x > 0 ? halfGap : 0}px); top: calc(${slot.y * 100}% + ${slot.y > 0 ? halfGap : 0}px); width: calc(${slot.width * 100}% - ${(slot.x > 0 ? halfGap : 0) + (slot.x + slot.width < 1 ? halfGap : 0)}px); height: calc(${slot.height * 100}% - ${(slot.y > 0 ? halfGap : 0) + (slot.y + slot.height < 1 ? halfGap : 0)}px);`;
	}
</script>

<div class="flex flex-col gap-2.5">
	<span class="text-[9px] font-bold uppercase tracking-widest text-text-dim">Snap Layout</span>
	<div class="flex flex-wrap justify-center gap-2.5">
		{#each SNAP_LAYOUTS as layout (layout.id)}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="snap-layout-thumbnail relative"
				onmouseenter={() => hoveredLayout = layout}
				onmouseleave={() => { hoveredLayout = null; hoveredSlotId = null; }}
			>
				{#each layout.slots as slot (slot.id)}
					<button
						class="snap-layout-slot {hoveredLayout?.id === layout.id && hoveredSlotId === slot.id ? 'snap-layout-slot--active' : ''}"
						style={slotStyle(slot)}
						onmouseenter={() => hoveredSlotId = slot.id}
						onclick={() => handleSlotClick(layout, slot.id)}
						aria-label="{layout.label} - {slot.id}"
					></button>
				{/each}
			</div>
		{/each}
	</div>
	<span class="text-[9px] text-text-dim text-center h-3 leading-3">
		{hoveredLayout ? hoveredLayout.label : 'Hover to preview'}
	</span>
</div>
