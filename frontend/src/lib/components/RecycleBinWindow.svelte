<script lang="ts">
	import Icon from './Icon.svelte';
	import FileManagerRow from './FileManagerRow.svelte';
	import DesktopContextMenu from './DesktopContextMenu.svelte';
	import ConfirmModal from './ConfirmModal.svelte';
	import type { ContextAction } from '$lib/stores/desktopStore.svelte';
	import { desktopStore, type RecycleBinItem } from '$lib/stores/desktopStore.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { formatRelativeTime } from '$lib/utils/format';

	// ── Selection ──
	let selectedId: string | null = $state(null);

	// ── Context menu ──
	let ctxMenu = $state({ open: false, x: 0, y: 0, targetId: null as string | null, actions: [] as ContextAction[] });
	let confirmEmpty = $state(false);
	let confirmDeleteId: string | null = $state(null);

	const binItemActions: ContextAction[] = [
		{ id: 'restore', label: 'Restore', icon: 'refresh' },
		{ id: 'delete-permanently', label: 'Delete Permanently', icon: 'x', separator: true, danger: true },
	];

	function openCtxMenu(e: MouseEvent, id: string, actions: ContextAction[]) {
		ctxMenu = { open: true, x: e.clientX, y: e.clientY, targetId: id, actions };
	}

	function closeCtxMenu() {
		ctxMenu = { open: false, x: 0, y: 0, targetId: null, actions: [] };
	}

	function handleContextAction(actionId: string) {
		const targetId = ctxMenu.targetId;
		closeCtxMenu();
		if (!targetId) return;

		switch (actionId) {
			case 'restore':
				handleRestore(targetId);
				break;
			case 'delete-permanently':
				confirmDeleteId = targetId;
				break;
		}
	}

	function sourceTypeIcon(type: RecycleBinItem['sourceType']): string {
		switch (type) {
			case 'optimization': return 'bolt';
			case 'project': return 'folder';
			case 'folder': return 'folder';
			case 'file': return 'file-text';
			default: return 'file-text';
		}
	}

	function handleRestore(itemId: string) {
		const item = desktopStore.recycleBin.find((i) => i.id === itemId);
		const offScreen = desktopStore.restoreItem(itemId);
		selectedId = null;
		if (offScreen && item) {
			toastState.show(`Desktop full — "${item.name}" placed off-screen. Sort or resize to reorganize.`, 'info');
		}
	}

	function confirmPermanentDelete() {
		if (confirmDeleteId) {
			desktopStore.permanentlyDeleteItem(confirmDeleteId);
			if (selectedId === confirmDeleteId) selectedId = null;
			confirmDeleteId = null;
			toastState.show('Item permanently deleted', 'success');
		}
	}

	function handleEmptyBin() {
		confirmEmpty = true;
	}

	function confirmEmptyBin() {
		desktopStore.emptyRecycleBin();
		selectedId = null;
		confirmEmpty = false;
		toastState.show('Recycle Bin emptied', 'success');
	}
</script>

<div class="flex h-full flex-col">
	<!-- Toolbar -->
	<div class="flex items-center justify-between border-b border-border-subtle px-3 py-2">
		<span class="text-xs text-text-secondary">
			{desktopStore.binItemCount} item{desktopStore.binItemCount === 1 ? '' : 's'}
		</span>
		{#if !desktopStore.binIsEmpty}
			<button
				class="flex items-center gap-1.5 rounded px-2 py-1 text-[10px] font-medium text-neon-red/70 transition-colors hover:bg-neon-red/10 hover:text-neon-red"
				onclick={handleEmptyBin}
				data-testid="empty-bin-btn"
			>
				<Icon name="trash-2" size={11} />
				Empty Recycle Bin
			</button>
		{/if}
	</div>

	<!-- Grid full warning -->
	{#if desktopStore.gridFull && !desktopStore.binIsEmpty}
		<div class="flex items-center gap-2 border-b border-neon-yellow/10 bg-neon-yellow/5 px-3 py-1.5">
			<Icon name="alert-circle" size={11} class="text-neon-yellow/60 shrink-0" />
			<span class="text-[10px] text-neon-yellow/70">Desktop full — restored icons will be placed off-screen</span>
		</div>
	{/if}

	<!-- Item list -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="flex-1 overflow-y-auto py-1" onclick={() => selectedId = null}>
		{#if desktopStore.binIsEmpty}
			<div class="flex flex-col items-center justify-center gap-2 pt-16 text-text-dim">
				<Icon name="trash-2" size={32} class="opacity-30" />
				<span class="text-xs">Recycle Bin is empty</span>
			</div>
		{:else}
			<div class="flex flex-col">
				{#each desktopStore.recycleBin as item (item.id)}
					<FileManagerRow
						onselect={() => selectedId = item.id}
						onopen={() => handleRestore(item.id)}
						oncontextmenu={(e) => openCtxMenu(e, item.id, binItemActions)}
						active={selectedId === item.id}
						testId="bin-item-{item.id}"
					>
						<Icon name={sourceTypeIcon(item.sourceType) as any} size={14} class="text-text-dim shrink-0" />
						<div class="flex-1 min-w-0">
							<span class="text-xs font-medium text-text-primary truncate block">{item.name}</span>
						</div>
						<div class="w-20 text-[10px] text-text-dim">
							{formatRelativeTime(item.trashedAt)}
						</div>
					</FileManagerRow>
				{/each}
			</div>
		{/if}
	</div>
</div>

<DesktopContextMenu
	open={ctxMenu.open}
	x={ctxMenu.x}
	y={ctxMenu.y}
	actions={ctxMenu.actions}
	onaction={handleContextAction}
	onclose={closeCtxMenu}
/>

<!-- Confirm: Empty Bin -->
<ConfirmModal
	bind:open={confirmEmpty}
	title="Empty Recycle Bin"
	message="Permanently delete all {desktopStore.binItemCount} item{desktopStore.binItemCount === 1 ? '' : 's'}? This cannot be undone."
	confirmLabel="Empty Bin"
	onconfirm={confirmEmptyBin}
	oncancel={() => confirmEmpty = false}
/>

<!-- Confirm: Delete permanently -->
<ConfirmModal
	open={confirmDeleteId !== null}
	title="Delete Permanently"
	message="This item will be permanently deleted. This cannot be undone."
	confirmLabel="Delete"
	onconfirm={confirmPermanentDelete}
	oncancel={() => confirmDeleteId = null}
/>
