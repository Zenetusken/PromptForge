<script lang="ts">
	import "../app.css";
	import { Tooltip } from "bits-ui";
	import { onNavigate } from "$app/navigation";
	import DesktopTaskbar from "$lib/components/DesktopTaskbar.svelte";
	import DesktopSurface from "$lib/components/DesktopSurface.svelte";
	import DesktopWindow from "$lib/components/DesktopWindow.svelte";
	import StartMenu from "$lib/components/StartMenu.svelte";
	import Toast from "$lib/components/Toast.svelte";
	import ForgeIDEWorkspace from "$lib/components/ForgeIDEWorkspace.svelte";
	import CommandPaletteUI from "$lib/components/CommandPaletteUI.svelte";
	import ConfirmModal from "$lib/components/ConfirmModal.svelte";
	import SnapPreview from "$lib/components/SnapPreview.svelte";
	import SnapAssist from "$lib/components/SnapAssist.svelte";
	import { desktopStore } from "$lib/stores/desktopStore.svelte";
	import { historyState } from "$lib/stores/history.svelte";
	import { optimizationState } from "$lib/stores/optimization.svelte";
	import { providerState } from "$lib/stores/provider.svelte";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { forgeMachine } from "$lib/stores/forgeMachine.svelte";
	import { windowManager } from "$lib/stores/windowManager.svelte";
	import { promptAnalysis } from "$lib/stores/promptAnalysis.svelte";
	import { statsState } from "$lib/stores/stats.svelte";
	import { processScheduler } from "$lib/stores/processScheduler.svelte";
	import { settingsState } from "$lib/stores/settings.svelte";
	import { systemBus } from "$lib/services/systemBus.svelte";
	import { notificationService } from "$lib/services/notificationService.svelte";
	import { commandPalette } from "$lib/services/commandPalette.svelte";
	import { clipboardService } from "$lib/services/clipboardService.svelte";
	import { mcpActivityFeed, MCP_WRITE_TOOLS } from "$lib/services/mcpActivityFeed.svelte";
	import { workspaceManager } from "$lib/stores/workspaceManager.svelte";
	import { saveActiveTabState, restoreTabState, closeIDE } from "$lib/stores/tabCoherence";
	import { onMount } from "svelte";
	import { appRegistry } from "$lib/kernel/services/appRegistry.svelte";
	import { promptForgeApp } from "$lib/apps/promptforge";
	import { helloWorldApp } from "$lib/apps/hello_world";

	// View Transitions API for page navigation crossfade
	onNavigate((navigation) => {
		if (!document.startViewTransition) return;
		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});

	let { children } = $props();

	/** Shared close-tab logic used by command palette tab-close + Ctrl+W shortcut. */
	function closeActiveTab() {
		if (!windowManager.ideVisible || forgeMachine.mode === 'forging') return;
		if (forgeSession.tabs.length <= 1) {
			optimizationState.resetForge();
			forgeMachine.reset();
			forgeSession.reset();
		} else {
			const idx = forgeSession.tabs.findIndex(t => t.id === forgeSession.activeTabId);
			forgeSession.tabs = forgeSession.tabs.filter(t => t.id !== forgeSession.activeTabId);
			const nextTab = forgeSession.tabs[Math.max(0, idx - 1)];
			forgeSession.activeTabId = nextTab.id;
			restoreTabState(nextTab);
		}
	}

	onMount(() => {
		// --- OS Bootstrap: App Registry ---
		appRegistry.register(promptForgeApp);
		appRegistry.register(helloWorldApp);
		appRegistry.setKernel({
			bus: systemBus,
			windowManager,
			commandPalette,
			processScheduler,
			settings: settingsState,
			clipboard: clipboardService,
		});

		if (!historyState.hasLoaded) {
			historyState.loadHistory();
		}
		// Fire stats load immediately in parallel — don't wait for history.
		// Pass -1 as sentinel to bypass the dedup guard on initial load.
		statsState.load(-1);
		providerState.startPolling();

		// --- OS Bootstrap: Process Scheduler & Optimization ---
		const cleanupScheduler = processScheduler.init();
		const cleanupOptimization = optimizationState.init();

		// --- OS Bootstrap: System Bus subscriptions ---
		notificationService.subscribeToBus();

		// MCP Activity Feed connection is managed reactively via $effect below.

		// Reload history/stats when a forge completes (via bus, not direct import chains)
		const unsubForgeComplete = systemBus.on('forge:completed', () => {
			setTimeout(() => {
				historyState.loadHistory();
				statsState.load(historyState.total);
			}, 500);
		});

		// Reload history/stats when external MCP write tools complete
		let mcpReloadTimer: ReturnType<typeof setTimeout> | undefined;
		const unsubMCPComplete = systemBus.on('mcp:tool_complete', (event) => {
			const tool = event.payload.tool_name as string | undefined;
			if (!tool || !(MCP_WRITE_TOOLS as readonly string[]).includes(tool)) return;
			// Debounce to avoid rapid reloads during batch operations
			clearTimeout(mcpReloadTimer);
			mcpReloadTimer = setTimeout(() => {
				historyState.loadHistory();
				statsState.load(historyState.total);
			}, 1000);
		});

		// --- OS Bootstrap: Command Registry ---
		commandPalette.registerAll([
			{
				id: 'ide-open',
				label: 'Open Forge IDE',
				category: 'window',
				shortcut: '/',
				icon: 'terminal',
				execute: () => { windowManager.openIDE(); forgeSession.focusTextarea(); },
			},
			{
				id: 'ide-minimize',
				label: 'Toggle Minimize IDE',
				category: 'window',
				shortcut: 'Ctrl+M',
				icon: 'minus',
				execute: () => {
					if (windowManager.ideSpawned) {
						if (windowManager.ideVisible) windowManager.minimizeWindow('ide');
						else windowManager.focusWindow('ide');
					}
				},
				available: () => windowManager.ideSpawned,
			},
			{
				id: 'tab-new',
				label: 'New Tab',
				category: 'forge',
				shortcut: 'Ctrl+N',
				icon: 'plus',
				execute: () => {
					if (forgeMachine.mode === 'forging') return;
					saveActiveTabState();
					const tab = forgeSession.createTab();
					if (tab) { restoreTabState(tab); forgeSession.activate(); }
				},
			},
			{
				id: 'tab-close',
				label: 'Close Tab',
				category: 'forge',
				shortcut: 'Ctrl+W',
				icon: 'x',
				execute: closeActiveTab,
				available: () => windowManager.ideVisible,
			},
			{
				id: 'window-projects',
				label: 'Open Projects',
				category: 'window',
				icon: 'folder',
				execute: () => windowManager.openProjectsWindow(),
			},
			{
				id: 'window-history',
				label: 'Open History',
				category: 'window',
				icon: 'clock',
				execute: () => windowManager.openHistoryWindow(),
			},
			{
				id: 'window-control-panel',
				label: 'Open Control Panel',
				category: 'settings',
				icon: 'settings',
				execute: () => windowManager.openWindow({ id: 'control-panel', title: 'Control Panel', icon: 'settings' }),
			},
			{
				id: 'window-task-manager',
				label: 'Open Task Manager',
				category: 'window',
				shortcut: 'Ctrl+Shift+Esc',
				icon: 'cpu',
				execute: () => windowManager.openWindow({ id: 'task-manager', title: 'Task Manager', icon: 'cpu' }),
			},
			{
				id: 'window-batch-processor',
				label: 'Open Batch Processor',
				category: 'forge',
				icon: 'layers',
				execute: () => windowManager.openWindow({ id: 'batch-processor', title: 'Batch Processor', icon: 'layers' }),
			},
			{
				id: 'window-strategy-workshop',
				label: 'Open Strategy Workshop',
				category: 'forge',
				icon: 'bar-chart',
				execute: () => windowManager.openWindow({ id: 'strategy-workshop', title: 'Strategy Workshop', icon: 'bar-chart' }),
			},
			{
				id: 'window-template-library',
				label: 'Open Template Library',
				category: 'forge',
				icon: 'file-text',
				execute: () => windowManager.openWindow({ id: 'template-library', title: 'Template Library', icon: 'file-text' }),
			},
			{
				id: 'window-terminal',
				label: 'Open Terminal',
				category: 'window',
				shortcut: 'Ctrl+`',
				icon: 'terminal',
				execute: () => windowManager.openWindow({ id: 'terminal', title: 'Terminal', icon: 'terminal' }),
			},
			{
				id: 'window-network-monitor',
				label: 'Open Network Monitor',
				category: 'window',
				icon: 'activity',
				execute: () => windowManager.openNetworkMonitor(),
			},
			{
				id: 'window-display-settings',
				label: 'Display Settings',
				category: 'settings',
				icon: 'monitor',
				execute: () => windowManager.openDisplaySettings(),
			},
			{
				id: 'command-palette-toggle',
				label: 'Command Palette',
				category: 'navigation',
				shortcut: 'Ctrl+K',
				icon: 'search',
				execute: () => commandPalette.toggle(),
			},
			// ── Snap Layout Commands ──
			{
				id: 'snap-left',
				label: 'Snap Window Left',
				category: 'window',
				shortcut: 'Alt+←',
				icon: 'chevrons-left',
				execute: () => windowManager.snapActiveWindow('left'),
				available: () => !!windowManager.activeWindowId,
			},
			{
				id: 'snap-right',
				label: 'Snap Window Right',
				category: 'window',
				shortcut: 'Alt+→',
				icon: 'chevrons-right',
				execute: () => windowManager.snapActiveWindow('right'),
				available: () => !!windowManager.activeWindowId,
			},
			{
				id: 'snap-layouts',
				label: 'Snap Layouts...',
				category: 'window',
				icon: 'maximize-2',
				execute: () => {
					if (windowManager.activeWindowId) {
						windowManager.openLayoutPicker(windowManager.activeWindowId);
					}
				},
				available: () => !!windowManager.activeWindowId,
			},
			{
				id: 'unsnap-window',
				label: 'Unsnap Window',
				category: 'window',
				icon: 'lock',
				execute: () => {
					if (windowManager.activeWindowId) {
						windowManager.unsnapWindow(windowManager.activeWindowId);
					}
				},
				available: () => !!windowManager.activeWindowId && windowManager.isWindowLocked(windowManager.activeWindowId!),
			},
			{
				id: 'unsnap-all',
				label: 'Unsnap All Windows',
				category: 'window',
				icon: 'x-circle',
				execute: () => windowManager.unsnapAll(),
				available: () => windowManager.snapGroups.length > 0,
			},
			{
				id: 'tile-grid',
				label: 'Tile All (Grid)',
				category: 'window',
				icon: 'layers',
				execute: () => windowManager.tileWindows('grid'),
				available: () => windowManager.windows.filter(w => w.state !== 'minimized').length > 0,
			},
			{
				id: 'tile-columns',
				label: 'Tile All (Columns)',
				category: 'window',
				icon: 'sliders',
				execute: () => windowManager.tileWindows('left-right'),
				available: () => windowManager.windows.filter(w => w.state !== 'minimized').length > 0,
			},
		]);

		// Global keyboard shortcuts
		function handleGlobalKeydown(e: KeyboardEvent) {
			const tag = (e.target as HTMLElement)?.tagName;
			if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT")
				return;

			// Escape — dismiss snap assist/picker → close start menu → restore minimized IDE → close IDE (compose only)
			if (e.key === "Escape") {
				if (windowManager.snapAssistActive) {
					e.preventDefault();
					windowManager.dismissSnapAssist();
					return;
				}
				if (windowManager.layoutPickerWindowId) {
					e.preventDefault();
					windowManager.closeLayoutPicker();
					return;
				}
				if (windowManager.startMenuOpen) {
					e.preventDefault();
					windowManager.closeStartMenu();
					return;
				}
				if (windowManager.ideSpawned && !windowManager.ideVisible) {
					e.preventDefault();
					windowManager.focusWindow('ide');
					return;
				}
				if (windowManager.ideVisible && windowManager.activeWindowId === 'ide' && forgeMachine.mode === "compose") {
					e.preventDefault();
					closeIDE();
					return;
				}
			}

			// Ctrl/Cmd+M — toggle minimize/restore IDE window
			if (e.key === "m" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
				if (windowManager.ideSpawned) {
					e.preventDefault();
					if (windowManager.ideVisible) {
						windowManager.minimizeWindow('ide');
					} else {
						windowManager.focusWindow('ide');
					}
					return;
				}
			}

			// Ctrl/Cmd+N — new forge tab
			if (e.key === "n" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
				e.preventDefault();
				if (e.repeat) return;
				if (forgeMachine.mode === 'forging') return;
				saveActiveTabState();
				const tab = forgeSession.createTab();
				if (tab) { restoreTabState(tab); forgeSession.activate(); }
				return;
			}

			// Ctrl/Cmd+W — close current tab (or exit IDE if last tab)
			if (e.key === "w" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
				if (windowManager.ideVisible) {
					e.preventDefault();
					closeActiveTab();
					return;
				}
			}

			// Ctrl/Cmd+K — toggle command palette
			if (e.key === "k" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
				e.preventDefault();
				commandPalette.toggle();
				return;
			}

			// Ctrl+Shift+Escape — open Task Manager
			if (e.key === "Escape" && (e.ctrlKey || e.metaKey) && e.shiftKey) {
				e.preventDefault();
				windowManager.openWindow({ id: 'task-manager', title: 'Task Manager', icon: 'cpu' });
				return;
			}

			// Alt+Arrow — snap active window
			if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
				if (e.key === "ArrowLeft") {
					e.preventDefault();
					windowManager.snapActiveWindow('left');
					return;
				}
				if (e.key === "ArrowRight") {
					e.preventDefault();
					windowManager.snapActiveWindow('right');
					return;
				}
				if (e.key === "ArrowUp") {
					e.preventDefault();
					windowManager.snapActiveWindow('top');
					return;
				}
				if (e.key === "ArrowDown") {
					e.preventDefault();
					if (windowManager.activeWindowId) {
						const win = windowManager.getWindow(windowManager.activeWindowId);
						if (win?.state === 'maximized') {
							windowManager.restoreWindow(windowManager.activeWindowId);
						} else {
							windowManager.minimizeWindow(windowManager.activeWindowId);
						}
					}
					return;
				}
			}

			// Ctrl+Alt+Arrow — snap to quadrants
			if (e.altKey && e.ctrlKey && !e.metaKey && !e.shiftKey) {
				if (e.key === "ArrowLeft") {
					e.preventDefault();
					windowManager.snapActiveWindow('top-left');
					return;
				}
				if (e.key === "ArrowRight") {
					e.preventDefault();
					windowManager.snapActiveWindow('top-right');
					return;
				}
			}

			// Ctrl+Alt+Shift+Arrow — snap to bottom quadrants
			if (e.altKey && e.ctrlKey && e.shiftKey && !e.metaKey) {
				if (e.key === "ArrowLeft") {
					e.preventDefault();
					windowManager.snapActiveWindow('bottom-left');
					return;
				}
				if (e.key === "ArrowRight") {
					e.preventDefault();
					windowManager.snapActiveWindow('bottom-right');
					return;
				}
			}

			// `/` — open/restore IDE and focus textarea
			if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
				e.preventDefault();
				windowManager.openIDE();
				forgeSession.focusTextarea();
			}
		}
		document.addEventListener("keydown", handleGlobalKeydown);
		return () => {
			providerState.stopPolling();
			notificationService.unsubscribeFromBus();
			unsubForgeComplete();
			unsubMCPComplete();
			cleanupScheduler();
			cleanupOptimization();
			mcpActivityFeed.disconnect();
			clearTimeout(mcpReloadTimer);
			document.removeEventListener("keydown", handleGlobalKeydown);
		};
	});

	// Auto-transition forge machine on optimization completion + feed analysis store + bind to tab
	$effect(() => {
		if (
			optimizationState.forgeResult &&
			!optimizationState.isRunning &&
			forgeMachine.mode === "forging"
		) {
			forgeMachine.complete();
			// Bind result to active tab
			const tab = forgeSession.activeTab;
			if (tab) {
				tab.resultId = optimizationState.forgeResult.id;
				tab.mode = 'review';
			}
			// Feed authoritative pipeline classification back to recommendation engine
			if (optimizationState.forgeResult.task_type) {
				promptAnalysis.updateFromPipeline(
					optimizationState.forgeResult.task_type,
					optimizationState.forgeResult.complexity,
				);
			}
		}
	});

	// Sync tab state for non-pipeline result loads (e.g. openDocument, restoreResult)
	$effect(() => {
		const tab = forgeSession.activeTab;
		const mode = forgeMachine.mode;
		const resultId = optimizationState.forgeResult?.id ?? null;
		if (!tab || mode === 'forging') return;

		if (mode === 'review' && resultId) {
			tab.resultId = resultId;
			tab.mode = 'review';
		} else if (mode === 'compose' && tab.mode !== 'compose') {
			tab.resultId = null;
			tab.mode = 'compose';
		}
	});

	// Sync: if session deactivates AND IDE is closed while machine is in a non-compose mode, reset machine.
	$effect(() => {
		if (!forgeSession.isActive && !windowManager.ideSpawned && forgeMachine.mode !== 'compose') {
			forgeMachine.reset();
		}
	});

	// Reset stats when history is confirmed empty
	$effect(() => {
		if (historyState.hasLoaded && historyState.total === 0) {
			statsState.reset();
		}
	});

	// Sync animation toggle to DOM attribute
	$effect(() => {
		if (typeof document !== 'undefined') {
			document.documentElement.toggleAttribute('data-no-animations', !settingsState.enableAnimations);
		}
	});

	// Keep Recycle Bin window title in sync for the taskbar
	$effect(() => {
		const count = desktopStore.binItemCount;
		if (windowManager.getWindow('recycle-bin')) {
			windowManager.updateWindowTitle('recycle-bin', `Recycle Bin (${count})`);
		}
	});

	// Sync workspace health data from provider polling → workspaceManager
	$effect(() => {
		const workspace = providerState.health?.workspace;
		if (workspace) {
			workspaceManager.updateFromHealth(workspace);
		}
	});

	// Keep History window title in sync
	$effect(() => {
		const count = historyState.total;
		if (windowManager.getWindow('history')) {
			windowManager.updateWindowTitle('history', `History (${count})`);
		}
	});

	// Lazy MCP Activity Feed — connect only when NetworkMonitor is open or MCP is connected
	$effect(() => {
		const networkMonitorOpen = !!windowManager.getWindow('network-monitor');
		const mcpConnected = !!providerState.health?.mcp_connected;
		const shouldConnect = networkMonitorOpen || mcpConnected;

		if (shouldConnect && !mcpActivityFeed.connected) {
			mcpActivityFeed.connect();
		} else if (!shouldConnect && mcpActivityFeed.connected) {
			mcpActivityFeed.disconnect();
		}
	});

	// Breadcrumbs for recycle-bin (Projects/History manage their own breadcrumbs)
	$effect(() => {
		if (windowManager.getWindow('recycle-bin')) {
			windowManager.setBreadcrumbs('recycle-bin', [
				{ label: 'Desktop', icon: 'monitor', action: () => windowManager.closeWindow('recycle-bin') },
				{ label: 'Recycle Bin' },
			]);
		}
	});
