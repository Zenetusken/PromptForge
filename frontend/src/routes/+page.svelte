<script lang="ts">
	import { optimizationState } from "$lib/stores/optimization.svelte";
	import { forgeMachine } from "$lib/stores/forgeMachine.svelte";
	import { windowManager } from "$lib/stores/windowManager.svelte";

	// Clear stale optimization state when navigating to home
	// Skip clearing when IDE is visible or an active forge is in progress
	if (!optimizationState.isRunning && forgeMachine.mode === 'compose' && !windowManager.ideVisible) {
		optimizationState.viewResult = null;
		optimizationState.currentRun = null;
		optimizationState.error = null;
	}
</script>

<!-- Desktop surface is rendered by +layout.svelte when on "/" route -->
<!-- This page is intentionally minimal — the DesktopSurface handles wallpaper + icons -->
