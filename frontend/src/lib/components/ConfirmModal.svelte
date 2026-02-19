<script lang="ts">
	import { AlertDialog } from 'bits-ui';
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
		open = $bindable(false),
		title = 'Are you sure?',
		message = '',
		confirmLabel = 'Confirm',
		cancelLabel = 'Cancel',
		variant = 'danger',
		onconfirm,
		oncancel,
	}: Props = $props();

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
</script>

<AlertDialog.Root bind:open onOpenChange={(o) => { if (!o) oncancel?.(); }}>
	<AlertDialog.Portal>
		<AlertDialog.Overlay data-testid="confirm-modal-backdrop" />
		<AlertDialog.Content
			class="!border {variantClasses.border}"
			data-testid="confirm-modal"
		>
			<div class="mb-4 flex items-start gap-3">
				<div class="mt-0.5 shrink-0">
					<Icon name="alert-circle" size={20} class={variantClasses.icon} />
				</div>
				<div class="min-w-0">
					<AlertDialog.Title
						class="text-sm font-semibold text-text-primary"
					>
						{title}
					</AlertDialog.Title>
					{#if message}
						<AlertDialog.Description
							class="mt-1.5 text-xs leading-relaxed text-text-secondary"
						>
							{message}
						</AlertDialog.Description>
					{/if}
				</div>
			</div>

			<div class="flex justify-end gap-2">
				<AlertDialog.Cancel
					class="rounded-lg bg-bg-hover px-3.5 py-1.5 text-xs text-text-dim transition-colors hover:bg-bg-hover/80 hover:text-text-secondary"
					data-testid="confirm-modal-cancel"
				>
					{cancelLabel}
				</AlertDialog.Cancel>
				<AlertDialog.Action
					onclick={() => onconfirm?.()}
					class="rounded-lg px-3.5 py-1.5 text-xs font-medium transition-colors {variantClasses.confirm}"
					data-testid="confirm-modal-confirm"
				>
					{confirmLabel}
				</AlertDialog.Action>
			</div>
		</AlertDialog.Content>
	</AlertDialog.Portal>
</AlertDialog.Root>
