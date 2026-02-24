<script lang="ts">
	import Icon from "./Icon.svelte";
	import HeaderStats from "./HeaderStats.svelte";
	import { Tooltip } from "./ui";

	let { sidebarOpen = $bindable(true) }: { sidebarOpen: boolean } = $props();
</script>

<header
	class="glass sticky top-0 z-30 flex shrink-0 items-center px-3 py-px relative border-b border-neon-cyan/10"
	data-testid="header"
>
	{#if !sidebarOpen}
		<Tooltip text="Open sidebar" side="right">
			<button
				onclick={() => (sidebarOpen = true)}
				class="absolute left-2 top-1/2 -translate-y-1/2 z-10 flex h-6 w-6 items-center justify-center rounded-md text-text-dim transition-[background-color,color] duration-200 hover:bg-bg-hover hover:text-neon-cyan"
				aria-label="Open sidebar"
				data-testid="sidebar-toggle"
			>
				<Icon name="menu" size={14} />
			</button>
		</Tooltip>
	{/if}

	<HeaderStats {sidebarOpen} />
</header>
