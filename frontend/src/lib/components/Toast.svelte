<script lang="ts">
	import { onMount } from 'svelte';

	let containerEl: HTMLDivElement;

	onMount(() => {
		// Register the toast container globally so showToast() can find it
		(window as any).__toastContainer = containerEl;
		return () => {
			delete (window as any).__toastContainer;
		};
	});
</script>

<div bind:this={containerEl} class="fixed bottom-6 right-6 z-50 flex flex-col gap-2" id="toast-container"></div>
