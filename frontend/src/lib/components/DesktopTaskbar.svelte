<script lang="ts">
	import Icon from './Icon.svelte';
	import TaskbarWindowButton from './TaskbarWindowButton.svelte';
	import TaskbarSystemTray from './TaskbarSystemTray.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';

	function handleStartClick() {
		windowManager.toggleStartMenu();
	}
</script>

<div class="os-taskbar" data-testid="taskbar">
	<!-- Start button -->
	<button
		class="taskbar-window-btn gap-1.5 font-bold {windowManager.startMenuOpen ? 'taskbar-window-btn--active' : ''}"
		onclick={handleStartClick}
		aria-label="Start menu"
		data-testid="start-button"
	>
		<Icon name="bolt" size={13} class="text-neon-cyan" />
		<span class="text-[11px]">Start</span>
	</button>

	<div class="h-5 w-px bg-border-subtle mx-1"></div>

	<!-- Window buttons -->
	<div class="flex items-center gap-0.5 flex-1 min-w-0">
		{#each windowManager.windows as win (win.id)}
			<TaskbarWindowButton {win} />
		{/each}
	</div>

	<!-- System tray -->
	<TaskbarSystemTray />
</div>
