<script lang="ts">
	import Icon from './Icon.svelte';

	interface Segment {
		label: string;
		href?: string;
	}

	let { segments }: { segments: Segment[] } = $props();
</script>

<nav aria-label="Breadcrumb" class="flex items-center gap-1 text-xs text-text-dim">
	{#each segments as segment, i (i)}
		{#if i > 0}
			<Icon name="chevron-right" size={10} class="text-text-dim/40" />
		{/if}
		{#if segment.href && i < segments.length - 1}
			<a
				href={segment.href}
				class="transition-colors hover:text-neon-cyan"
			>
				{segment.label}
			</a>
		{:else}
			<span class="text-text-secondary">{segment.label}</span>
		{/if}
	{/each}
</nav>
