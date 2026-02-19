<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';

	interface Props {
		open: boolean;
		title?: string;
		message?: string;
		confirmLabel?: string;
		cancelLabel?: string;
		variant?: 'danger' | 'warning';
		onconfirm?: () => void;
		oncancel?: () => void;
	}

	let {
		open = false,
		title = 'Are you sure?',
		message = '',
		confirmLabel = 'Confirm',
		cancelLabel = 'Cancel',
		variant = 'danger',
		onconfirm,
		oncancel,
	}: Props = $props();

	let confirmBtn: HTMLButtonElement | undefined = $state();

	const variantClasses = $derived(
		variant === 'danger'
			? {
					icon: 'text-neon-red',
					confirm: 'bg-neon-red/15 text-neon-red hover:bg-neon-red/25 ring-1 ring-neon-red/20',
					border: 'border-neon-red/20',
				}
			: {
					icon: 'text-neon-yellow',
					confirm: 'bg-neon-yellow/15 text-neon-yellow hover:bg-neon-yellow/25 ring-1 ring-neon-yellow/20',
					border: 'border-neon-yellow/20',
				}
	);

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			oncancel?.();
		}
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			oncancel?.();
		}
	}

	// Focus the confirm button when the modal opens
	$effect(() => {
		if (open) {
			// Delay to let DOM render
			requestAnimationFrame(() => {
				confirmBtn?.focus();
			});
		}
	});
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
		onkeydown={handleKeydown}
		onclick={handleBackdropClick}
		data-testid="confirm-modal-backdrop"
	>
		<div
			role="dialog"
			aria-modal="true"
			aria-labelledby="confirm-modal-title"
			aria-describedby={message ? 'confirm-modal-message' : undefined}
			class="animate-fade-in mx-4 w-full max-w-sm rounded-xl border {variantClasses.border} bg-bg-card p-5 shadow-2xl"
			data-testid="confirm-modal"
		>
			<div class="mb-4 flex items-start gap-3">
				<div class="mt-0.5 shrink-0">
					<Icon name="alert-circle" size={20} class={variantClasses.icon} />
				</div>
				<div class="min-w-0">
					<h3
						id="confirm-modal-title"
						class="text-sm font-semibold text-text-primary"
					>
						{title}
					</h3>
					{#if message}
						<p
							id="confirm-modal-message"
							class="mt-1.5 text-xs leading-relaxed text-text-secondary"
						>
							{message}
						</p>
					{/if}
				</div>
			</div>

			<div class="flex justify-end gap-2">
				<button
					onclick={() => oncancel?.()}
					class="rounded-lg bg-bg-hover px-3.5 py-1.5 text-xs text-text-dim transition-colors hover:bg-bg-hover/80 hover:text-text-secondary"
					data-testid="confirm-modal-cancel"
				>
					{cancelLabel}
				</button>
				<button
					bind:this={confirmBtn}
					onclick={() => onconfirm?.()}
					class="rounded-lg px-3.5 py-1.5 text-xs font-medium transition-colors {variantClasses.confirm}"
					data-testid="confirm-modal-confirm"
				>
					{confirmLabel}
				</button>
			</div>
		</div>
	</div>
{/if}
