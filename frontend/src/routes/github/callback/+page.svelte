<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { workspaceManager } from '$lib/stores/workspaceManager.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';

	let status = $state<'loading' | 'connected' | 'error'>('loading');
	let errorMessage = $state('');

	function friendlyError(code: string | null): string {
		switch (code) {
			case 'invalid_state': return 'OAuth session expired or was tampered with. Please try connecting again.';
			case 'not_configured': return 'GitHub OAuth is not configured. Set up credentials in the Workspace Hub first.';
			case 'token_exchange_failed': return 'Failed to exchange authorization code. The code may have expired — please try again.';
			case 'user_fetch_failed': return 'Connected to GitHub but failed to fetch your profile. Please try again.';
			case 'access_denied': return 'Access was denied. You may have cancelled the authorization on GitHub.';
			default: return code || 'An unknown error occurred during GitHub authentication.';
		}
	}

	onMount(async () => {
		const params = $page.url.searchParams;
		const callbackStatus = params.get('status');
		const error = params.get('error');

		if (callbackStatus === 'connected') {
			status = 'connected';
			// Refresh workspace state
			await workspaceManager.initialize();
			systemBus.emit('workspace:connected', 'github-callback');

			// Open Workspace Hub and redirect after brief delay
			windowManager.openWorkspaceHub();
			setTimeout(() => goto('/'), 1500);
		} else {
			status = 'error';
			errorMessage = friendlyError(error);
			setTimeout(() => goto('/'), 3000);
		}
	});
</script>

<div class="fixed inset-0 bg-bg-primary flex items-center justify-center font-mono">
	<div class="text-center space-y-3 max-w-xs">
		{#if status === 'loading'}
			<p class="text-xs text-text-secondary">Connecting to GitHub...</p>
		{:else if status === 'connected'}
			<div class="w-3 h-3 rounded-full bg-neon-green mx-auto"></div>
			<p class="text-sm text-neon-green">GitHub Connected</p>
			<p class="text-xs text-text-dim">Redirecting to Workspace Hub...</p>
		{:else}
			<div class="w-3 h-3 rounded-full bg-neon-red mx-auto"></div>
			<p class="text-sm text-neon-red">Connection Failed</p>
			<p class="text-xs text-text-dim">{errorMessage}</p>
			<p class="text-[10px] text-text-dim mt-2">Redirecting...</p>
		{/if}
	</div>
</div>
