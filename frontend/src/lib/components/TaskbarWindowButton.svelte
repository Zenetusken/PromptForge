<script lang="ts">
	import { goto } from '$app/navigation';
	import Icon from './Icon.svelte';
	import { windowManager, PERSISTENT_WINDOW_IDS, type WindowEntry } from '$lib/stores/windowManager.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';

	let { win }: { win: WindowEntry } = $props();

	let isActive = $derived(windowManager.activeWindowId === win.id && win.state !== 'minimized');
	let isMinimized = $derived(win.state === 'minimized');

	// Show pulsing dot for IDE when forge is running
	let showRunningDot = $derived(
		win.id === 'ide' && forgeMachine.runningCount > 0
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
</script>

<button
	class="taskbar-window-btn {isActive ? 'taskbar-window-btn--active' : ''} {isMinimized ? 'taskbar-window-btn--minimized' : ''}"
	onclick={handleClick}
	title={win.title}
>
	<Icon name={win.icon as any} size={12} />

	{#if showRunningDot}
		<span class="h-1.5 w-1.5 rounded-full bg-neon-cyan animate-pulse flex-shrink-0"></span>
	{/if}

	<span class="truncate">{win.title}</span>
</button>
