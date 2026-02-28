<script lang="ts">
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import Icon from './Icon.svelte';

	let retryCountdown = $state(0);
	let retryInterval: ReturnType<typeof setInterval> | null = null;

	$effect(() => {
		const retryAfter = optimizationState.retryAfter;
		if (retryInterval) {
			clearInterval(retryInterval);
			retryInterval = null;
		}
		if (retryAfter && retryAfter > 0) {
			retryCountdown = retryAfter;
			retryInterval = setInterval(() => {
				retryCountdown--;
				if (retryCountdown <= 0 && retryInterval) {
					clearInterval(retryInterval);
					retryInterval = null;
				}
			}, 1000);
		} else {
			retryCountdown = 0;
		}
		return () => {
			if (retryInterval) {
				clearInterval(retryInterval);
				retryInterval = null;
			}
		};
	});

	// Auto-retry on rate limit when countdown expires and flag is enabled
	$effect(() => {
		if (
			forgeSession.autoRetryOnRateLimit &&
			optimizationState.errorType === 'rate_limit' &&
			retryCountdown === 0 &&
			forgeSession.hasText &&
			!optimizationState.isRunning
		) {
			// Small delay to avoid immediate retry race
			const timer = setTimeout(() => {
				if (forgeSession.hasText && !optimizationState.isRunning) {
					optimizationState.error = null;
					const metadata = forgeSession.buildMetadata();
					optimizationState.startOptimization(forgeSession.draft.text, metadata);
				}
			}, 500);
			return () => clearTimeout(timer);
		}
	});

	function handleRetry() {
		if (forgeSession.hasText) {
			optimizationState.error = null;
			const metadata = forgeSession.buildMetadata();
			optimizationState.startOptimization(forgeSession.draft.text, metadata);
		}
	}
</script>

{#if optimizationState.error}
	<div class="animate-fade-in rounded-xl border border-neon-red/20 bg-neon-red/5 p-4" role="alert" data-testid="error-display">
		<div class="flex items-center gap-3">
			<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-neon-red/10">
				<Icon name="alert-circle" size={16} class="text-neon-red" />
			</div>
			<div class="flex-1">
				<p class="text-sm font-medium text-neon-red">
					{optimizationState.errorType === 'rate_limit' ? 'Rate limit reached' : 'Optimization failed'}
				</p>
				<p class="mt-0.5 text-sm text-text-secondary">{optimizationState.error}</p>
				{#if optimizationState.errorType === 'rate_limit' && retryCountdown > 0}
					<p class="mt-1 font-mono text-xs text-neon-yellow" data-testid="retry-countdown">
						Try again in {retryCountdown}s
					</p>
				{/if}
				{#if optimizationState.errorType === 'rate_limit'}
					<label class="mt-1.5 flex items-center gap-1.5 cursor-pointer">
						<input
							id="forge-error-auto-retry"
							type="checkbox"
							bind:checked={forgeSession.autoRetryOnRateLimit}
							class="accent-neon-cyan"
							data-testid="auto-retry-toggle"
						/>
						<span class="text-[11px] text-text-dim">Auto-retry when limit expires</span>
					</label>
				{/if}
			</div>
			{#if forgeSession.hasText}
				<button
					onclick={handleRetry}
					disabled={optimizationState.errorType === 'rate_limit' && retryCountdown > 0}
					class="shrink-0 rounded-lg border border-neon-cyan/20 bg-neon-cyan/5 px-4 py-1.5 font-mono text-xs text-neon-cyan transition-[background-color] hover:bg-neon-cyan/10 disabled:opacity-40 disabled:cursor-not-allowed"
					data-testid="retry-button"
				>
					Retry
				</button>
			{/if}
		</div>
	</div>
{/if}
