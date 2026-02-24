<script lang="ts">
	interface Segment {
		label: string;
		href?: string;
	}

	let { segments }: { segments: Segment[] } = $props();
</script>

<nav
	aria-label="Breadcrumb"
	class="group/crumbs inline-flex items-center gap-2 rounded-lg border border-border-subtle/20 bg-bg-card/30 px-3 py-1.5
		animate-fade-in"
	style="animation-fill-mode: both;"
	data-testid="breadcrumbs"
>
	{#each segments as segment, i (i)}
		{#if i > 0}
			<span class="select-none font-mono text-[10px] leading-none text-text-dim/25 transition-colors duration-200 group-hover/crumbs:text-text-dim/50" aria-hidden="true">/</span>
		{/if}

		{#if segment.href && i < segments.length - 1}
			<a
				href={segment.href}
				class="font-mono text-[11px] leading-none text-text-dim transition-all duration-200
					hover:text-neon-cyan
					active:scale-95 active:text-neon-cyan/70
					focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-neon-cyan/40 focus-visible:rounded-sm"
			>
				{segment.label}
			</a>
		{:else}
			<span
				class="max-w-[28ch] truncate font-mono text-[11px] leading-none text-text-secondary"
				aria-current={i === segments.length - 1 ? "page" : undefined}
			>
				{segment.label}
			</span>
		{/if}
	{/each}
</nav>
