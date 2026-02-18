<script lang="ts">
	import '../app.css';
	import { goto, beforeNavigate } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import HistorySidebar from '$lib/components/HistorySidebar.svelte';
	import Toast from '$lib/components/Toast.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { navigationState } from '$lib/stores/navigation.svelte';
	import { onMount } from 'svelte';

	let { children } = $props();

	let sidebarOpen = $state(true);

	beforeNavigate(({ from, to }) => {
		if (from?.url && to?.url) {
			navigationState.recordNavigation(from.url.pathname, to.url.pathname);
		}
	});

	onMount(() => {
		if (!historyState.hasLoaded) {
			historyState.loadHistory();
		}
		providerState.startPolling();

		// Global `/` shortcut to focus prompt textarea (when not in an input)
		function handleGlobalKeydown(e: KeyboardEvent) {
			if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
				const tag = (e.target as HTMLElement)?.tagName;
				if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
				const textarea = document.querySelector<HTMLTextAreaElement>('[data-testid="prompt-textarea"]');
				if (textarea) {
					e.preventDefault();
					textarea.focus();
				}
			}
		}
		document.addEventListener('keydown', handleGlobalKeydown);
		return () => {
			providerState.stopPolling();
			document.removeEventListener('keydown', handleGlobalKeydown);
		};
	});

	$effect(() => {
		const nav = optimizationState.pendingNavigation;
		if (nav) {
			optimizationState.consumeNavigation();
			goto(nav, { replaceState: true });
		}
	});
</script>

<a href="#main-content" class="skip-link">Skip to main content</a>

<div class="flex h-screen w-screen overflow-hidden bg-bg-primary">
	<HistorySidebar bind:open={sidebarOpen} />

	<div class="flex flex-1 flex-col overflow-hidden">
		<Header bind:sidebarOpen />

		<main id="main-content" class="relative flex-1 overflow-y-auto" tabindex="-1">
			<div class="mx-auto max-w-5xl px-6 pt-4 pb-8">
				{@render children()}
			</div>
		</main>

		<Footer />
	</div>
</div>

<Toast />
