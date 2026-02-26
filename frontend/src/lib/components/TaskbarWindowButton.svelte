<script lang="ts">
	import { goto } from '$app/navigation';
	import Icon from './Icon.svelte';
	import { windowManager, PERSISTENT_WINDOW_IDS, type WindowEntry } from '$lib/stores/windowManager.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { getGroupColor } from '$lib/stores/snapLayout';

	let { win }: { win: WindowEntry } = $props();

	let isActive = $derived(windowManager.activeWindowId === win.id && win.state !== 'minimized');
	let isMinimized = $derived(win.state === 'minimized');

	// Show pulsing dot for IDE when forge is running
	let showRunningDot = $derived(
		win.id === 'ide' && forgeMachine.runningCount > 0
	);

	// Snap group state
	let snapGroup = $derived(windowManager.getSnapGroup(win.id));
	let groupColor = $derived(snapGroup ? getGroupColor(snapGroup.id) : null);

	// Sibling highlight: this button is highlighted when another button in the same group is hovered
	let isSiblingHighlighted = $derived(
		snapGroup !== undefined
		&& windowManager.hoveredSnapGroupId === snapGroup.id
		&& windowManager.hoveredSnapGroupId !== null
	);

	function handleClick() {
		if (isActive) {
			if (PERSISTENT_WINDOW_IDS.has(win.id)) {
				windowManager.minimizeWindow(win.id);
			} else {
				// Route-driven window — close by navigating home
				goto('/');
			}
		} else {
			windowManager.focusWindow(win.id);
		}
	}

	function handleMouseEnter() {
		if (snapGroup) {
			windowManager.hoveredSnapGroupId = snapGroup.id;
		}
	}

	function handleMouseLeave() {
		if (windowManager.hoveredSnapGroupId === snapGroup?.id) {
			windowManager.hoveredSnapGroupId = null;
		}
	}
</script>

<button
	class="taskbar-window-btn {isActive ? 'taskbar-window-btn--active' : ''} {isMinimized ? 'taskbar-window-btn--minimized' : ''} {snapGroup ? 'taskbar-window-btn--grouped' : ''} {isSiblingHighlighted ? 'taskbar-window-btn--sibling-highlight' : ''}"
	onclick={handleClick}
	onmouseenter={handleMouseEnter}
	onmouseleave={handleMouseLeave}
	title={win.title}
	data-snap-group={snapGroup?.id ?? ''}
>
	<Icon name={win.icon as any} size={12} />

	{#if showRunningDot}
		<span class="h-1.5 w-1.5 rounded-full bg-neon-cyan animate-pulse flex-shrink-0"></span>
	{/if}

	<span class="truncate">{win.title}</span>

	{#if groupColor}
		<span class="taskbar-group-bar" style="background: {groupColor}"></span>
	{/if}
</button>
