<script lang="ts">
	import Icon from './Icon.svelte';
	import { Tooltip } from './ui';

	let { sidebarOpen = $bindable(true) }: { sidebarOpen: boolean } = $props();
</script>

<header
	class="glass sticky top-0 z-30 flex h-14 shrink-0 items-center px-5 relative"
	data-testid="header"
>
	<div class="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border-glow to-transparent"></div>
	<div class="flex items-center gap-3">
		{#if !sidebarOpen}
			<Tooltip text="Open sidebar" side="right">
				<button
					onclick={() => (sidebarOpen = true)}
					class="flex h-8 w-8 items-center justify-center rounded-lg text-text-dim transition-[background-color,color,box-shadow] duration-200 hover:bg-bg-hover hover:text-neon-cyan hover:shadow-[0_0_8px_rgba(0,229,255,0.08)]"
					aria-label="Open sidebar"
					data-testid="sidebar-toggle"
				>
					<Icon name="menu" size={16} />
				</button>
			</Tooltip>
		{/if}

		<Tooltip text="Go to home" side="bottom">
			<a href="/" class="flex items-center gap-2.5 no-underline">
				<!-- Forge icon -->
				<div class="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20 shadow-[0_0_12px_rgba(0,229,255,0.08)]">
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
		</Tooltip>
	</div>

</header>
