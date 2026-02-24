<script lang="ts">
	import "../app.css";
	import { Tooltip } from "bits-ui";
	import { page } from "$app/stores";
	import Header from "$lib/components/Header.svelte";
	import Footer from "$lib/components/Footer.svelte";
	import HistorySidebar from "$lib/components/HistorySidebar.svelte";
	import Toast from "$lib/components/Toast.svelte";
	import ForgeIDEWorkspace from "$lib/components/ForgeIDEWorkspace.svelte";
	import { historyState } from "$lib/stores/history.svelte";
	import { optimizationState } from "$lib/stores/optimization.svelte";
	import { providerState } from "$lib/stores/provider.svelte";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { forgeMachine } from "$lib/stores/forgeMachine.svelte";
	import { promptAnalysis } from "$lib/stores/promptAnalysis.svelte";
	import { statsState } from "$lib/stores/stats.svelte";
	import { sidebarState } from "$lib/stores/sidebar.svelte";
	import { onMount } from "svelte";

	let { children } = $props();

	let isHomePage = $derived($page.url.pathname === '/');

	onMount(() => {
		if (!historyState.hasLoaded) {
			historyState.loadHistory();
		}
		providerState.startPolling();

		// Global keyboard shortcuts
		function handleGlobalKeydown(e: KeyboardEvent) {
			const tag = (e.target as HTMLElement)?.tagName;
			if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT")
				return;

			// Escape — exit IDE (compose mode only, prevents accidental close during pipeline)
			if (e.key === "Escape" && forgeSession.isActive && forgeMachine.mode === "compose") {
				e.preventDefault();
				forgeSession.isActive = false;
				return;
			}

			// `/` — open IDE / focus textarea
			if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
				e.preventDefault();
				forgeSession.focusTextarea();
			}
		}
		document.addEventListener("keydown", handleGlobalKeydown);
		return () => {
			providerState.stopPolling();
			document.removeEventListener("keydown", handleGlobalKeydown);
		};
	});

	// Auto-transition forge machine on optimization completion + feed analysis store
	$effect(() => {
		if (
			optimizationState.result &&
			!optimizationState.isRunning &&
			forgeMachine.mode === "forging"
		) {
			forgeMachine.complete();
			// Feed authoritative pipeline classification back to recommendation engine
			if (optimizationState.result.task_type) {
				promptAnalysis.updateFromPipeline(
					optimizationState.result.task_type,
					optimizationState.result.complexity,
				);
			}
		}
	});

	// Load stats globally when history is available; reset when emptied
	$effect(() => {
		if (!historyState.hasLoaded) return;
		if (historyState.total > 0) {
			statsState.load(historyState.total);
		} else {
			statsState.reset();
		}
	});
</script>

<Tooltip.Provider delayDuration={400} skipDelayDuration={300}>
	<a href="#main-content" class="skip-link">Skip to main content</a>

	<div class="flex h-screen w-screen overflow-hidden bg-bg-primary">
		<HistorySidebar bind:open={sidebarState.isOpen} />

		<div class="flex flex-1 flex-col overflow-hidden min-w-0">
			<Header bind:sidebarOpen={sidebarState.isOpen} />

			{#if isHomePage && (forgeSession.isActive || forgeMachine.mode !== "compose")}
				<ForgeIDEWorkspace />
			{:else}
				<main
					id="main-content"
					class="relative flex-1 overflow-y-auto"
					tabindex="-1"
				>
					<div class="mx-auto max-w-5xl px-4 pt-1.5 pb-4">
						{@render children()}
					</div>
				</main>
				<Footer />
			{/if}
		</div>
	</div>

	<Toast />
</Tooltip.Provider>
