<script lang="ts">
	import Icon from './Icon.svelte';

	let { searchQuery = '' }: { searchQuery?: string } = $props();
</script>

<div class="flex flex-col items-center justify-center py-12 text-center" data-testid="empty-state">
	<div class="mb-3 rounded-xl bg-bg-hover/50 p-3 text-text-dim">
		{#if searchQuery}
			<Icon name="search" size={24} />
		{:else}
			<Icon name="layers" size={24} />
		{/if}
	</div>
	{#if searchQuery}
		<p class="text-sm font-medium text-text-secondary">No matches</p>
		<p class="mt-1 text-xs text-text-dim">Try a different search term</p>
	{:else}
		<p class="text-sm font-medium text-text-secondary">No optimizations yet</p>
		<p class="mt-1 px-6 text-xs leading-relaxed text-text-dim">Paste a prompt and click Forge It!</p>
	{/if}
</div>
