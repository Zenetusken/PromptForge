<script lang="ts">
	import { onMount } from 'svelte';
	import BrandLogo from './BrandLogo.svelte';
	import DesktopIcon from './DesktopIcon.svelte';
	import DesktopContextMenu from './DesktopContextMenu.svelte';
	import { desktopStore, CELL_WIDTH, CELL_HEIGHT, GRID_PADDING, RECYCLE_BIN_ID, DB_FOLDER_PREFIX, DB_PROMPT_PREFIX } from '$lib/stores/desktopStore.svelte';
	import { fsOrchestrator } from '$lib/stores/filesystemOrchestrator.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { settingsState } from '$lib/stores/settings.svelte';
	import { DRAG_MIME, decodeDragPayload, encodeDragPayload } from '$lib/utils/dragPayload';
	import { createFolderDescriptor, createPromptDescriptor } from '$lib/utils/fileDescriptor';

	let surfaceEl: HTMLDivElement | undefined = $state();
	let editingIconId: string | null = $state(null);
	let dropTargetIconId: string | null = $state(null);
	let draggingDesktopIconId: string | null = $state(null);

	// ── Marquee selection state (transient UI — does not belong in store) ──
	let marqueeActive = $state(false);
	let marqueeStartX = $state(0);
	let marqueeStartY = $state(0);
	let marqueeEndX = $state(0);
	let marqueeEndY = $state(0);
	let marqueeCtrl = $state(false);
	let preMarqueeSelection = $state<Set<string>>(new Set());

	const marqueeRect = $derived({
		left: Math.min(marqueeStartX, marqueeEndX),
		top: Math.min(marqueeStartY, marqueeEndY),
		width: Math.abs(marqueeEndX - marqueeStartX),
		height: Math.abs(marqueeEndY - marqueeStartY),
	});

	function isDbIcon(iconId: string): boolean {
		return iconId.startsWith(DB_FOLDER_PREFIX) || iconId.startsWith(DB_PROMPT_PREFIX);
	}

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
			if (!(e.ctrlKey || e.metaKey)) {
				desktopStore.deselectAll();
			}
			editingIconId = null;
		}
	}

	function handleSurfaceMouseDown(e: MouseEvent) {
		// Only start marquee on left-click on empty surface (not on icons), not during grid drag
		if (e.button !== 0) return;
		if (desktopStore.dragState) return;
		const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
		if (iconEl) return;
		if (!surfaceEl) return;

		const rect = surfaceEl.getBoundingClientRect();
		marqueeStartX = e.clientX - rect.left;
		marqueeStartY = e.clientY - rect.top;
		marqueeEndX = marqueeStartX;
		marqueeEndY = marqueeStartY;
		marqueeCtrl = e.ctrlKey || e.metaKey;
		preMarqueeSelection = new Set(marqueeCtrl ? desktopStore.selectedIconIds : []);
		marqueeActive = true;
	}

	function handleSurfaceContextMenu(e: MouseEvent) {
		e.preventDefault();
		// Only show desktop context menu if clicking empty space
		const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
		if (!iconEl) {
			desktopStore.openContextMenu(e.clientX, e.clientY, null);
		}
	}

	function updateMarqueeSelection() {
		if (!surfaceEl) return;
		const rect = marqueeRect;
		// Skip tiny marquees (< 5px) — treat as click
		if (rect.width < 5 && rect.height < 5) return;

		const intersected = new Set<string>();
		for (const icon of desktopStore.icons) {
			const iconLeft = icon.position.col * CELL_WIDTH + GRID_PADDING;
			const iconTop = icon.position.row * CELL_HEIGHT + GRID_PADDING;
			const iconRight = iconLeft + CELL_WIDTH;
			const iconBottom = iconTop + CELL_HEIGHT;

			// AABB intersection test
			if (
				iconLeft < rect.left + rect.width &&
				iconRight > rect.left &&
				iconTop < rect.top + rect.height &&
				iconBottom > rect.top
			) {
				intersected.add(icon.id);
			}
		}

		if (marqueeCtrl) {
			// Toggle: start from pre-marquee selection, toggle intersected
			const next = new Set(preMarqueeSelection);
			for (const id of intersected) {
				if (preMarqueeSelection.has(id)) {
					next.delete(id);
				} else {
					next.add(id);
				}
			}
			desktopStore.selectedIconIds = next;
		} else {
			desktopStore.selectedIconIds = intersected;
		}
	}

	function handleMouseMove(e: MouseEvent) {
		if (marqueeActive && surfaceEl) {
			const rect = surfaceEl.getBoundingClientRect();
			marqueeEndX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
			marqueeEndY = Math.max(0, Math.min(e.clientY - rect.top, rect.height));
			updateMarqueeSelection();
			return;
		}
		if (desktopStore.dragState && surfaceEl) {
			e.preventDefault();
			desktopStore.updateDragGhost(e.clientX, e.clientY, surfaceEl.getBoundingClientRect());
		}
	}

	function handleMouseUp() {
		if (marqueeActive) {
			marqueeActive = false;
			return;
		}
		if (desktopStore.dragState) {
			desktopStore.endDrag();
		}
	}

	function handleIconSelect(id: string, e?: MouseEvent) {
		// Selecting a different icon exits rename mode
		if (editingIconId && editingIconId !== id) {
			editingIconId = null;
		}
		if (e && (e.ctrlKey || e.metaKey)) {
			desktopStore.toggleIconSelection(id);
		} else {
			desktopStore.selectIcon(id);
		}
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
		// If icon is already in multi-selection, preserve selection
		if (!desktopStore.selectedIconIds.has(id)) {
			desktopStore.selectIcon(id);
		}
		desktopStore.openContextMenu(e.clientX, e.clientY, id);
	}

	function handleIconMouseDown(e: MouseEvent, id: string) {
		if (isDbIcon(id)) return; // DB icons use HTML5 drag, not grid repositioning
		const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
		if (!iconEl) return;
		const rect = iconEl.getBoundingClientRect();
		const offsetX = e.clientX - rect.left;
		const offsetY = e.clientY - rect.top;
		desktopStore.startDrag(id, offsetX, offsetY);
	}

	function handleLabelClick(id: string) {
		// Only enter rename if icon is already selected, single-selected, AND is non-system
		const icon = desktopStore.icons.find((i) => i.id === id);
		if (desktopStore.selectedIconId === id && !desktopStore.isMultiSelect && icon?.type !== 'system') {
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

	// End drag/marquee even if mouse leaves the surface element
	$effect(() => {
		if (!desktopStore.dragState && !marqueeActive) return;
		function endGlobal() {
			if (marqueeActive) marqueeActive = false;
			if (desktopStore.dragState) desktopStore.endDrag();
		}
		function onLeave(e: MouseEvent) {
			if (!e.relatedTarget) endGlobal();
		}
		document.addEventListener('mouseup', endGlobal);
		document.addEventListener('mouseleave', onLeave);
		return () => {
			document.removeEventListener('mouseup', endGlobal);
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

	// ── Desktop icon native drag (DB-backed icons → FolderWindow or folder icon) ──

	function handleIconDragStart(e: DragEvent, icon: { id: string; label: string }) {
		if (!e.dataTransfer) return;
		draggingDesktopIconId = icon.id;

		if (icon.id.startsWith(DB_FOLDER_PREFIX)) {
			const folderId = icon.id.slice(DB_FOLDER_PREFIX.length);
			const payload = { descriptor: createFolderDescriptor(folderId, icon.label), source: 'desktop' as const };
			e.dataTransfer.setData(DRAG_MIME, encodeDragPayload(payload));
		} else if (icon.id.startsWith(DB_PROMPT_PREFIX)) {
			const promptId = icon.id.slice(DB_PROMPT_PREFIX.length);
			const name = icon.label.replace(/\.md$/, '');
			const payload = { descriptor: createPromptDescriptor(promptId, '', name), source: 'desktop' as const };
			e.dataTransfer.setData(DRAG_MIME, encodeDragPayload(payload));
		}
		e.dataTransfer.effectAllowed = 'move';
	}

	function handleIconDragEnd() {
		draggingDesktopIconId = null;
	}

	// ── External drag-and-drop (from FolderWindow, etc.) ──

	function handleExternalDragOver(e: DragEvent) {
		if (!e.dataTransfer?.types.includes(DRAG_MIME)) return;

		// Detect if hovering over a desktop icon
		const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
		if (iconEl) {
			const iconId = iconEl.getAttribute('data-desktop-icon') ?? '';
			// Only folder icons are valid drop targets; skip the icon being dragged
			if (iconId.startsWith(DB_FOLDER_PREFIX) && iconId !== draggingDesktopIconId) {
				e.preventDefault();
				e.dataTransfer.dropEffect = 'move';
				dropTargetIconId = iconId;
				return;
			}
			// Non-folder icon — not a valid drop target, don't accept
			dropTargetIconId = null;
			return;
		}

		// Empty desktop surface — valid drop target (move to root)
		e.preventDefault();
		e.dataTransfer.dropEffect = 'move';
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
		const type: 'project' | 'prompt' = desc.kind === 'folder' ? 'project' : 'prompt';

		if (targetIcon) {
			// Drop on a folder icon → move into that folder
			const folderId = desktopStore.getDbFolderId(targetIcon);
			if (folderId) {
				// Prevent dropping a folder on itself
				if (desc.kind === 'folder' && desc.id === folderId) return;
				await fsOrchestrator.move(type, desc.id, folderId);
			}
		} else {
			// If drop landed on a non-folder icon, ignore (not a valid target)
			const iconEl = (e.target as HTMLElement)?.closest?.('[data-desktop-icon]');
			if (iconEl) return;

			// Skip if already at root (desktop → desktop empty space is a no-op)
			if (payload.source === 'desktop') return;
			// Drop on empty desktop → move to root
			await fsOrchestrator.move(type, desc.id, null);
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
	onmousedown={handleSurfaceMouseDown}
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
			{@const isNativeDragging = draggingDesktopIconId === icon.id}
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
					selected={desktopStore.selectedIconIds.has(icon.id)}
					dragging={isDragTarget || isNativeDragging}
					editing={editingIconId === icon.id}
					renameable={icon.type !== 'system'}
					binIndicator={icon.id === RECYCLE_BIN_ID}
					binEmpty={desktopStore.binIsEmpty}
					draggable={isDbIcon(icon.id) && editingIconId !== icon.id}
					onselect={(e) => handleIconSelect(icon.id, e)}
					ondblclick={() => handleIconDblClick(icon.id)}
					oncontextmenu={(e) => handleIconContextMenu(e, icon.id)}
					onmousedown={(e) => handleIconMouseDown(e, icon.id)}
					ondragstart={(e) => handleIconDragStart(e, icon)}
					ondragend={handleIconDragEnd}
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

	<!-- Marquee selection rectangle -->
	{#if marqueeActive && (marqueeRect.width > 5 || marqueeRect.height > 5)}
		<div
			class="absolute pointer-events-none border border-neon-cyan/40 bg-neon-cyan/5 z-20"
			style="left:{marqueeRect.left}px;top:{marqueeRect.top}px;width:{marqueeRect.width}px;height:{marqueeRect.height}px;"
		></div>
	{/if}

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
