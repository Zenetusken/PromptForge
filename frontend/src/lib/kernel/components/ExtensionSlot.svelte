<script lang="ts">
	import { appRegistry } from '$lib/kernel/services/appRegistry.svelte';

	interface Props {
		slotId: string;
		context?: Record<string, unknown>;
	}

	let { slotId, context = {} }: Props = $props();

	let extensions = $derived(appRegistry.getExtensions(slotId));
</script>

{#each extensions as ext (ext.appId + ':' + ext.component)}
	{#await ext.loadComponent()}
		<!-- Loading extension -->
	{:then mod}
		<mod.default {...context} />
	{:catch err}
		<span class="text-[9px] text-neon-red" title={String(err)}>Extension error</span>
	{/await}
{/each}
