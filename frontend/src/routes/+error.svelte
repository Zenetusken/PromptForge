<script lang="ts">
	import { page } from '$app/stores';
</script>

<div class="flex min-h-[60vh] flex-col items-center justify-center text-center">
	<div class="text-gradient-forge font-display text-8xl font-extrabold tracking-tight">
		{$page.status}
	</div>

	<h1 class="mt-4 font-display text-2xl font-bold text-text-primary">
		{#if $page.status === 404}
			Page Not Found
		{:else}
			Something went wrong
		{/if}
	</h1>

	<p class="mt-2 mb-8 max-w-md text-sm leading-relaxed text-text-secondary">
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
		class="btn-primary px-6 py-3 font-display text-sm tracking-wide no-underline"
		data-testid="back-home-link"
	>
		Back to PromptForge
	</a>
</div>
