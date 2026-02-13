<script lang="ts">
	import { page } from '$app/stores';
</script>

<div class="flex min-h-[60vh] flex-col items-center justify-center text-center">
	<div
		class="mb-4 font-mono text-8xl font-bold tracking-tight"
		style="background: linear-gradient(135deg, var(--color-neon-red), var(--color-neon-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;"
	>
		{$page.status}
	</div>

	<h1 class="mb-2 text-2xl font-semibold text-text-primary">
		{#if $page.status === 404}
			Page Not Found
		{:else}
			Something went wrong
		{/if}
	</h1>

	<p class="mb-8 max-w-md text-text-secondary">
		{#if $page.status === 404}
			The page you're looking for doesn't exist or has been moved.
		{:else if $page.error?.message}
			{$page.error.message}
		{:else}
			An unexpected error occurred. Please try again.
		{/if}
	</p>

	<a
		href="/"
		class="rounded-lg px-6 py-3 font-semibold text-bg-primary transition-all duration-200 hover:scale-105"
		style="background: linear-gradient(135deg, var(--color-neon-cyan), var(--color-neon-purple)); box-shadow: 0 0 20px rgba(0, 240, 255, 0.2);"
		data-testid="back-home-link"
	>
		Back to PromptForge
	</a>

	<div class="mt-12 text-text-dim">
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="48"
			height="48"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="1"
			stroke-linecap="round"
			stroke-linejoin="round"
		>
			<circle cx="12" cy="12" r="10" />
			<path d="M16 16s-1.5-2-4-2-4 2-4 2" />
			<line x1="9" y1="9" x2="9.01" y2="9" />
			<line x1="15" y1="9" x2="15.01" y2="9" />
		</svg>
	</div>
</div>
