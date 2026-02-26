import { systemBus } from '$lib/services/systemBus.svelte';

const STORAGE_KEY = 'pf_wm';

export type WindowId = string;
export type WindowState = 'normal' | 'maximized' | 'minimized';

export interface WindowGeometry {
	x: number;
	y: number;
	width: number;
	height: number;
}

export interface WindowEntry {
	id: WindowId;
	title: string;
	icon: string;
	state: WindowState;
	zIndex: number;
	route?: string;
	data?: Record<string, unknown>;
	geometry?: WindowGeometry;
	minWidth?: number;
	minHeight?: number;
	resizable?: boolean;
}

/** Windows that persist independently of routes. Minimized on active taskbar click. */
export const PERSISTENT_WINDOW_IDS = new Set([
	'ide', 'recycle-bin', 'projects', 'history',
	'control-panel', 'task-manager',
	'batch-processor', 'strategy-workshop', 'template-library', 'terminal',
	'network-monitor',
]);

export interface BreadcrumbSegment {
	label: string;
	icon?: string;
	/** Called when clicked. Last segment (current location) should have no action. */
	action?: () => void;
}

export interface WindowNavigation {
	canGoBack: boolean;
	canGoForward: boolean;
	goBack: () => void;
	goForward: () => void;
}

interface PersistedState {
	windows: WindowEntry[];
	activeWindowId: WindowId | null;
	nextZIndex: number;
}

function loadState(): PersistedState | null {
	if (typeof window === 'undefined') return null;
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (!raw) return null;
		return JSON.parse(raw) as PersistedState;
	} catch {
		return null;
	}
}

class WindowManagerState {
	// ── Core multi-window state ──
	windows: WindowEntry[] = $state([]);
	activeWindowId: WindowId | null = $state(null);
	private _nextZIndex: number = $state(10);
	startMenuOpen: boolean = $state(false);
	startMenuSection: 'default' | 'projects' | 'history' = $state('default');
	private _breadcrumbs: Record<WindowId, BreadcrumbSegment[]> = $state({});
	private _navigation: Record<WindowId, WindowNavigation> = $state({});

	// ── Derived helpers ──
	activeWindow: WindowEntry | undefined = $derived(
		this.windows.find((w) => w.id === this.activeWindowId)
	);

	/** True when the IDE window exists and is visible (not minimized) */
	ideVisible: boolean = $derived.by(() => {
		const ide = this.windows.find((w) => w.id === 'ide');
		return !!ide && ide.state !== 'minimized';
	});

	/** True when the IDE window is registered (even if minimized) */
	ideSpawned: boolean = $derived(this.windows.some((w) => w.id === 'ide'));

	constructor() {
		const saved = loadState();
		if (saved) {
			this.windows = saved.windows;
			this.activeWindowId = saved.activeWindowId;
			this._nextZIndex = saved.nextZIndex;
		}
	}

	// ── Window lifecycle ──

	openWindow(entry: Omit<WindowEntry, 'zIndex' | 'state'> & { state?: WindowState }): WindowEntry {
		const existing = this.windows.find((w) => w.id === entry.id);
		if (existing) {
			this.focusWindow(entry.id);
			if (existing.state === 'minimized') {
				existing.state = 'maximized';
			}
			return existing;
		}

		const win: WindowEntry = {
			...entry,
			state: entry.state ?? 'maximized',
			zIndex: this._nextZIndex++,
		};
		this.windows.push(win);
		this.activeWindowId = win.id;
		this._persist();
		systemBus.emit('window:opened', 'windowManager', { id: win.id, title: win.title });
		return win;
	}

	closeWindow(id: WindowId) {
		this.windows = this.windows.filter((w) => w.id !== id);
		delete this._breadcrumbs[id];
		delete this._navigation[id];
		if (this.activeWindowId === id) {
			// Focus the next highest z-index window, or null
			const sorted = [...this.windows].sort((a, b) => b.zIndex - a.zIndex);
			this.activeWindowId = sorted[0]?.id ?? null;
		}
		this._persist();
		systemBus.emit('window:closed', 'windowManager', { id });
	}

	minimizeWindow(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (!win) return;
		win.state = 'minimized';
		// Focus the next non-minimized window
		if (this.activeWindowId === id) {
			const others = this.windows
				.filter((w) => w.id !== id && w.state !== 'minimized')
				.sort((a, b) => b.zIndex - a.zIndex);
			this.activeWindowId = others[0]?.id ?? null;
		}
		this._persist();
	}

	maximizeWindow(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (!win) return;
		win.state = 'maximized';
		this.focusWindow(id);
	}

	restoreWindow(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (!win) return;
		win.state = 'normal';
		this.focusWindow(id);
	}

	toggleWindowState(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (!win) return;
		if (win.state === 'maximized') {
			win.state = 'normal';
		} else {
			win.state = 'maximized';
		}
		this.focusWindow(id);
	}

	focusWindow(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (!win) return;
		if (win.state === 'minimized') {
			win.state = 'maximized';
		}
		win.zIndex = this._nextZIndex++;
		this.activeWindowId = id;
		this._persist();
	}

	getWindow(id: WindowId): WindowEntry | undefined {
		return this.windows.find((w) => w.id === id);
	}

