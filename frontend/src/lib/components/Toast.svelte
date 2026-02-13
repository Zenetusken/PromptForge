<script lang="ts">
	import { toastState } from '$lib/stores/optimization';

	let visible = $derived(toastState.message !== '');

	function getToastClasses(type: string): string {
		switch (type) {
			case 'success':
				return 'border-neon-green/30 bg-neon-green/10';
			case 'error':
				return 'border-neon-red/30 bg-neon-red/10';
			default:
				return 'border-neon-cyan/30 bg-neon-cyan/10';
		}
	}
</script>

{#if visible}
	<div
		class="fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl border px-5 py-3 shadow-lg transition-all duration-300 {getToastClasses(toastState.type)}"
		role="alert"
	>
		{#if toastState.type === 'success'}
			<svg
				class="h-5 w-5 text-neon-green"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="2"
			>
				<polyline points="20 6 9 17 4 12" />
			</svg>
		{:else if toastState.type === 'error'}
			<svg
				class="h-5 w-5 text-neon-red"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="2"
			>
				<circle cx="12" cy="12" r="10" />
				<line x1="15" y1="9" x2="9" y2="15" />
				<line x1="9" y1="9" x2="15" y2="15" />
			</svg>
		{:else}
			<svg
				class="h-5 w-5 text-neon-cyan"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="2"
			>
				<circle cx="12" cy="12" r="10" />
				<line x1="12" y1="16" x2="12" y2="12" />
				<line x1="12" y1="8" x2="12.01" y2="8" />
			</svg>
		{/if}

		<span class="text-sm text-text-primary">{toastState.message}</span>

		<button
			onclick={() => toastState.dismiss()}
			class="ml-2 text-text-dim transition-colors hover:text-text-secondary"
			aria-label="Dismiss notification"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="14"
				height="14"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
			>
				<line x1="18" y1="6" x2="6" y2="18" />
				<line x1="6" y1="6" x2="18" y2="18" />
			</svg>
		</button>
	</div>
{/if}
