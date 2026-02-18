<script lang="ts">
	import { toastState } from '$lib/stores/toast.svelte';
	import Icon from './Icon.svelte';

	function toastClasses(type: 'success' | 'error' | 'info'): string {
		switch (type) {
			case 'success': return 'border-neon-green/20 bg-bg-card';
			case 'error': return 'border-neon-red/20 bg-bg-card';
			default: return 'border-neon-cyan/20 bg-bg-card';
		}
	}
</script>

<div class="fixed bottom-6 right-6 z-50 flex flex-col gap-2" id="toast-container">
	{#each toastState.toasts as toast (toast.id)}
		<div
			role="alert"
			data-testid="toast-notification"
			class="flex items-center gap-3 rounded-xl border px-4 py-3 text-sm shadow-2xl {toastClasses(toast.type)} {toast.dismissing ? 'animate-slide-out-right' : 'animate-slide-in-right'}"
		>
			{#if toast.type === 'success'}
				<div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-neon-green/15">
					<Icon name="check" size={14} class="text-neon-green" />
				</div>
			{:else if toast.type === 'error'}
				<div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-neon-red/15">
					<Icon name="x" size={14} class="text-neon-red" />
				</div>
			{:else}
				<div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-neon-cyan/15">
					<Icon name="info" size={14} class="text-neon-cyan" />
				</div>
			{/if}
			<span class="text-text-primary">{toast.message}</span>
			<button
				class="btn-icon ml-1"
				aria-label="Dismiss notification"
				onclick={() => toastState.dismiss(toast.id)}
			>
				<Icon name="x" size={12} />
			</button>
		</div>
	{/each}
</div>
