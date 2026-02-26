<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';
	import DesktopContextMenu from './DesktopContextMenu.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { computeSnapZone, computeEdgeSnap, computeResizeEdgeSnap, getSnapCandidateWindows, getViewportSize } from '$lib/stores/snapLayout';
	import type { ContextAction } from '$lib/stores/desktopStore.svelte';

	/** Approximate title bar height — keeps title bar above taskbar during drag. */
	const TITLE_BAR_HEIGHT = 32;
	/** Minimum visible window width at screen edges during drag. */
	const MIN_VISIBLE = 100;

	let {
		windowId,
		title = 'Window',
		icon = 'terminal',
		children,
		maximizable = true,
		minimizable = true,
		closable = true,
		onclose,
	}: {
		windowId: string;
		title?: string;
		icon?: string;
		children: Snippet;
		maximizable?: boolean;
		minimizable?: boolean;
		closable?: boolean;
		onclose?: () => void;
	} = $props();

	let win = $derived(windowManager.getWindow(windowId));
	let isFocused = $derived(windowManager.activeWindowId === windowId);
	let isMaximized = $derived(win?.state === 'maximized');
	let isNormal = $derived(win?.state === 'normal');
	let crumbs = $derived(windowManager.getBreadcrumbs(windowId));
	let nav = $derived(windowManager.getNavigation(windowId));
	let hasNav = $derived(crumbs.length > 0 || !!nav);
	let geo = $derived(win?.geometry);

	// --- Snap state ---
	let isLocked = $derived(windowManager.isWindowLocked(windowId));
	let showLayoutPicker = $derived(windowManager.layoutPickerWindowId === windowId);

	// --- Drag state ---
	let dragging = $state(false);
	let dragOffset = $state({ x: 0, y: 0 });

	// --- Resize state ---
	type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';
	let resizing = $state(false);
	let resizeDir: ResizeDir = $state('se');
	let resizeStart = $state({ x: 0, y: 0, gx: 0, gy: 0, gw: 0, gh: 0 });

	// --- Layout picker hover timer ---
	let pickerTimer: ReturnType<typeof setTimeout> | undefined = $state(undefined);
	let pickerGraceTimer: ReturnType<typeof setTimeout> | undefined = $state(undefined);

	// Clean up timers when component is destroyed
	$effect(() => {
		return () => {
			clearTimeout(pickerTimer);
			clearTimeout(pickerGraceTimer);
			if (windowManager.layoutPickerWindowId === windowId) {
				windowManager.closeLayoutPicker();
			}
		};
	});

	// --- Context menu state ---
	let contextMenuOpen = $state(false);
	let contextMenuX = $state(0);
	let contextMenuY = $state(0);
	let contextMenuActions = $derived.by((): ContextAction[] => {
		const actions: ContextAction[] = [];
		actions.push({ id: 'snap-layouts', label: 'Snap Layouts...', icon: 'maximize-2' });
		if (!isLocked) {
			actions.push({ id: 'snap-left', label: 'Snap Left', icon: 'chevrons-left' });
			actions.push({ id: 'snap-right', label: 'Snap Right', icon: 'chevrons-right' });
		}
		if (isLocked) {
			actions.push({ id: 'unsnap', label: 'Unsnap', icon: 'lock' });
		}
		const group = windowManager.getSnapGroup(windowId);
		if (group) {
			actions.push({ id: 'unsnap-group', label: 'Unsnap Group', icon: 'x-circle' });
		}
		actions.push({ id: 'sep-1', label: '', separator: true });
		if (minimizable) {
			actions.push({ id: 'minimize', label: 'Minimize', icon: 'minus' });
		}
		if (maximizable) {
			if (isMaximized) {
				actions.push({ id: 'restore', label: 'Restore', icon: 'minimize-2' });
			} else {
				actions.push({ id: 'maximize', label: 'Maximize', icon: 'maximize-2' });
			}
		}
		if (closable) {
			actions.push({ id: 'sep-2', label: '', separator: true });
			actions.push({ id: 'close', label: 'Close', icon: 'x', danger: true });
		}
		return actions;
	});

	function handleMinimize(e: MouseEvent) {
		e.stopPropagation();
		windowManager.minimizeWindow(windowId);
	}

	function handleToggleMaximize(e: MouseEvent) {
		e.stopPropagation();
		// If locked, unsnap instead
		if (isLocked) {
			windowManager.unsnapWindow(windowId);
			return;
		}
		windowManager.toggleWindowState(windowId);
	}

	function handleClose(e: MouseEvent) {
		e.stopPropagation();
		if (onclose) {
			onclose();
		} else {
			windowManager.closeWindow(windowId);
		}
	}

	function handleTitleBarClick() {
		windowManager.focusWindow(windowId);
	}

	function handleTitleBarDblClick() {
		if (isLocked) {
			windowManager.unsnapWindow(windowId);
			return;
		}
		if (maximizable) {
			windowManager.toggleWindowState(windowId);
		}
	}

	// --- Context menu ---
	function handleTitleBarContextMenu(e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		contextMenuX = e.clientX;
		contextMenuY = e.clientY;
		contextMenuOpen = true;
	}

	function handleContextAction(id: string) {
		contextMenuOpen = false;
		switch (id) {
			case 'snap-layouts':
				windowManager.openLayoutPicker(windowId);
				break;
			case 'snap-left':
				windowManager.snapActiveWindow('left');
				break;
			case 'snap-right':
				windowManager.snapActiveWindow('right');
				break;
			case 'unsnap':
				windowManager.unsnapWindow(windowId);
				break;
			case 'unsnap-group': {
				const group = windowManager.getSnapGroup(windowId);
				if (group) {
					windowManager.unsnapGroup(group.id);
				}
				break;
			}
			case 'minimize':
				windowManager.minimizeWindow(windowId);
				break;
			case 'maximize':
				windowManager.maximizeWindow(windowId);
				break;
			case 'restore':
				windowManager.restoreWindow(windowId);
				break;
			case 'close':
				if (onclose) onclose();
				else windowManager.closeWindow(windowId);
				break;
		}
	}

	// --- Drag handlers (pointer events with capture) ---
	function handleDragStart(e: PointerEvent) {
		if (isLocked) return;
		if (!isNormal || !geo) return;
		if (e.button !== 0) return;
		// Don't initiate drag when clicking buttons (window controls, nav, breadcrumbs)
		if ((e.target as Element).closest('button')) return;
		dragging = true;
		dragOffset = { x: e.clientX - geo.x, y: e.clientY - geo.y };
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}

	function handleDragMove(e: PointerEvent) {
		if (!dragging || !geo) return;
		const { vw, vh } = getViewportSize();
		// Clamp: left/top = 0, right = keep MIN_VISIBLE visible, bottom = title bar above taskbar
		let x = Math.max(-(geo.width - MIN_VISIBLE), Math.min(e.clientX - dragOffset.x, vw - MIN_VISIBLE));
		let y = Math.max(0, Math.min(e.clientY - dragOffset.y, vh - TITLE_BAR_HEIGHT));

		// Compute snap zone for preview (viewport edges take priority)
		const zone = computeSnapZone(e.clientX, e.clientY);
		windowManager.setActiveSnapZone(zone);

		// Magnetic edge snap: only when NOT in a viewport snap zone
		if (!zone) {
			const candidates = getSnapCandidateWindows(windowManager.windows, windowId);
			const snap = computeEdgeSnap({ x, y, width: geo.width, height: geo.height }, candidates);
			x = snap.x;
			y = snap.y;
		}

		windowManager.moveWindow(windowId, x, y);
	}

	function handleDragEnd() {
		if (dragging) {
			// If there's an active snap zone, snap the window
			const zone = windowManager.activeSnapZone;
			if (zone) {
				windowManager.snapWindowToZone(windowId, zone);
			}
			windowManager.setActiveSnapZone(null);
		}
		dragging = false;
	}

	// --- Resize handlers (pointer events with capture) ---
	function handleResizeStart(e: PointerEvent, dir: ResizeDir) {
		if (isLocked) return;
		if (!isNormal || !geo || win?.resizable === false) return;
		e.preventDefault();
		e.stopPropagation();
		resizing = true;
		resizeDir = dir;
		resizeStart = { x: e.clientX, y: e.clientY, gx: geo.x, gy: geo.y, gw: geo.width, gh: geo.height };
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}

	function handleResizeMove(e: PointerEvent) {
		if (!resizing) return;
		const { vw, vh } = getViewportSize();
		const dx = e.clientX - resizeStart.x;
		const dy = e.clientY - resizeStart.y;
		let { gx, gy, gw, gh } = resizeStart;

		if (resizeDir.includes('e')) gw += dx;
		if (resizeDir.includes('w')) { gw -= dx; gx += dx; }
		if (resizeDir.includes('s')) gh += dy;
		if (resizeDir.includes('n')) { gh -= dy; gy += dy; }

		const minW = win?.minWidth ?? 200;
		const minH = win?.minHeight ?? 150;
		if (gw < minW) { if (resizeDir.includes('w')) gx = resizeStart.gx + resizeStart.gw - minW; gw = minW; }
		if (gh < minH) { if (resizeDir.includes('n')) gy = resizeStart.gy + resizeStart.gh - minH; gh = minH; }

		// Magnetic edge snap during resize
		const candidates = getSnapCandidateWindows(windowManager.windows, windowId);
		const snap = computeResizeEdgeSnap({ x: gx, y: gy, width: gw, height: gh }, resizeDir, candidates);
		gx = snap.x;
		gy = snap.y;
		gw = snap.width;
		gh = snap.height;

		// Re-enforce minimums (defensive after snap adjustment)
		if (gw < minW) { if (resizeDir.includes('w')) gx = resizeStart.gx + resizeStart.gw - minW; gw = minW; }
		if (gh < minH) { if (resizeDir.includes('n')) gy = resizeStart.gy + resizeStart.gh - minH; gh = minH; }

		// Clamp: right edge to viewport width, bottom edge to usable area (above taskbar)
		if (gx + gw > vw) gw = vw - Math.max(0, gx);
		if (gy + gh > vh) gh = vh - Math.max(0, gy);

		windowManager.moveAndResizeWindow(windowId, Math.max(0, gx), Math.max(0, gy), gw, gh);
	}

	function handleResizeEnd() {
		resizing = false;
	}

	// --- Layout picker hover ---
	function handleMaxBtnEnter() {
		clearTimeout(pickerTimer);
		clearTimeout(pickerGraceTimer);
		pickerTimer = setTimeout(() => {
			windowManager.openLayoutPicker(windowId);
		}, 300);
	}

	function handleMaxBtnLeave() {
		clearTimeout(pickerTimer);
		// Grace period to cross to popover
		pickerGraceTimer = setTimeout(() => {
			if (showLayoutPicker) {
				windowManager.closeLayoutPicker();
			}
		}, 100);
	}

	function handlePickerEnter() {
		clearTimeout(pickerGraceTimer);
	}

	function handlePickerLeave() {
		windowManager.closeLayoutPicker();
	}

	const RESIZE_HANDLES: { dir: ResizeDir; class: string; cursor: string }[] = [
		{ dir: 'n', class: 'inset-x-1 top-0 h-1', cursor: 'ns-resize' },
		{ dir: 's', class: 'inset-x-1 bottom-0 h-1', cursor: 'ns-resize' },
		{ dir: 'e', class: 'inset-y-1 right-0 w-1', cursor: 'ew-resize' },
		{ dir: 'w', class: 'inset-y-1 left-0 w-1', cursor: 'ew-resize' },
		{ dir: 'ne', class: 'top-0 right-0 h-2 w-2', cursor: 'nesw-resize' },
		{ dir: 'nw', class: 'top-0 left-0 h-2 w-2', cursor: 'nesw-resize' },
		{ dir: 'se', class: 'bottom-0 right-0 h-2 w-2', cursor: 'nwse-resize' },
		{ dir: 'sw', class: 'bottom-0 left-0 h-2 w-2', cursor: 'nesw-resize' },
	];
