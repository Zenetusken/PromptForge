<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';

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

	// --- Drag state ---
	let dragging = $state(false);
	let dragOffset = $state({ x: 0, y: 0 });

	// --- Resize state ---
	type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';
	let resizing = $state(false);
	let resizeDir: ResizeDir = $state('se');
	let resizeStart = $state({ x: 0, y: 0, gx: 0, gy: 0, gw: 0, gh: 0 });

	function handleMinimize(e: MouseEvent) {
		e.stopPropagation();
		windowManager.minimizeWindow(windowId);
	}

	function handleToggleMaximize(e: MouseEvent) {
		e.stopPropagation();
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
		if (maximizable) {
			windowManager.toggleWindowState(windowId);
		}
	}

	// --- Drag handlers ---
	function handleDragStart(e: MouseEvent) {
		if (!isNormal || !geo) return;
		// Only left button, and don't drag on control buttons
		if (e.button !== 0) return;
		dragging = true;
		dragOffset = { x: e.clientX - geo.x, y: e.clientY - geo.y };
		document.addEventListener('mousemove', handleDragMove);
		document.addEventListener('mouseup', handleDragEnd);
	}

	function handleDragMove(e: MouseEvent) {
		if (!dragging) return;
		const x = Math.max(0, e.clientX - dragOffset.x);
		const y = Math.max(0, e.clientY - dragOffset.y);
		windowManager.moveWindow(windowId, x, y);

		// Snap-to-edge: if dragged to screen edge, maximize or half-snap
		const vw = window.innerWidth;
		if (e.clientX <= 2) {
			// Snap left half
			dragging = false;
			document.removeEventListener('mousemove', handleDragMove);
			document.removeEventListener('mouseup', handleDragEnd);
			const vh = window.innerHeight - 40;
			windowManager.moveWindow(windowId, 0, 0);
			windowManager.resizeWindow(windowId, Math.floor(vw / 2), vh);
		} else if (e.clientX >= vw - 2) {
			// Snap right half
			dragging = false;
			document.removeEventListener('mousemove', handleDragMove);
			document.removeEventListener('mouseup', handleDragEnd);
			const vh = window.innerHeight - 40;
			windowManager.moveWindow(windowId, Math.floor(vw / 2), 0);
			windowManager.resizeWindow(windowId, Math.floor(vw / 2), vh);
		} else if (e.clientY <= 2) {
			// Snap maximize
			dragging = false;
			document.removeEventListener('mousemove', handleDragMove);
			document.removeEventListener('mouseup', handleDragEnd);
			windowManager.maximizeWindow(windowId);
		}
	}

	function handleDragEnd() {
		dragging = false;
		document.removeEventListener('mousemove', handleDragMove);
		document.removeEventListener('mouseup', handleDragEnd);
	}

	// --- Resize handlers ---
	function handleResizeStart(e: MouseEvent, dir: ResizeDir) {
		if (!isNormal || !geo || win?.resizable === false) return;
		e.preventDefault();
		e.stopPropagation();
		resizing = true;
		resizeDir = dir;
		resizeStart = { x: e.clientX, y: e.clientY, gx: geo.x, gy: geo.y, gw: geo.width, gh: geo.height };
		document.addEventListener('mousemove', handleResizeMove);
		document.addEventListener('mouseup', handleResizeEnd);
	}

	function handleResizeMove(e: MouseEvent) {
		if (!resizing) return;
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

		windowManager.moveWindow(windowId, Math.max(0, gx), Math.max(0, gy));
		windowManager.resizeWindow(windowId, gw, gh);
	}

	function handleResizeEnd() {
		resizing = false;
		document.removeEventListener('mousemove', handleResizeMove);
		document.removeEventListener('mouseup', handleResizeEnd);
	}

	// Safety: reset drag/resize if mouseup was missed (mouse left viewport,
	// event captured by another handler, or tab lost focus).
	$effect(() => {
		if (!dragging && !resizing) return;
		function resetDragResize() {
			if (dragging) {
				dragging = false;
				document.removeEventListener('mousemove', handleDragMove);
				document.removeEventListener('mouseup', handleDragEnd);
			}
			if (resizing) {
				resizing = false;
				document.removeEventListener('mousemove', handleResizeMove);
				document.removeEventListener('mouseup', handleResizeEnd);
			}
		}
		window.addEventListener('blur', resetDragResize);
		document.addEventListener('visibilitychange', resetDragResize);
		return () => {
			window.removeEventListener('blur', resetDragResize);
			document.removeEventListener('visibilitychange', resetDragResize);
		};
	});

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
		onmousedown={() => windowManager.focusWindow(windowId)}
	>
		<!-- Resize handles (only in normal/windowed mode) -->
		{#if isNormal && geo && win.resizable !== false}
			{#each RESIZE_HANDLES as handle (handle.dir)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="absolute z-10 {handle.class} hover:bg-neon-cyan/10"
					style="cursor: {handle.cursor}"
					onmousedown={(e) => handleResizeStart(e, handle.dir)}
				></div>
			{/each}
		{/if}

		<!-- Title bar (icon + nav/breadcrumbs + window controls) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="window-titlebar {isFocused ? 'window-titlebar--focused' : ''} {dragging || resizing ? 'select-none' : ''}"
			onclick={handleTitleBarClick}
			ondblclick={handleTitleBarDblClick}
			onmousedown={handleDragStart}
			onkeydown={(e) => { if (e.key === 'Enter') handleTitleBarClick(); }}
		>
			<!-- Left: icon + title (compact when nav/crumbs shown) -->
			<Icon name={icon as any} size={12} class="{isFocused ? 'text-neon-cyan' : 'text-text-dim'} shrink-0" />
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
			<div class="flex items-center gap-0.5 shrink-0">
				{#if minimizable}
					<button class="wc-btn" onclick={handleMinimize} aria-label="Minimize">
						<Icon name="minus" size={10} />
					</button>
				{/if}
				{#if maximizable}
					<button class="wc-btn" onclick={handleToggleMaximize} aria-label={isMaximized ? 'Restore' : 'Maximize'}>
						<Icon name={isMaximized ? 'minimize-2' : 'maximize-2'} size={10} />
					</button>
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
