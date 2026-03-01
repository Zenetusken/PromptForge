<script lang="ts">
	import { AlertDialog } from 'bits-ui';
	import Icon from '$lib/components/Icon.svelte';
	import { fsOrchestrator } from '$lib/stores/filesystemOrchestrator.svelte';
	import type { FsNode } from '$lib/api/client';

	let {
		open = $bindable(false),
		nodeType = null,
		nodeId = null,
		onmove,
		oncancel,
	}: {
		open: boolean;
		nodeType: 'project' | 'prompt' | null;
		nodeId: string | null;
		onmove?: (type: 'project' | 'prompt', id: string, targetFolderId: string | null) => void;
		oncancel?: () => void;
	} = $props();

	let folders: FsNode[] = $state([]);
	let selectedFolderId: string | null | undefined = $state(undefined);
	let loading = $state(false);

	const hasSelection = $derived(selectedFolderId !== undefined);

	// Load root folders when dialog opens
	$effect(() => {
		if (open) {
			selectedFolderId = undefined;
			loading = true;
			fsOrchestrator.loadChildren(null).then((children) => {
				// Filter to folders, exclude self if moving a folder
				folders = children.filter((n) => {
					if (n.type !== 'folder') return false;
					if (nodeType === 'project' && nodeId === n.id) return false;
					return true;
				});
				loading = false;
			}).catch(() => {
				folders = [];
				loading = false;
			});
		}
	});

	function handleMove() {
		if (!nodeType || !nodeId || !hasSelection) return;
		onmove?.(nodeType, nodeId, selectedFolderId ?? null);
	}
</script>

<AlertDialog.Root bind:open onOpenChange={(o) => { if (!o) oncancel?.(); }}>
	<AlertDialog.Portal>
		<AlertDialog.Overlay data-testid="move-to-dialog-backdrop" />
		<AlertDialog.Content
			class="!border border-border-subtle"
			data-testid="move-to-dialog"
		>
			<div class="mb-4 flex items-start gap-3">
				<div class="mt-0.5 shrink-0">
					<Icon name="folder-open" size={20} class="text-neon-cyan" />
				</div>
				<div class="min-w-0">
					<AlertDialog.Title class="text-sm font-semibold text-text-primary">
						Move to...
					</AlertDialog.Title>
					<AlertDialog.Description class="mt-1 text-xs text-text-secondary">
						Select a destination folder.
					</AlertDialog.Description>
				</div>
			</div>

			<div class="max-h-48 overflow-y-auto rounded-lg border border-border-subtle bg-bg-input">
				{#if loading}
					<div class="px-3 py-3 text-xs text-text-dim text-center">Loading...</div>
				{:else if folders.length === 0}
					<div class="px-3 py-3 text-xs text-text-dim text-center">No folders available</div>
				{:else}
					{#each folders as folder (folder.id)}
						<button
							type="button"
							class="flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors
								{selectedFolderId === folder.id ? 'bg-neon-cyan/10 text-neon-cyan' : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'}"
							onclick={() => selectedFolderId = folder.id}
							data-testid="move-to-folder-{folder.id}"
						>
							<Icon name="folder" size={14} class={selectedFolderId === folder.id ? 'text-neon-yellow' : 'text-text-dim'} />
							<span>{folder.name}</span>
						</button>
					{/each}
				{/if}
			</div>

			<div class="mt-4 flex justify-end gap-2">
				<AlertDialog.Cancel
					class="rounded-lg bg-bg-hover px-3.5 py-1.5 text-xs text-text-dim transition-colors hover:bg-bg-hover/80 hover:text-text-secondary"
					data-testid="move-to-cancel"
				>
					Cancel
				</AlertDialog.Cancel>
				<AlertDialog.Action
					onclick={handleMove}
					disabled={!hasSelection}
					class="rounded-lg px-3.5 py-1.5 text-xs font-medium transition-colors ring-1
						{hasSelection
							? 'bg-neon-cyan/15 text-neon-cyan hover:bg-neon-cyan/25 ring-neon-cyan/20'
							: 'bg-bg-hover text-text-dim ring-border-subtle cursor-not-allowed'}"
					data-testid="move-to-confirm"
				>
					Move
				</AlertDialog.Action>
			</div>
		</AlertDialog.Content>
	</AlertDialog.Portal>
</AlertDialog.Root>
