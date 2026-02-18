<script lang="ts">
	import Icon from './Icon.svelte';

	let { sidebarOpen = $bindable(true) }: { sidebarOpen: boolean } = $props();
</script>

<header
	class="glass sticky top-0 z-30 flex h-14 shrink-0 items-center border-b border-border-subtle px-5"
	data-testid="header"
>
	<div class="flex items-center gap-3">
		{#if !sidebarOpen}
			<button
				onclick={() => (sidebarOpen = true)}
				class="flex h-8 w-8 items-center justify-center rounded-lg text-text-dim transition-[background-color,color] duration-200 hover:bg-bg-hover hover:text-neon-cyan"
				aria-label="Open sidebar"
				data-testid="sidebar-toggle"
			>
				<Icon name="menu" size={16} />
			</button>
		{/if}

		<a href="/" class="flex items-center gap-2.5 no-underline">
			<!-- Forge icon -->
			<div class="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20">
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="url(#bolt-grad)" />
					<defs>
						<linearGradient id="bolt-grad" x1="3" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
							<stop stop-color="#00e5ff" />
							<stop offset="1" stop-color="#a855f7" />
						</linearGradient>
					</defs>
				</svg>
			</div>
			<span
				class="text-gradient-forge font-display text-lg font-bold leading-normal tracking-tight"
				data-testid="logo-text"
			>
				PromptForge
			</span>
		</a>
	</div>

</header>
