<script lang="ts">
	import '../app.css';
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import HistorySidebar from '$lib/components/HistorySidebar.svelte';
	import Toast from '$lib/components/Toast.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { onMount } from 'svelte';

	let { children } = $props();

	let sidebarOpen = $state(true);

	onMount(() => {
		if (!historyState.hasLoaded) {
			historyState.loadHistory();
		}
	});

	$effect(() => {
		const nav = optimizationState.pendingNavigation;
		if (nav) {
			optimizationState.consumeNavigation();
			goto(nav, { replaceState: true });
		}
	});
</script>

<div class="flex h-screen w-screen overflow-hidden">
	<HistorySidebar bind:open={sidebarOpen} />

	<div class="flex flex-1 flex-col overflow-hidden">
		<Header bind:sidebarOpen />

		<main class="flex-1 overflow-y-auto p-6">
			{@render children()}
		</main>

		<Footer />
	</div>
</div>

<Toast />
