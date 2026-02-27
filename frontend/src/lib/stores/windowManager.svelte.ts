import { systemBus } from '$lib/services/systemBus.svelte';
import {
	type SnapZone,
	type SnapGroup,
	type SnapGroupSlot,
	type SnapSlotId,
	inferLayoutFromZone,
	getLayout,
	resolveSlotGeometry,
	resolveZoneGeometry,
	getEmptySlots,
	getViewportSize,
} from './snapLayout';

const STORAGE_KEY = 'pf_wm';
const PREFS_KEY = 'pf_window_prefs';

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
	snapGroupId?: string;
	snapSlotId?: SnapSlotId;
}

/** Windows that persist independently of routes. Minimized on active taskbar click. */
export const PERSISTENT_WINDOW_IDS = new Set([
	'ide', 'recycle-bin', 'projects', 'history',
	'control-panel', 'task-manager',
	'batch-processor', 'strategy-workshop', 'template-library', 'terminal',
	'network-monitor', 'workspace-manager', 'display-settings',
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
	snapGroups?: SnapGroup[];
}

interface WindowPrefs {
	/** Per-window geometry (last known position/size in 'normal' state) */
	geometries: Record<WindowId, WindowGeometry>;
	/** Per-window last state preference (maximized, normal, etc.) */
	states: Record<WindowId, WindowState>;
	/** Geometry snapshot taken before maximizing — used by restore */
	preMaxGeometries: Record<WindowId, WindowGeometry>;
}

const VALID_STATES = new Set<WindowState>(['normal', 'maximized', 'minimized']);

function loadPrefs(): WindowPrefs {
	if (typeof window === 'undefined') return { geometries: {}, states: {}, preMaxGeometries: {} };
	try {
		const raw = localStorage.getItem(PREFS_KEY);
		if (!raw) return { geometries: {}, states: {}, preMaxGeometries: {} };
		const parsed = JSON.parse(raw);
		return {
			geometries: parsed.geometries ?? {},
			states: parsed.states ?? {},
			preMaxGeometries: parsed.preMaxGeometries ?? {},
		};
	} catch {
		return { geometries: {}, states: {}, preMaxGeometries: {} };
	}
}

/** Validate and clamp a geometry to the current viewport. */
function clampGeometry(
	geo: unknown,
	vw: number,
	vh: number,
	minW = 200,
	minH = 150,
): WindowGeometry | null {
	if (!geo || typeof geo !== 'object') return null;
	const g = geo as Record<string, unknown>;
	const x = typeof g.x === 'number' ? g.x : NaN;
	const y = typeof g.y === 'number' ? g.y : NaN;
	const width = typeof g.width === 'number' ? g.width : NaN;
	const height = typeof g.height === 'number' ? g.height : NaN;
	if (![x, y, width, height].every(Number.isFinite)) return null;
	// Clamp dimensions to reasonable bounds
	const cw = Math.max(minW, Math.min(width, vw));
	const ch = Math.max(minH, Math.min(height, vh));
	// Clamp position so at least 50px of window is visible
	const cx = Math.max(-cw + 50, Math.min(x, vw - 50));
	const cy = Math.max(0, Math.min(y, vh - 50));
	return { x: Math.round(cx), y: Math.round(cy), width: Math.round(cw), height: Math.round(ch) };
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

	// ── Window prefs (localStorage) ──
	private _prefs: WindowPrefs = loadPrefs();

	// ── Snap state ──
	snapGroups: SnapGroup[] = $state([]);
	activeSnapZone: SnapZone | null = $state(null);
	snapAssistActive: boolean = $state(false);
	snapAssistLayoutId: string | null = $state(null);
	snapAssistFilledSlots: Record<string, string> = $state({}); // slotId → windowId
	layoutPickerWindowId: WindowId | null = $state(null);
	hoveredSnapGroupId: string | null = $state(null);

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
			if (saved.snapGroups) {
				this.snapGroups = this._pruneGroups(saved.snapGroups);
			}
		}
	}

	/** Prune snap groups that reference non-existent windows. */
	private _pruneGroups(groups: SnapGroup[]): SnapGroup[] {
		const windowIds = new Set(this.windows.map((w) => w.id));
		return groups
			.map((g) => ({
				...g,
				slots: g.slots.filter((s) => windowIds.has(s.windowId)),
			}))
			.filter((g) => g.slots.length >= 2);
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

		// Recall saved prefs (geometry + state) for this window ID
		const savedState = this._prefs.states[entry.id];
		const validSavedState = savedState && VALID_STATES.has(savedState) ? savedState : undefined;
		const savedGeo = this._prefs.geometries[entry.id];
		const { vw, vh } = getViewportSize();
		const clampedGeo = savedGeo
			? clampGeometry(savedGeo, vw, vh, entry.minWidth, entry.minHeight)
			: null;

		const win: WindowEntry = {
			...entry,
			state: entry.state ?? validSavedState ?? 'maximized',
			geometry: clampedGeo ?? entry.geometry,
			zIndex: this._nextZIndex++,
		};
		this.windows.push(win);
		this.activeWindowId = win.id;
		this._persist();
		systemBus.emit('window:opened', 'windowManager', { id: win.id, title: win.title });
		return win;
	}

	closeWindow(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (win) {
			this._saveWindowPrefs(win, true); // flush immediately — window is about to be destroyed
		}

		// Remove from snap group if present
		this._removeFromGroup(id);

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
		// Snapshot current geometry before maximizing
		if (win.state === 'normal' && win.geometry) {
			this._savePreMaxGeometry(win);
		}
		win.state = 'maximized';
		this.focusWindow(id);
	}

	restoreWindow(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (!win) return;
		win.state = 'normal';
		this._restoreGeometry(win);
		this.focusWindow(id);
	}

	toggleWindowState(id: WindowId) {
		const win = this.windows.find((w) => w.id === id);
		if (!win) return;
		if (win.state === 'maximized') {
			win.state = 'normal';
			this._restoreGeometry(win);
		} else {
			if (win.geometry) {
				this._savePreMaxGeometry(win);
			}
			win.state = 'maximized';
		}
		this.focusWindow(id);
	}

	private _ensureGeometry(win: WindowEntry): void {
		if (win.geometry) return;
		const { vw, vh } = getViewportSize();
		const w = Math.round(vw * 0.75);
		const h = Math.round(vh * 0.8);
		win.geometry = {
			x: Math.round((vw - w) / 2),
			y: Math.round((vh - h) / 2),
			width: Math.max(w, win.minWidth ?? 200),
			height: Math.max(h, win.minHeight ?? 150),
		};
	}

	/** Restore geometry with 3-tier fallback: pre-max snapshot → saved prefs → centered default. */
	private _restoreGeometry(win: WindowEntry): void {
		const { vw, vh } = getViewportSize();

		// Tier 1: Pre-maximize snapshot
		const preMax = this._prefs.preMaxGeometries[win.id];
		if (preMax) {
			const clamped = clampGeometry(preMax, vw, vh, win.minWidth, win.minHeight);
			if (clamped) {
				win.geometry = clamped;
				return;
			}
		}

		// Tier 2: Saved geometry prefs
		const saved = this._prefs.geometries[win.id];
		if (saved) {
			const clamped = clampGeometry(saved, vw, vh, win.minWidth, win.minHeight);
			if (clamped) {
				win.geometry = clamped;
				return;
			}
		}

		// Tier 3: Centered default (existing behavior)
		this._ensureGeometry(win);
	}

	/** Flush prefs to localStorage immediately. */
	private _flushPrefs(): void {
		if (typeof window === 'undefined') return;
		try {
			localStorage.setItem(PREFS_KEY, JSON.stringify(this._prefs));
		} catch {
			// ignore — localStorage quota exceeded or unavailable
		}
	}

	private _prefsTimer: ReturnType<typeof setTimeout> | null = null;

	/** Persist window prefs to localStorage (debounced for rapid move/resize events). */
	private _persistPrefs(): void {
		if (this._prefsTimer) return; // already scheduled
		this._prefsTimer = setTimeout(() => {
			this._prefsTimer = null;
			this._flushPrefs();
		}, 200);
	}

	/** Save current geometry of a window to prefs (called on close, move, resize). */
	private _saveWindowPrefs(win: WindowEntry, flush = false): void {
		if (win.geometry && win.state === 'normal') {
			this._prefs.geometries[win.id] = { ...win.geometry };
		}
		this._prefs.states[win.id] = win.state;
		if (flush) {
			if (this._prefsTimer) { clearTimeout(this._prefsTimer); this._prefsTimer = null; }
			this._flushPrefs();
		} else {
			this._persistPrefs();
		}
	}

	/** Record the pre-maximize geometry for later restore. */
	private _savePreMaxGeometry(win: WindowEntry): void {
		if (win.geometry) {
			this._prefs.preMaxGeometries[win.id] = { ...win.geometry };
			this._flushPrefs(); // immediate — pre-max must be durable before state change
		}
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
		this._saveWindowPrefs(win);
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
		this._saveWindowPrefs(win);
	}

	/** Move and resize in one call — batches persistence (used during resize-from-edge). */
	moveAndResizeWindow(id: WindowId, x: number, y: number, width: number, height: number) {
		const win = this.windows.find((w) => w.id === id);
		if (!win || !win.geometry || win.resizable === false) return;
		const minW = win.minWidth ?? 200;
		const minH = win.minHeight ?? 150;
		win.geometry = {
			x,
			y,
			width: Math.max(width, minW),
			height: Math.max(height, minH),
		};
		this._persist();
		this._saveWindowPrefs(win);
	}

	tileWindows(layout: 'left-right' | 'grid') {
		const { vw: viewportW, vh: viewportH } = getViewportSize();
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

	// ── Snap Zone API ──

	setActiveSnapZone(zone: SnapZone | null) {
		this.activeSnapZone = zone;
	}

	/**
	 * Snap a window to a zone. Sets geometry, infers layout, triggers snap assist.
	 * For 'top' zone (maximize), just maximizes — no snap group.
	 */
	snapWindowToZone(windowId: WindowId, zone: SnapZone) {
		const win = this.windows.find((w) => w.id === windowId);
		if (!win) return;

		// Save current geometry before snapping overwrites it
		if (win.state === 'normal' && win.geometry) {
			this._savePreMaxGeometry(win);
		}

		// Top zone = maximize, no snap group needed
		if (zone.id === 'top') {
			win.state = 'maximized';
			win.snapGroupId = undefined;
			win.snapSlotId = undefined;
			this.focusWindow(windowId);
			return;
		}

		// Set window to normal state with zone geometry
		win.state = 'normal';
		win.geometry = { ...zone.geometry };

		const { layoutId, slotId } = inferLayoutFromZone(zone.id);
		win.snapSlotId = slotId;

		this.focusWindow(windowId);
		this._persist();

		// Check if there are empty slots to trigger snap assist
		const layout = getLayout(layoutId);
		if (layout && layout.slots.length > 1) {
			this.startSnapAssist(layoutId, { [slotId]: windowId });
		}
	}

	/**
	 * Snap the currently active window to a zone ID (for keyboard shortcuts).
	 */
	snapActiveWindow(zoneId: SnapZone['id']) {
		if (!this.activeWindowId) return;
		const win = this.windows.find((w) => w.id === this.activeWindowId);
		if (!win) return;

		// If locked, unsnap first
		if (this.isWindowLocked(this.activeWindowId)) {
			this.unsnapWindow(this.activeWindowId);
			return;
		}

		if (zoneId === 'top') {
			this.maximizeWindow(this.activeWindowId);
			return;
		}

		const { vw, vh } = getViewportSize();
		const geometry = resolveZoneGeometry(zoneId, vw, vh);
		this.snapWindowToZone(this.activeWindowId, { id: zoneId, geometry });
	}

	/**
	 * Assign a window to a specific slot in a layout.
	 */
	assignToSlot(windowId: WindowId, layoutId: string, slotId: SnapSlotId) {
		const win = this.windows.find((w) => w.id === windowId);
		if (!win) return;

		const layout = getLayout(layoutId);
		if (!layout) return;

		const slot = layout.slots.find((s) => s.id === slotId);
		if (!slot) return;

		// Save current geometry before slot overwrites it (same pattern as snapWindowToZone)
		if (win.state === 'normal' && win.geometry) {
			this._savePreMaxGeometry(win);
		}

		const { vw, vh } = getViewportSize();
		win.state = 'normal';
		win.geometry = resolveSlotGeometry(slot, vw, vh);
		win.snapSlotId = slotId;

		this.focusWindow(windowId);
		this._persist();
	}

	// ── Snap Groups ──

	/**
	 * Create a snap group from a set of window→slot assignments.
	 * Windows get tagged with the group ID and locked.
	 */
	createSnapGroup(layoutId: string, assignments: { slotId: SnapSlotId; windowId: string }[]) {
		if (assignments.length < 2) return;

		const groupId = `snap_${Date.now()}`;
		const { vw, vh } = getViewportSize();
		const layout = getLayout(layoutId);
		if (!layout) return;

		const slots: SnapGroupSlot[] = [];

		for (const { slotId, windowId } of assignments) {
			const win = this.windows.find((w) => w.id === windowId);
			const layoutSlot = layout.slots.find((s) => s.id === slotId);
			if (!win || !layoutSlot) continue;

			const geo = resolveSlotGeometry(layoutSlot, vw, vh);
			win.state = 'normal';
			win.geometry = geo;
			win.snapGroupId = groupId;
			win.snapSlotId = slotId;

			slots.push({ slotId, windowId, geometry: geo });
		}

		if (slots.length < 2) return;

		const group: SnapGroup = {
			id: groupId,
			layoutId,
			slots,
			locked: true,
		};

		this.snapGroups.push(group);
		this._persist();
		systemBus.emit('snap:created', 'windowManager', { groupId, layoutId, windowCount: slots.length });
		for (const slot of slots) {
			systemBus.emit('snap:window_added', 'windowManager', { windowId: slot.windowId, groupId });
		}
	}

	/**
	 * Remove a window from its snap group. Dissolves group if < 2 remain.
	 * Restores window geometry via 3-tier fallback: pre-snap → saved prefs → centered default.
	 */
	unsnapWindow(windowId: WindowId) {
		const win = this.windows.find((w) => w.id === windowId);
		if (!win || !win.snapGroupId) return;

		const groupId = win.snapGroupId;
		win.snapGroupId = undefined;
		win.snapSlotId = undefined;

		// Remove slot from group
		const group = this.snapGroups.find((g) => g.id === groupId);
		if (group) {
			group.slots = group.slots.filter((s) => s.windowId !== windowId);
		}

		// Restore to saved geometry instead of always centering
		this._restoreGeometry(win);

		systemBus.emit('snap:window_removed', 'windowManager', { windowId, groupId });

		// Check if group should be dissolved
		this._checkGroupIntegrity(groupId);
		this._persist();
	}

	/**
	 * Dissolve a specific snap group. All members are unsnapped and restored.
	 */
	unsnapGroup(groupId: string) {
		const group = this.snapGroups.find((g) => g.id === groupId);
		if (!group) return;

		for (const slot of group.slots) {
			const win = this.windows.find((wn) => wn.id === slot.windowId);
			if (win) {
				win.snapGroupId = undefined;
				win.snapSlotId = undefined;
				this._restoreGeometry(win);
				systemBus.emit('snap:window_removed', 'windowManager', { windowId: slot.windowId, groupId });
			}
		}

		this.snapGroups = this.snapGroups.filter((g) => g.id !== groupId);
		systemBus.emit('snap:dissolved', 'windowManager', { groupId });
		this._persist();
	}

	/**
	 * Dissolve all snap groups.
	 */
	unsnapAll() {
		for (const group of [...this.snapGroups]) {
			for (const slot of group.slots) {
				const win = this.windows.find((w) => w.id === slot.windowId);
				if (win) {
					win.snapGroupId = undefined;
					win.snapSlotId = undefined;
					this._restoreGeometry(win);
				}
			}
			systemBus.emit('snap:dissolved', 'windowManager', { groupId: group.id });
		}
		this.snapGroups = [];
		this._persist();
	}

	/**
	 * Check if a window is in a locked snap group.
	 */
	isWindowLocked(windowId: WindowId): boolean {
		const win = this.windows.find((w) => w.id === windowId);
		if (!win?.snapGroupId) return false;
		const group = this.snapGroups.find((g) => g.id === win.snapGroupId);
		return !!group?.locked;
	}

	/**
	 * Get the snap group a window belongs to.
	 */
	getSnapGroup(windowId: WindowId): SnapGroup | undefined {
		const win = this.windows.find((w) => w.id === windowId);
		if (!win?.snapGroupId) return undefined;
		return this.snapGroups.find((g) => g.id === win.snapGroupId);
	}

	/**
	 * Get sibling window IDs in the same snap group.
	 */
	getGroupSiblings(windowId: WindowId): WindowId[] {
		const group = this.getSnapGroup(windowId);
		if (!group) return [];
		return group.slots.filter((s) => s.windowId !== windowId).map((s) => s.windowId);
	}

	/**
	 * Remove a window from its snap group (internal). Called on window close.
	 */
	private _removeFromGroup(windowId: WindowId) {
		const win = this.windows.find((w) => w.id === windowId);
		if (!win?.snapGroupId) return;

		const groupId = win.snapGroupId;
		win.snapGroupId = undefined;
		win.snapSlotId = undefined;

		// Update group slots
		const group = this.snapGroups.find((g) => g.id === groupId);
		if (group) {
			group.slots = group.slots.filter((s) => s.windowId !== windowId);
		}

		systemBus.emit('snap:window_removed', 'windowManager', { windowId, groupId });
		this._checkGroupIntegrity(groupId);
	}

	/**
	 * Check if a group still has enough members. Dissolves if < 2.
	 */
	private _checkGroupIntegrity(groupId: string) {
		const group = this.snapGroups.find((g) => g.id === groupId);
		if (!group) return;

		if (group.slots.length < 2) {
			// Untag remaining window(s)
			for (const slot of group.slots) {
				const win = this.windows.find((w) => w.id === slot.windowId);
				if (win) {
					win.snapGroupId = undefined;
					win.snapSlotId = undefined;
				}
			}
			this.snapGroups = this.snapGroups.filter((g) => g.id !== groupId);
			systemBus.emit('snap:dissolved', 'windowManager', { groupId });
		}
	}

	// ── Layout Picker ──

	openLayoutPicker(windowId: WindowId) {
		this.layoutPickerWindowId = windowId;
	}

	closeLayoutPicker() {
		this.layoutPickerWindowId = null;
	}

	// ── Snap Assist ──

	startSnapAssist(layoutId: string, filledSlots: Record<string, string>) {
		this.snapAssistActive = true;
		this.snapAssistLayoutId = layoutId;
		this.snapAssistFilledSlots = { ...filledSlots };
	}

	dismissSnapAssist() {
		this.snapAssistActive = false;
		this.snapAssistLayoutId = null;
		this.snapAssistFilledSlots = {};
	}

	/**
	 * Assign a window to a slot during snap assist.
	 * If all slots are filled, creates a snap group and ends assist.
	 */
	completeSnapAssist(slotId: SnapSlotId, windowId: WindowId) {
		if (!this.snapAssistLayoutId) return;

		const layoutId = this.snapAssistLayoutId;

		// Assign window to slot
		this.assignToSlot(windowId, layoutId, slotId);
		this.snapAssistFilledSlots[slotId] = windowId;

		// Check if all slots are filled
		const layout = getLayout(layoutId);
		if (!layout) return;

		const emptySlots = getEmptySlots(
			layoutId,
			Object.keys(this.snapAssistFilledSlots) as SnapSlotId[],
		);

		if (emptySlots.length === 0) {
			// All slots filled — create snap group
			const assignments = Object.entries(this.snapAssistFilledSlots).map(([slot, winId]) => ({
				slotId: slot as SnapSlotId,
				windowId: winId,
			}));
			this.createSnapGroup(layoutId, assignments);
			this.dismissSnapAssist();
		}
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

	openFolderWindow(folderId: string, name: string) {
		return this.openWindow({
			id: `folder-${folderId}`,
			title: name,
			icon: 'folder',
			data: { folderId },
		});
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

	openWorkspaceHub() {
		return this.openWindow({ id: 'workspace-manager', title: 'Workspace Hub', icon: 'git-branch' });
	}

	openDisplaySettings() {
		return this.openWindow({ id: 'display-settings', title: 'Display Settings', icon: 'monitor' });
	}

	// ── Persistence ──

	private _persist() {
		if (typeof window === 'undefined') return;
		try {
			const state: PersistedState = {
				windows: this.windows.map((w) => ({ ...w })),
				activeWindowId: this.activeWindowId,
				nextZIndex: this._nextZIndex,
				snapGroups: this.snapGroups.map((g) => ({ ...g, slots: g.slots.map((s) => ({ ...s })) })),
			};
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
		} catch {
			// ignore
		}
	}
}

export const windowManager = new WindowManagerState();
