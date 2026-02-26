<script lang="ts">
	import BrandLogo from './BrandLogo.svelte';
	import DesktopIcon from './DesktopIcon.svelte';
	import DesktopContextMenu from './DesktopContextMenu.svelte';
	import { desktopStore, CELL_WIDTH, CELL_HEIGHT, GRID_PADDING, RECYCLE_BIN_ID } from '$lib/stores/desktopStore.svelte';

	let surfaceEl: HTMLDivElement | undefined = $state();
	let editingIconId: string | null = $state(null);

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
>
	<!-- Wallpaper layer -->
	<div class="desktop-wallpaper">
		<BrandLogo wallpaper />
	</div>

	<!-- Icons layer (absolute positioned) -->
	<div class="relative z-10">
		{#each desktopStore.icons as icon (icon.id)}
			{@const isDragTarget = desktopStore.dragState?.iconId === icon.id && desktopStore.isDragging}
			<div
				class="absolute {isDragTarget ? '' : 'transition-[left,top] duration-150'}"
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
