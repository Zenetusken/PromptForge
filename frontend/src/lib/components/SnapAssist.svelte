<script lang="ts">
	import { fade } from 'svelte/transition';
	import Icon from './Icon.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { getLayout, resolveSlotGeometry, getViewportSize, type LayoutSlot, type SnapSlotId } from '$lib/stores/snapLayout';

	let active = $derived(windowManager.snapAssistActive);
	let layoutId = $derived(windowManager.snapAssistLayoutId);
	let filledSlots = $derived(windowManager.snapAssistFilledSlots);

	let layout = $derived(layoutId ? getLayout(layoutId) : undefined);

	let emptySlots = $derived.by((): LayoutSlot[] => {
		if (!layout) return [];
		const filled = Object.keys(filledSlots) as SnapSlotId[];
		return layout.slots.filter((s) => !filled.includes(s.id));
	});

	/** Candidate windows for snap assist: non-minimized, not in a group, not already placed. */
	let candidates = $derived.by(() => {
		const placedIds = new Set(Object.values(filledSlots));
		return windowManager.windows.filter(
			(w) => w.state !== 'minimized' && !w.snapGroupId && !placedIds.has(w.id)
		);
	});

	// Reactive viewport dimensions via svelte:window bindings
	let innerWidth = $state(typeof window !== 'undefined' ? window.innerWidth : 1280);
	let innerHeight = $state(typeof window !== 'undefined' ? window.innerHeight : 720);
	let vw = $derived(innerWidth);
	let vh = $derived(innerHeight - 40); // exclude taskbar

	function handleSlotClick(slotId: SnapSlotId, windowId: string) {
		windowManager.completeSnapAssist(slotId, windowId);
	}

	function handleDismiss(e: MouseEvent) {
		// Only dismiss if clicking the scrim itself, not a card
		if (e.target === e.currentTarget) {
			windowManager.dismissSnapAssist();
		}
	}

	// Auto-dismiss when no candidates are available
	$effect(() => {
		if (active && candidates.length === 0) {
			windowManager.dismissSnapAssist();
		}
	});
</script>

<!-- Reactive viewport tracking -->
<svelte:window bind:innerWidth bind:innerHeight />

{#if active && emptySlots.length > 0 && candidates.length > 0}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="snap-assist-scrim" onclick={handleDismiss} transition:fade={{ duration: 150 }}>
		{#each emptySlots as slot (slot.id)}
			{@const geo = resolveSlotGeometry(slot, vw, vh)}
			<div
				class="snap-assist-zone"
				style="
					left: {geo.x}px;
					top: {geo.y}px;
					width: {geo.width}px;
					height: {geo.height}px;
				"
			>
				{#each candidates.slice(0, 4) as candidate (candidate.id)}
					<button
						class="snap-assist-card"
						onclick={() => handleSlotClick(slot.id, candidate.id)}
					>
						<Icon name={candidate.icon as any} size={12} class="text-text-dim shrink-0" />
						<span class="text-[11px] text-text-secondary truncate">{candidate.title}</span>
					</button>
				{/each}
				{#if candidates.length > 4}
					<span class="text-[9px] text-text-dim px-2">+{candidates.length - 4} more</span>
				{/if}
			</div>
		{/each}
	</div>
{/if}