</script>

{#if win && win.state !== 'minimized'}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="window-chrome animate-window-open {isMaximized ? 'window-chrome--maximized' : 'window-chrome--normal'} {isFocused ? 'window-chrome--focused' : ''}"
		style="z-index: {win.zIndex}{isNormal && geo ? `; position: absolute; top: ${geo.y}px; left: ${geo.x}px; width: ${geo.width}px; height: ${geo.height}px; right: auto; bottom: auto` : ''}"
		onpointerdown={() => windowManager.focusWindow(windowId)}
	>
		<!-- Resize handles (only in normal/windowed mode, not when locked) -->
		{#if isNormal && geo && win.resizable !== false && !isLocked}
			{#each RESIZE_HANDLES as handle (handle.dir)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="absolute z-10 {handle.class} hover:bg-neon-cyan/10"
					style="cursor: {handle.cursor}"
					onpointerdown={(e) => handleResizeStart(e, handle.dir)}
					onpointermove={handleResizeMove}
					onpointerup={handleResizeEnd}
				></div>
			{/each}
		{/if}

		<!-- Title bar (icon + nav/breadcrumbs + window controls) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="window-titlebar {isFocused ? 'window-titlebar--focused' : ''} {dragging || resizing ? 'select-none' : ''}"
			onclick={handleTitleBarClick}
			ondblclick={handleTitleBarDblClick}
			onpointerdown={handleDragStart}
			onpointermove={handleDragMove}
			onpointerup={handleDragEnd}
			oncontextmenu={handleTitleBarContextMenu}
			onkeydown={(e) => { if (e.key === 'Enter') handleTitleBarClick(); }}
		>
			<!-- Left: icon + lock indicator + title -->
			<Icon name={icon as any} size={12} class="{isFocused ? 'text-neon-cyan' : 'text-text-dim'} shrink-0" />

			{#if isLocked}
				<button
					class="snap-lock-icon"
					onclick={(e) => { e.stopPropagation(); windowManager.unsnapWindow(windowId); }}
					aria-label="Unsnap window"
					title="Unsnap"
				>
					<Icon name="lock" size={8} />
				</button>
			{/if}

			{#if !hasNav}
				<span class="flex-1 truncate text-[11px] font-medium {isFocused ? 'text-text-primary' : 'text-text-dim'}">
					{title}
				</span>
			{:else}
				<span class="shrink-0 text-[11px] font-medium {isFocused ? 'text-text-primary' : 'text-text-dim'}">
					{title}
				</span>

				<!-- Center: nav chevrons + breadcrumbs -->
				<div class="flex flex-1 items-center justify-center gap-1.5 min-w-0 px-2">
					{#if nav}
						<button
							class="p-0.5 transition-colors shrink-0 {nav.canGoBack ? 'text-text-dim hover:text-neon-cyan' : 'text-text-dim/20 cursor-default'}"
							onclick={() => nav?.canGoBack && nav.goBack()}
							disabled={!nav.canGoBack}
							aria-label="Back"
						>
							<Icon name="chevron-left" size={12} />
						</button>
						<button
							class="p-0.5 transition-colors shrink-0 {nav.canGoForward ? 'text-text-dim hover:text-neon-cyan' : 'text-text-dim/20 cursor-default'}"
							onclick={() => nav?.canGoForward && nav.goForward()}
							disabled={!nav.canGoForward}
							aria-label="Forward"
						>
							<Icon name="chevron-right" size={12} />
						</button>
						{#if crumbs.length > 0}
							<span class="h-3 w-px bg-border-subtle/40 shrink-0"></span>
						{/if}
					{/if}
					{#each crumbs as seg, i (i)}
						{#if i > 0}
							<span class="text-[9px] text-text-dim/30 select-none shrink-0">/</span>
						{/if}
						{#if seg.action && i < crumbs.length - 1}
							<button
								class="font-mono text-[10px] text-text-dim transition-colors hover:text-neon-cyan shrink-0"
								onclick={seg.action}
							>{seg.label}</button>
						{:else}
							<span class="font-mono text-[10px] text-text-secondary truncate">{seg.label}</span>
						{/if}
					{/each}
				</div>
			{/if}

			<!-- Right: window controls -->
			<div class="flex items-center gap-0.5 shrink-0 relative">
				{#if minimizable}
					<button class="wc-btn" onclick={handleMinimize} aria-label="Minimize">
						<Icon name="minus" size={10} />
					</button>
				{/if}
				{#if maximizable}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						class="relative"
						onmouseenter={handleMaxBtnEnter}
						onmouseleave={handleMaxBtnLeave}
					>
						<button
							class="wc-btn"
							onclick={handleToggleMaximize}
							aria-label={isLocked ? 'Unsnap' : isMaximized ? 'Restore' : 'Maximize'}
						>
							<Icon name={isLocked ? 'lock' : isMaximized ? 'minimize-2' : 'maximize-2'} size={10} />
						</button>

						<!-- Layout Picker popover -->
						{#if showLayoutPicker}
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div
								class="snap-layout-picker"
								style="top: 100%; right: 0; margin-top: 4px;"
								onmouseenter={handlePickerEnter}
								onmouseleave={handlePickerLeave}
							>
								{#await import('./SnapLayoutPicker.svelte') then mod}
									<mod.default {windowId} />
								{:catch}
									<p class="text-text-dim text-[10px]">Failed to load</p>
								{/await}
							</div>
						{/if}
					</div>
				{/if}
				{#if closable}
					<button class="wc-btn wc-close" onclick={handleClose} aria-label="Close">
						<Icon name="x" size={10} />
					</button>
				{/if}
			</div>
		</div>

		<!-- Content area -->
		<div class="flex-1 overflow-hidden {dragging || resizing ? 'pointer-events-none' : ''}">
			{@render children()}
		</div>
	</div>
{/if}

<!-- Title bar context menu -->
<DesktopContextMenu
	open={contextMenuOpen}
	x={contextMenuX}
	y={contextMenuY}
	actions={contextMenuActions}
	onaction={handleContextAction}
	onclose={() => contextMenuOpen = false}
/>
