<script lang="ts">
	let { searchQuery = '' }: { searchQuery?: string } = $props();
</script>

<div class="flex flex-col items-center justify-center py-10 text-center" data-testid="empty-state">
	<div class="mb-3 text-text-dim">
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="32"
			height="32"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="1.5"
			stroke-linecap="round"
			stroke-linejoin="round"
		>
			{#if searchQuery}
				<circle cx="11" cy="11" r="8" />
				<line x1="21" y1="21" x2="16.65" y2="16.65" />
			{:else}
				<path d="M12 2L2 7l10 5 10-5-10-5z" />
				<path d="M2 17l10 5 10-5" />
				<path d="M2 12l10 5 10-5" />
			{/if}
		</svg>
	</div>
	{#if searchQuery}
		<p class="text-sm font-semibold text-text-secondary">No matching entries</p>
		<p class="mt-1 text-xs text-text-dim">Try a different search term</p>
	{:else}
		<p class="text-sm font-semibold text-text-secondary">No optimizations yet</p>
		<p class="mt-1 px-4 text-xs text-text-dim">Get started by pasting a prompt and clicking Forge It!</p>
	{/if}
</div>
