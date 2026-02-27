<script lang="ts">
	import { onMount } from 'svelte';
	import BrandLogo from './BrandLogo.svelte';
	import DesktopIcon from './DesktopIcon.svelte';
	import DesktopContextMenu from './DesktopContextMenu.svelte';
	import { desktopStore, CELL_WIDTH, CELL_HEIGHT, GRID_PADDING, RECYCLE_BIN_ID, DB_FOLDER_PREFIX, DB_PROMPT_PREFIX } from '$lib/stores/desktopStore.svelte';
	import { fsOrchestrator } from '$lib/stores/filesystemOrchestrator.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { settingsState } from '$lib/stores/settings.svelte';
	import { DRAG_MIME, decodeDragPayload } from '$lib/utils/dragPayload';

	let surfaceEl: HTMLDivElement | undefined = $state();
	let editingIconId: string | null = $state(null);
	let dropTargetIconId: string | null = $state(null);

	// Watch for rename requests from context menu action
	$effect(() => {
		if (desktopStore.requestRename) {
			editingIconId = desktopStore.requestRename;
			desktopStore.requestRename = null;
		}
	});

	function handleSurfaceClick(e: MouseEvent) {
		// Only deselect if clicking the surface itself, not an icon
		if (e.target === surfaceEl || (e.target as HTMLElement)?.closest?.('.desktop-wallpaper')) {
			desktopStore.deselectAll();
			editingIconId = null;
		}
	}

	function handleSurfaceContextMenu(e: MouseEvent) {
		e.preventDefault();
		// Only show desktop context menu if clicking empty space
		const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
		if (!iconEl) {
			desktopStore.openContextMenu(e.clientX, e.clientY, null);
		}
	}

	function handleMouseMove(e: MouseEvent) {
		if (desktopStore.dragState && surfaceEl) {
			e.preventDefault();
			desktopStore.updateDragGhost(e.clientX, e.clientY, surfaceEl.getBoundingClientRect());
		}
	}

	function handleMouseUp() {
		if (desktopStore.dragState) {
			desktopStore.endDrag();
		}
	}

	function handleIconSelect(id: string) {
		// Selecting a different icon exits rename mode
		if (editingIconId && editingIconId !== id) {
			editingIconId = null;
		}
		desktopStore.selectIcon(id);
	}

	function handleIconDblClick(id: string) {
		editingIconId = null;
		if (id === RECYCLE_BIN_ID) {
			desktopStore.executeIconAction(id, 'open-bin');
		} else {
			desktopStore.executeIconAction(id, 'open');
		}
	}

	function handleIconContextMenu(e: MouseEvent, id: string) {
		editingIconId = null;
		desktopStore.openContextMenu(e.clientX, e.clientY, id);
	}

	function handleIconMouseDown(e: MouseEvent, id: string) {
		const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
		if (!iconEl) return;
		const rect = iconEl.getBoundingClientRect();
		const offsetX = e.clientX - rect.left;
		const offsetY = e.clientY - rect.top;
		desktopStore.startDrag(id, offsetX, offsetY);
	}

	function handleLabelClick(id: string) {
		// Only enter rename if icon is already selected AND is non-system
		const icon = desktopStore.icons.find((i) => i.id === id);
		if (desktopStore.selectedIconId === id && icon?.type !== 'system') {
			editingIconId = id;
		}
	}

	function handleRename(id: string, newLabel: string) {
		desktopStore.renameIcon(id, newLabel);
		editingIconId = null;
	}

	function handleContextAction(actionId: string) {
		desktopStore.executeContextAction(actionId);
	}

	function handleContextClose() {
		desktopStore.closeContextMenu();
	}

	// End drag even if mouse leaves the surface element
	$effect(() => {
		if (!desktopStore.dragState) return;
		function endDragGlobal() { desktopStore.endDrag(); }
		function onLeave(e: MouseEvent) { if (!e.relatedTarget) desktopStore.endDrag(); }
		document.addEventListener('mouseup', endDragGlobal);
		document.addEventListener('mouseleave', onLeave);
		return () => {
			document.removeEventListener('mouseup', endDragGlobal);
			document.removeEventListener('mouseleave', onLeave);
		};
	});

	// Reclamp icon positions on window resize
	$effect(() => {
		let timer: ReturnType<typeof setTimeout>;
		function onResize() {
			clearTimeout(timer);
			timer = setTimeout(() => desktopStore.reclampPositions(), 250);
		}
		window.addEventListener('resize', onResize);
		return () => {
			clearTimeout(timer);
			window.removeEventListener('resize', onResize);
		};
	});

	// ── Filesystem folder sync ──

	async function syncRootContent() {
		try {
			const children = await fsOrchestrator.loadChildren(null);
			desktopStore.syncDbFolders(children.filter((n) => n.type === 'folder'));
			desktopStore.syncDbPrompts(children.filter((n) => n.type === 'prompt'));
		} catch {
			// Backend may be unavailable during startup — silently skip
		}
	}

	onMount(() => {
		syncRootContent();
		const unsub1 = systemBus.on('fs:created', () => syncRootContent());
		const unsub2 = systemBus.on('fs:moved', () => syncRootContent());
		const unsub3 = systemBus.on('fs:deleted', () => syncRootContent());
		const unsub4 = systemBus.on('fs:renamed', () => syncRootContent());
		return () => { unsub1(); unsub2(); unsub3(); unsub4(); };
	});

	// ── External drag-and-drop (from FolderWindow, etc.) ──

	function handleExternalDragOver(e: DragEvent) {
		if (!e.dataTransfer?.types.includes(DRAG_MIME)) return;
		e.preventDefault();
		e.dataTransfer.dropEffect = 'move';

		// Detect if hovering over a DB folder icon
		const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
		if (iconEl) {
			const iconId = iconEl.getAttribute('data-desktop-icon') ?? '';
			if (iconId.startsWith(DB_FOLDER_PREFIX)) {
				dropTargetIconId = iconId;
				return;
			}
		}
		dropTargetIconId = null;
	}

	function handleExternalDragLeave(e: DragEvent) {
		// Only clear if leaving the surface entirely
		if (!surfaceEl?.contains(e.relatedTarget as Node)) {
			dropTargetIconId = null;
		}
	}

	async function handleExternalDrop(e: DragEvent) {
		e.preventDefault();
		const targetIcon = dropTargetIconId;
		dropTargetIconId = null;

		const raw = e.dataTransfer?.getData(DRAG_MIME);
		if (!raw) return;
		const payload = decodeDragPayload(raw);
		if (!payload) return;

		const desc = payload.descriptor;
		const type = desc.kind === 'folder' ? 'project' : 'prompt';

		if (targetIcon) {
			// Drop on a folder icon → move into that folder
			const folderId = desktopStore.getDbFolderId(targetIcon);
			if (folderId) {
				await fsOrchestrator.move(type as 'project' | 'prompt', desc.id, folderId);
			}
		} else {
			// Drop on empty desktop → move to root
			await fsOrchestrator.move(type as 'project' | 'prompt', desc.id, null);
		}
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="desktop-surface"
	bind:this={surfaceEl}
	onclick={handleSurfaceClick}
	oncontextmenu={handleSurfaceContextMenu}
	onmousemove={handleMouseMove}
	onmouseup={handleMouseUp}
	ondragover={handleExternalDragOver}
	ondragleave={handleExternalDragLeave}
	ondrop={handleExternalDrop}
>
	<!-- Wallpaper layer -->
	<div class="desktop-wallpaper">
		<BrandLogo wallpaper level={settingsState.wallpaperMode} />
	</div>

	<!-- Icons layer (absolute positioned) -->
	<div class="relative z-10">
		{#each desktopStore.icons as icon (icon.id)}
			{@const isDragTarget = desktopStore.dragState?.iconId === icon.id && desktopStore.isDragging}
			{@const isDropTarget = dropTargetIconId === icon.id}
			<div
				class="absolute {isDragTarget ? '' : 'transition-[left,top] duration-150'} {isDropTarget ? 'ring-1 ring-neon-cyan/40 rounded-lg bg-neon-cyan/5' : ''}"
				style="left: {icon.position.col * CELL_WIDTH + GRID_PADDING}px; top: {icon.position.row * CELL_HEIGHT + GRID_PADDING}px; width: {CELL_WIDTH}px; height: {CELL_HEIGHT}px;"
				data-desktop-icon={icon.id}
			>
				<DesktopIcon
					id={icon.id}
					label={icon.label}
					icon={icon.icon}
					color={icon.color}
					selected={desktopStore.selectedIconId === icon.id}
					dragging={isDragTarget}
					editing={editingIconId === icon.id}
					renameable={icon.type !== 'system'}
					binIndicator={icon.id === RECYCLE_BIN_ID}
					binEmpty={desktopStore.binIsEmpty}
					onselect={() => handleIconSelect(icon.id)}
					ondblclick={() => handleIconDblClick(icon.id)}
					oncontextmenu={(e) => handleIconContextMenu(e, icon.id)}
					onmousedown={(e) => handleIconMouseDown(e, icon.id)}
					onlabelclick={() => handleLabelClick(icon.id)}
					onrename={(newLabel) => handleRename(icon.id, newLabel)}
				/>
			</div>
		{/each}

		<!-- Drag ghost indicator -->
		{#if desktopStore.isDragging && desktopStore.dragState}
			<div
				class="absolute pointer-events-none rounded-lg border border-dashed border-neon-cyan/30"
				style="left: {desktopStore.dragState.ghostCol * CELL_WIDTH + GRID_PADDING}px; top: {desktopStore.dragState.ghostRow * CELL_HEIGHT + GRID_PADDING}px; width: {CELL_WIDTH - 4}px; height: {CELL_HEIGHT - 4}px;"
			></div>
		{/if}
	</div>

	<!-- Context Menu -->
	<DesktopContextMenu
		open={desktopStore.contextMenu.open}
		x={desktopStore.contextMenu.x}
		y={desktopStore.contextMenu.y}
		actions={desktopStore.contextMenu.actions}
		onaction={handleContextAction}
		onclose={handleContextClose}
	/>
</div>