	updateWindowTitle(id: WindowId, title: string) {
		const win = this.windows.find((w) => w.id === id);
		if (win) {
			win.title = title;
			this._persist();
		}
	}

	// ── Breadcrumbs ──

	setBreadcrumbs(id: WindowId, segments: BreadcrumbSegment[]) {
		this._breadcrumbs[id] = segments;
	}

	getBreadcrumbs(id: WindowId): BreadcrumbSegment[] {
		return this._breadcrumbs[id] ?? [];
	}

	// ── Navigation ──

	setNavigation(id: WindowId, nav: WindowNavigation) {
		this._navigation[id] = nav;
	}

	getNavigation(id: WindowId): WindowNavigation | undefined {
		return this._navigation[id];
	}

	clearNavigation(id: WindowId) {
		delete this._navigation[id];
	}

	// ── Start Menu ──

	toggleStartMenu() {
		this.startMenuOpen = !this.startMenuOpen;
	}

	closeStartMenu() {
		this.startMenuOpen = false;
		this.startMenuSection = 'default';
	}

	openStartMenuTo(section: 'projects' | 'history') {
		this.startMenuSection = section;
		this.startMenuOpen = true;
	}

	// ── Window Geometry ──

	moveWindow(id: WindowId, x: number, y: number) {
		const win = this.windows.find((w) => w.id === id);
		if (!win || !win.geometry) return;
		win.geometry = { ...win.geometry, x, y };
		this._persist();
	}

	resizeWindow(id: WindowId, width: number, height: number) {
		const win = this.windows.find((w) => w.id === id);
		if (!win || !win.geometry || win.resizable === false) return;
		const minW = win.minWidth ?? 200;
		const minH = win.minHeight ?? 150;
		win.geometry = {
			...win.geometry,
			width: Math.max(width, minW),
			height: Math.max(height, minH),
		};
		this._persist();
	}

	tileWindows(layout: 'left-right' | 'grid') {
		const viewportW = typeof window !== 'undefined' ? window.innerWidth : 1280;
		const viewportH = typeof window !== 'undefined' ? window.innerHeight - 40 : 680; // minus taskbar
		const visible = this.windows.filter((w) => w.state !== 'minimized');
		if (visible.length === 0) return;

		if (layout === 'left-right') {
			const tileW = Math.floor(viewportW / visible.length);
			visible.forEach((win, i) => {
				win.state = 'normal';
				win.geometry = { x: i * tileW, y: 0, width: tileW, height: viewportH };
			});
		} else {
			const cols = Math.ceil(Math.sqrt(visible.length));
			const rows = Math.ceil(visible.length / cols);
			const tileW = Math.floor(viewportW / cols);
			const tileH = Math.floor(viewportH / rows);
			visible.forEach((win, i) => {
				const col = i % cols;
				const row = Math.floor(i / cols);
				win.state = 'normal';
				win.geometry = { x: col * tileW, y: row * tileH, width: tileW, height: tileH };
			});
		}
		this._persist();
	}

	cascadeWindows() {
		const visible = this.windows.filter((w) => w.state !== 'minimized');
		visible.forEach((win, i) => {
			win.state = 'normal';
			win.geometry = {
				x: 40 + i * 30,
				y: 40 + i * 30,
				width: 700,
				height: 500,
			};
			win.zIndex = this._nextZIndex++;
		});
		if (visible.length > 0) {
			this.activeWindowId = visible[visible.length - 1].id;
		}
		this._persist();
	}

	// ── Convenience window openers ──

	openIDE() {
		this.openWindow({ id: 'ide', title: 'Forge IDE', icon: 'terminal', state: 'maximized' });
	}

	closeIDE() {
		this.closeWindow('ide');
	}

	focusDashboard() {
		this.minimizeWindow('ide');
	}

	openProjectsWindow() {
		return this.openWindow({ id: 'projects', title: 'Projects', icon: 'folder' });
	}

	openHistoryWindow() {
		return this.openWindow({ id: 'history', title: 'History', icon: 'clock' });
	}

	openControlPanel() {
		return this.openWindow({ id: 'control-panel', title: 'Control Panel', icon: 'settings' });
	}

	openTaskManager() {
		return this.openWindow({ id: 'task-manager', title: 'Task Manager', icon: 'cpu' });
	}

	openBatchProcessor() {
		return this.openWindow({ id: 'batch-processor', title: 'Batch Processor', icon: 'layers' });
	}

	openStrategyWorkshop() {
		return this.openWindow({ id: 'strategy-workshop', title: 'Strategy Workshop', icon: 'bar-chart' });
	}

	openTemplateLibrary() {
		return this.openWindow({ id: 'template-library', title: 'Template Library', icon: 'file-text' });
	}

	openTerminal() {
		return this.openWindow({ id: 'terminal', title: 'Terminal', icon: 'terminal' });
	}

	openNetworkMonitor() {
		return this.openWindow({ id: 'network-monitor', title: 'Network Monitor', icon: 'activity' });
	}

	// ── Persistence ──

	private _persist() {
		if (typeof window === 'undefined') return;
		try {
			const state: PersistedState = {
				windows: this.windows.map((w) => ({ ...w })),
				activeWindowId: this.activeWindowId,
				nextZIndex: this._nextZIndex,
			};
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
		} catch {
			// ignore
		}
	}
}

export const windowManager = new WindowManagerState();
