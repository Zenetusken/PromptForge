<script lang="ts">
	import Icon from './Icon.svelte';

	let { searchQuery = '' }: { searchQuery?: string } = $props();
</script>

<div class="flex flex-col items-center justify-center py-8 text-center" data-testid="empty-state">
	<div class="mb-2 rounded-xl bg-bg-hover/50 p-2.5 text-text-dim">
		{#if searchQuery}
			<Icon name="search" size={20} />
		{:else}
			<Icon name="layers" size={20} />
		{/if}
	</div>
	{#if searchQuery}
		<p class="text-[12px] font-medium text-text-secondary">No matches</p>
		<p class="mt-0.5 text-[11px] text-text-dim">Try a different search term</p>
	{:else}
		<p class="text-[12px] font-medium text-text-secondary">No optimizations yet</p>
		<p class="mt-0.5 px-4 text-[11px] leading-relaxed text-text-dim">Paste a prompt and click Forge It!</p>
	{/if}
</div>
