<script lang="ts">
	import '../app.css';
	import Header from '$lib/components/Header.svelte';
	import HistorySidebar from '$lib/components/HistorySidebar.svelte';
	import Toast from '$lib/components/Toast.svelte';

	let { children } = $props();

	let sidebarOpen = $state(true);
</script>

<div class="flex h-screen w-screen overflow-hidden">
	<HistorySidebar bind:open={sidebarOpen} />

	<div class="flex flex-1 flex-col overflow-hidden">
		<Header bind:sidebarOpen />

		<main class="flex-1 overflow-y-auto p-6">
			{@render children()}
		</main>
	</div>
</div>

<Toast />