</script>

<Tooltip.Provider delayDuration={400} skipDelayDuration={300}>
	<a href="#main-content" class="skip-link">Skip to main content</a>

	<div class="relative flex h-screen w-screen flex-col overflow-hidden bg-bg-primary">
		<!-- Desktop area -->
		<div class="relative flex-1 overflow-hidden" id="main-content" tabindex="-1">
			<!-- Desktop surface (wallpaper + icons) — always the base layer -->
			<DesktopSurface />

			<!-- Window layer -->
			<div class="absolute inset-0 pointer-events-none" style="z-index: 10">
				<!-- Snap Preview (z-index: 9, below windows) -->
				<SnapPreview />

				<!-- IDE Window (special case — static import, custom close handler) -->
				{#if windowManager.ideVisible}
					<DesktopWindow
						windowId="ide"
						title="Forge IDE"
						icon="terminal"
						onclose={() => {
							closeIDE();
						}}
					>
						<ForgeIDEWorkspace />
					</DesktopWindow>
				{/if}

				<!-- Registry-driven app windows (all manifest-declared windows except IDE) -->
				{#each appRegistry.allWindows.filter(w => w.windowId !== 'ide') as reg (reg.windowId)}
					{#if windowManager.getWindow(reg.windowId)}
						{#await reg.loadComponent() then mod}
							{@const Component = mod.default}
							<DesktopWindow windowId={reg.windowId} title={reg.title} icon={reg.icon}>
								<Component />
							</DesktopWindow>
						{:catch}
							<DesktopWindow windowId={reg.windowId} title={reg.title} icon={reg.icon}>
								<p class="p-4 text-text-secondary">Failed to load component.</p>
							</DesktopWindow>
						{/await}
					{/if}
				{/each}

				<!-- Dynamic Folder Windows (not manifest-declared, created at runtime) -->
				{#each windowManager.windows.filter(w => w.id.startsWith('folder-')) as entry (entry.id)}
					{@const folderId = entry.data?.folderId as string}
					{#if folderId}
						{#await import("$lib/components/FolderWindow.svelte") then mod}
							{@const FolderWindow = mod.default}
							<DesktopWindow windowId={entry.id} title={entry.title} icon="folder">
								<FolderWindow {folderId} />
							</DesktopWindow>
						{:catch}
							<DesktopWindow windowId={entry.id} title={entry.title} icon="folder">
								<p class="p-4 text-text-secondary">Failed to load folder.</p>
							</DesktopWindow>
						{/await}
					{/if}
				{/each}

				<!-- Snap Assist Overlay (z-index: 15, above windows) -->
				<SnapAssist />

				</div>

			<!-- SvelteKit page slot — home page script clears stale optimization state -->
			<div class="hidden">{@render children()}</div>

			<!-- Start Menu (z-40) -->
			<div style="z-index: 40" class="absolute inset-0 pointer-events-none">
				<StartMenu />
			</div>
		</div>

		<!-- Taskbar (fixed bottom) -->
		<DesktopTaskbar />
	</div>

	<!-- Desktop confirm dialog (global, for context menu destructive actions) -->
	<ConfirmModal
		bind:open={desktopStore.confirmDialog.open}
		title={desktopStore.confirmDialog.title}
		message={desktopStore.confirmDialog.message}
		confirmLabel={desktopStore.confirmDialog.confirmLabel}
		onconfirm={() => desktopStore.confirmDialog.onConfirm()}
		oncancel={() => desktopStore.confirmDialog.open = false}
	/>

	<div style="z-index: 60">
		<Toast />
	</div>

	<!-- Command Palette (z-70, above everything) -->
	<div style="z-index: 70">
		<CommandPaletteUI />
	</div>
</Tooltip.Provider>
