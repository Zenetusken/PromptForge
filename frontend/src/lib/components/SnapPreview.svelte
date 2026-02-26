<script lang="ts">
	import { fade } from 'svelte/transition';
	import { windowManager } from '$lib/stores/windowManager.svelte';

	let zone = $derived(windowManager.activeSnapZone);
</script>

{#if zone}
	<div
		class="snap-preview"
		style="
			left: {zone.geometry.x}px;
			top: {zone.geometry.y}px;
			width: {zone.geometry.width}px;
			height: {zone.geometry.height}px;
			z-index: 9;
		"
		transition:fade={{ duration: 120 }}
	></div>
{/if}
