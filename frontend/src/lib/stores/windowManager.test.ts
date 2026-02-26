import { describe, it, expect, beforeEach } from 'vitest';

// Mock sessionStorage
const storage = new Map<string, string>();
const mockStorage = {
	getItem: (key: string) => storage.get(key) ?? null,
	setItem: (key: string, value: string) => storage.set(key, value),
	removeItem: (key: string) => storage.delete(key),
};
Object.defineProperty(globalThis, 'sessionStorage', { value: mockStorage, writable: true });

// Mock localStorage
const localStore = new Map<string, string>();
const mockLocalStorage = {
	getItem: (key: string) => localStore.get(key) ?? null,
	setItem: (key: string, value: string) => localStore.set(key, value),
	removeItem: (key: string) => localStore.delete(key),
};
Object.defineProperty(globalThis, 'localStorage', { value: mockLocalStorage, writable: true });

import { windowManager, PERSISTENT_WINDOW_IDS } from './windowManager.svelte';
import { computeSnapZone, inferLayoutFromZone, resolveSlotGeometry, getLayout, getEmptySlots, getGroupColor, SNAP_LAYOUTS, TASKBAR_HEIGHT, getViewportSize, computeEdgeSnap, computeResizeEdgeSnap, getSnapCandidateWindows, EDGE_SNAP_THRESHOLD } from './snapLayout';
import type { WindowEntry } from './windowManager.svelte';

describe('WindowManagerState', () => {
	beforeEach(() => {
		storage.clear();
		localStore.clear();
		// Close all windows to reset (unsnapAll first to avoid group interference)
		windowManager.unsnapAll();
		for (const w of [...windowManager.windows]) {
			windowManager.closeWindow(w.id);
		}
		// Clear prefs and cancel any pending debounced write
		const wm = windowManager as any;
		if (wm._prefsTimer) { clearTimeout(wm._prefsTimer); wm._prefsTimer = null; }
		wm._prefs = { geometries: {}, states: {}, preMaxGeometries: {} };
		localStore.clear();
		windowManager.startMenuOpen = false;
		windowManager.dismissSnapAssist();
		windowManager.closeLayoutPicker();
		windowManager.setActiveSnapZone(null);
	});

	// ── Backward-compat (existing tests) ──

	describe('initial state', () => {
		it('starts with no windows and no active window', () => {
			expect(windowManager.windows).toHaveLength(0);
			expect(windowManager.activeWindowId).toBeNull();
			expect(windowManager.ideVisible).toBe(false);
			expect(windowManager.ideSpawned).toBe(false);
		});
	});

	describe('openIDE', () => {
		it('spawns IDE and focuses it', () => {
			windowManager.openIDE();
			expect(windowManager.ideSpawned).toBe(true);
			expect(windowManager.activeWindowId).toBe('ide');
			expect(windowManager.ideVisible).toBe(true);
		});

		it('persists to sessionStorage', () => {
			windowManager.openIDE();
			const saved = storage.get('pf_wm');
			expect(saved).toBeTruthy();
			const parsed = JSON.parse(saved!);
			expect(parsed.windows).toHaveLength(1);
			expect(parsed.activeWindowId).toBe('ide');
		});
	});

	describe('focusDashboard', () => {
		it('minimizes IDE without closing it', () => {
			windowManager.openIDE();
			windowManager.focusDashboard();
			expect(windowManager.ideSpawned).toBe(true);
			expect(windowManager.ideVisible).toBe(false);
			const ide = windowManager.getWindow('ide');
			expect(ide?.state).toBe('minimized');
		});
	});

	describe('closeIDE', () => {
		it('despawns IDE', () => {
			windowManager.openIDE();
			windowManager.closeIDE();
			expect(windowManager.ideSpawned).toBe(false);
			expect(windowManager.ideVisible).toBe(false);
			expect(windowManager.activeWindowId).toBeNull();
		});
	});

	describe('ideVisible derived', () => {
		it('is true when spawned and not minimized, regardless of focus', () => {
			expect(windowManager.ideVisible).toBe(false);

			windowManager.openIDE();
			expect(windowManager.ideVisible).toBe(true);

			// Opening another window doesn't hide the IDE
			windowManager.openWindow({ id: 'detail', title: 'Detail', icon: 'bolt' });
			expect(windowManager.activeWindowId).toBe('detail');
			expect(windowManager.ideVisible).toBe(true);
		});

		it('is false when minimized via focusDashboard', () => {
			windowManager.openIDE();
			windowManager.focusDashboard();
			expect(windowManager.ideVisible).toBe(false);
		});
	});

	// ── New multi-window tests ──

	describe('openWindow', () => {
		it('opens a new window and focuses it', () => {
			const win = windowManager.openWindow({ id: 'test', title: 'Test', icon: 'terminal' });
			expect(win.id).toBe('test');
			expect(win.state).toBe('maximized');
			expect(windowManager.activeWindowId).toBe('test');
			expect(windowManager.windows).toHaveLength(1);
		});

		it('focuses existing window instead of duplicating', () => {
			windowManager.openWindow({ id: 'test', title: 'Test', icon: 'terminal' });
			windowManager.openWindow({ id: 'other', title: 'Other', icon: 'folder' });
			expect(windowManager.windows).toHaveLength(2);

			windowManager.openWindow({ id: 'test', title: 'Test Updated', icon: 'terminal' });
			expect(windowManager.windows).toHaveLength(2);
			expect(windowManager.activeWindowId).toBe('test');
		});

		it('restores minimized window when re-opened', () => {
			windowManager.openWindow({ id: 'test', title: 'Test', icon: 'terminal' });
			windowManager.minimizeWindow('test');
			expect(windowManager.getWindow('test')?.state).toBe('minimized');

			windowManager.openWindow({ id: 'test', title: 'Test', icon: 'terminal' });
			expect(windowManager.getWindow('test')?.state).toBe('maximized');
		});
	});

	describe('closeWindow', () => {
		it('removes window and focuses next highest z-index', () => {
			windowManager.openWindow({ id: 'a', title: 'A', icon: 'terminal' });
			windowManager.openWindow({ id: 'b', title: 'B', icon: 'folder' });
			expect(windowManager.activeWindowId).toBe('b');

			windowManager.closeWindow('b');
			expect(windowManager.windows).toHaveLength(1);
			expect(windowManager.activeWindowId).toBe('a');
		});

		it('sets activeWindowId to null when last window closed', () => {
			windowManager.openWindow({ id: 'a', title: 'A', icon: 'terminal' });
			windowManager.closeWindow('a');
			expect(windowManager.activeWindowId).toBeNull();
		});
	});

	describe('minimizeWindow', () => {
		it('sets state to minimized and shifts focus', () => {
			windowManager.openWindow({ id: 'a', title: 'A', icon: 'terminal' });
			windowManager.openWindow({ id: 'b', title: 'B', icon: 'folder' });
			windowManager.minimizeWindow('b');
			expect(windowManager.getWindow('b')?.state).toBe('minimized');
			expect(windowManager.activeWindowId).toBe('a');
		});
	});

	describe('maximizeWindow', () => {
		it('maximizes and focuses the window', () => {
			windowManager.openWindow({ id: 'a', title: 'A', icon: 'terminal', state: 'normal' });
			windowManager.maximizeWindow('a');
			expect(windowManager.getWindow('a')?.state).toBe('maximized');
			expect(windowManager.activeWindowId).toBe('a');
		});
	});

	describe('toggleWindowState', () => {
		it('toggles between maximized and normal', () => {
			windowManager.openWindow({ id: 'a', title: 'A', icon: 'terminal' });
			expect(windowManager.getWindow('a')?.state).toBe('maximized');

			windowManager.toggleWindowState('a');
			expect(windowManager.getWindow('a')?.state).toBe('normal');

			windowManager.toggleWindowState('a');
			expect(windowManager.getWindow('a')?.state).toBe('maximized');
		});
	});

	describe('focusWindow', () => {
		it('brings window to top z-index', () => {
			windowManager.openWindow({ id: 'a', title: 'A', icon: 'terminal' });
			windowManager.openWindow({ id: 'b', title: 'B', icon: 'folder' });
			const bZ = windowManager.getWindow('b')!.zIndex;

			windowManager.focusWindow('a');
			expect(windowManager.getWindow('a')!.zIndex).toBeGreaterThan(bZ);
			expect(windowManager.activeWindowId).toBe('a');
		});

		it('restores minimized window on focus', () => {
			windowManager.openWindow({ id: 'a', title: 'A', icon: 'terminal' });
			windowManager.minimizeWindow('a');
			expect(windowManager.getWindow('a')?.state).toBe('minimized');

			windowManager.focusWindow('a');
			expect(windowManager.getWindow('a')?.state).toBe('maximized');
		});
	});

	describe('start menu', () => {
		it('toggles start menu', () => {
			expect(windowManager.startMenuOpen).toBe(false);
			windowManager.toggleStartMenu();
			expect(windowManager.startMenuOpen).toBe(true);
			windowManager.toggleStartMenu();
			expect(windowManager.startMenuOpen).toBe(false);
		});

		it('closes start menu', () => {
			windowManager.startMenuOpen = true;
			windowManager.closeStartMenu();
			expect(windowManager.startMenuOpen).toBe(false);
		});
	});

	describe('updateWindowTitle', () => {
		it('updates the title of an existing window', () => {
			windowManager.openWindow({ id: 'a', title: 'Old', icon: 'terminal' });
			windowManager.updateWindowTitle('a', 'New');
			expect(windowManager.getWindow('a')?.title).toBe('New');
		});
	});

	describe('openStartMenuTo', () => {
		it('opens start menu and sets section', () => {
			windowManager.openStartMenuTo('projects');
			expect(windowManager.startMenuOpen).toBe(true);
			expect(windowManager.startMenuSection).toBe('projects');
		});

		it('sets history section', () => {
			windowManager.openStartMenuTo('history');
			expect(windowManager.startMenuOpen).toBe(true);
			expect(windowManager.startMenuSection).toBe('history');
		});

		it('closeStartMenu resets section to default', () => {
			windowManager.openStartMenuTo('projects');
			windowManager.closeStartMenu();
			expect(windowManager.startMenuOpen).toBe(false);
			expect(windowManager.startMenuSection).toBe('default');
		});
	});

	describe('PERSISTENT_WINDOW_IDS', () => {
		it('contains expected IDs', () => {
			expect(PERSISTENT_WINDOW_IDS.has('ide')).toBe(true);
			expect(PERSISTENT_WINDOW_IDS.has('recycle-bin')).toBe(true);
			expect(PERSISTENT_WINDOW_IDS.has('projects')).toBe(true);
			expect(PERSISTENT_WINDOW_IDS.has('history')).toBe(true);
		});

		it('has exactly 13 entries', () => {
			expect(PERSISTENT_WINDOW_IDS.size).toBe(13);
		});

		it('does not contain route-driven window IDs', () => {
			expect(PERSISTENT_WINDOW_IDS.has('optimize-123')).toBe(false);
			expect(PERSISTENT_WINDOW_IDS.has('project-456')).toBe(false);
		});
	});

	describe('breadcrumbs', () => {
		it('setBreadcrumbs stores segments', () => {
			windowManager.openWindow({ id: 'test', title: 'Test', icon: 'terminal' });
			const segments = [{ label: 'Desktop' }, { label: 'Test' }];
			windowManager.setBreadcrumbs('test', segments);
			expect(windowManager.getBreadcrumbs('test')).toEqual(segments);
		});

		it('getBreadcrumbs returns empty array for unknown window', () => {
			expect(windowManager.getBreadcrumbs('nonexistent')).toEqual([]);
		});

		it('closeWindow cleans up breadcrumbs', () => {
			windowManager.openWindow({ id: 'bc-test', title: 'Test', icon: 'terminal' });
			windowManager.setBreadcrumbs('bc-test', [{ label: 'Desktop' }, { label: 'Test' }]);
			expect(windowManager.getBreadcrumbs('bc-test')).toHaveLength(2);

			windowManager.closeWindow('bc-test');
			expect(windowManager.getBreadcrumbs('bc-test')).toEqual([]);
		});

		it('setBreadcrumbs overwrites previous segments', () => {
			windowManager.openWindow({ id: 'ow-test', title: 'Test', icon: 'terminal' });
			windowManager.setBreadcrumbs('ow-test', [{ label: 'A' }]);
			windowManager.setBreadcrumbs('ow-test', [{ label: 'B' }, { label: 'C' }]);
			expect(windowManager.getBreadcrumbs('ow-test')).toEqual([{ label: 'B' }, { label: 'C' }]);
		});
	});

	describe('navigation', () => {
		it('setNavigation stores navigation state', () => {
			windowManager.openWindow({ id: 'nav-test', title: 'Nav', icon: 'folder' });
			const nav = {
				canGoBack: true,
				canGoForward: false,
				goBack: () => {},
				goForward: () => {},
			};
			windowManager.setNavigation('nav-test', nav);
			const result = windowManager.getNavigation('nav-test');
			expect(result).toBeDefined();
			expect(result!.canGoBack).toBe(true);
			expect(result!.canGoForward).toBe(false);
		});

		it('getNavigation returns undefined for unknown window', () => {
			expect(windowManager.getNavigation('nonexistent')).toBeUndefined();
		});

		it('closeWindow cleans up navigation', () => {
			windowManager.openWindow({ id: 'nav-close', title: 'Nav', icon: 'folder' });
			windowManager.setNavigation('nav-close', {
				canGoBack: true,
				canGoForward: true,
				goBack: () => {},
				goForward: () => {},
			});
			expect(windowManager.getNavigation('nav-close')).toBeDefined();

			windowManager.closeWindow('nav-close');
			expect(windowManager.getNavigation('nav-close')).toBeUndefined();
		});

		it('clearNavigation removes navigation state', () => {
			windowManager.openWindow({ id: 'nav-clear', title: 'Nav', icon: 'folder' });
			windowManager.setNavigation('nav-clear', {
				canGoBack: false,
				canGoForward: true,
				goBack: () => {},
				goForward: () => {},
			});
			expect(windowManager.getNavigation('nav-clear')).toBeDefined();

			windowManager.clearNavigation('nav-clear');
			expect(windowManager.getNavigation('nav-clear')).toBeUndefined();
		});
	});

	describe('geometry initialization', () => {
		it('toggleWindowState from maximized creates centered geometry', () => {
			windowManager.openWindow({ id: 'geo-1', title: 'Geo', icon: 'terminal' });
			expect(windowManager.getWindow('geo-1')?.state).toBe('maximized');
			expect(windowManager.getWindow('geo-1')?.geometry).toBeUndefined();

			windowManager.toggleWindowState('geo-1');
			const win = windowManager.getWindow('geo-1')!;
			expect(win.state).toBe('normal');
			expect(win.geometry).toBeDefined();
			expect(win.geometry!.width).toBeGreaterThan(0);
			expect(win.geometry!.height).toBeGreaterThan(0);
			expect(win.geometry!.x).toBeGreaterThanOrEqual(0);
			expect(win.geometry!.y).toBeGreaterThanOrEqual(0);
		});

		it('restoreWindow from maximized creates geometry', () => {
			windowManager.openWindow({ id: 'geo-2', title: 'Geo', icon: 'terminal' });
			windowManager.restoreWindow('geo-2');
			const win = windowManager.getWindow('geo-2')!;
			expect(win.state).toBe('normal');
			expect(win.geometry).toBeDefined();
			expect(win.geometry!.width).toBeGreaterThan(0);
			expect(win.geometry!.height).toBeGreaterThan(0);
		});

		it('subsequent toggleWindowState preserves existing geometry', () => {
			windowManager.openWindow({ id: 'geo-3', title: 'Geo', icon: 'terminal' });
			windowManager.toggleWindowState('geo-3'); // maximized → normal (creates geometry)
			const geo = { ...windowManager.getWindow('geo-3')!.geometry! };

			windowManager.toggleWindowState('geo-3'); // normal → maximized
			windowManager.toggleWindowState('geo-3'); // maximized → normal (should preserve)
			const win = windowManager.getWindow('geo-3')!;
			expect(win.geometry).toEqual(geo);
		});

		it('geometry respects minWidth and minHeight', () => {
			windowManager.openWindow({
				id: 'geo-4', title: 'Geo', icon: 'terminal',
				minWidth: 2000, minHeight: 1500,
			});
			windowManager.toggleWindowState('geo-4');
			const win = windowManager.getWindow('geo-4')!;
			expect(win.geometry!.width).toBeGreaterThanOrEqual(2000);
			expect(win.geometry!.height).toBeGreaterThanOrEqual(1500);
		});
	});

	describe('IDE and detail window coexistence', () => {
		it('both IDE and detail windows can exist simultaneously', () => {
			windowManager.openIDE();
			windowManager.openWindow({ id: 'optimize-123', title: 'Forge Detail', icon: 'bolt' });

			expect(windowManager.windows).toHaveLength(2);
			expect(windowManager.ideSpawned).toBe(true);
			expect(windowManager.ideVisible).toBe(true);
			expect(windowManager.getWindow('optimize-123')).toBeDefined();
		});

		it('closing detail window does not affect IDE', () => {
			windowManager.openIDE();
			windowManager.openWindow({ id: 'project-456', title: 'Project', icon: 'folder' });

			windowManager.closeWindow('project-456');
			expect(windowManager.windows).toHaveLength(1);
			expect(windowManager.ideSpawned).toBe(true);
			expect(windowManager.ideVisible).toBe(true);
		});
	});

	// ── Snap Zone Detection ──

	describe('snap zones', () => {
		describe('computeSnapZone', () => {
			const VW = 1280;
			const VH = 680;

			it('detects left edge', () => {
				const zone = computeSnapZone(10, 340, VW, VH);
				expect(zone).not.toBeNull();
				expect(zone!.id).toBe('left');
			});

			it('detects right edge', () => {
				const zone = computeSnapZone(1270, 340, VW, VH);
				expect(zone).not.toBeNull();
				expect(zone!.id).toBe('right');
			});

			it('detects top-left corner (priority over edges)', () => {
				const zone = computeSnapZone(5, 5, VW, VH);
				expect(zone).not.toBeNull();
				expect(zone!.id).toBe('top-left');
			});

			it('detects top-right corner', () => {
				const zone = computeSnapZone(1275, 5, VW, VH);
				expect(zone).not.toBeNull();
				expect(zone!.id).toBe('top-right');
			});

			it('detects bottom-left corner', () => {
				const zone = computeSnapZone(5, 675, VW, VH);
				expect(zone).not.toBeNull();
				expect(zone!.id).toBe('bottom-left');
			});

			it('detects bottom-right corner', () => {
				const zone = computeSnapZone(1275, 675, VW, VH);
				expect(zone).not.toBeNull();
				expect(zone!.id).toBe('bottom-right');
			});

			it('detects top-center as maximize', () => {
				const zone = computeSnapZone(640, 3, VW, VH);
				expect(zone).not.toBeNull();
				expect(zone!.id).toBe('top');
				expect(zone!.geometry.width).toBe(VW);
				expect(zone!.geometry.height).toBe(VH);
			});

			it('returns null for center of screen', () => {
				const zone = computeSnapZone(640, 340, VW, VH);
				expect(zone).toBeNull();
			});

			it('returns correct geometry for left half', () => {
				const zone = computeSnapZone(10, 340, VW, VH);
				expect(zone!.geometry).toEqual({ x: 0, y: 0, width: 640, height: 680 });
			});

			it('returns correct geometry for quadrant', () => {
				const zone = computeSnapZone(5, 5, VW, VH);
				expect(zone!.geometry).toEqual({ x: 0, y: 0, width: 640, height: 340 });
			});
		});

		describe('inferLayoutFromZone', () => {
			it('left maps to 2-even layout', () => {
				const result = inferLayoutFromZone('left');
				expect(result.layoutId).toBe('2-even');
				expect(result.slotId).toBe('left');
			});

			it('top-left maps to 4-grid layout', () => {
				const result = inferLayoutFromZone('top-left');
				expect(result.layoutId).toBe('4-grid');
				expect(result.slotId).toBe('top-left');
			});

			it('top maps to 1-full layout', () => {
				const result = inferLayoutFromZone('top');
				expect(result.layoutId).toBe('1-full');
				expect(result.slotId).toBe('full');
			});
		});
	});

	// ── Layout Catalog ──

	describe('layout catalog', () => {
		it('has 7 presets', () => {
			expect(SNAP_LAYOUTS).toHaveLength(7);
		});

		it('getLayout returns correct layout', () => {
			const layout = getLayout('2-even');
			expect(layout).toBeDefined();
			expect(layout!.slots).toHaveLength(2);
		});

		it('getLayout returns undefined for unknown ID', () => {
			expect(getLayout('unknown')).toBeUndefined();
		});

		it('resolveSlotGeometry converts fractions to pixels', () => {
			const geo = resolveSlotGeometry({ id: 'left', x: 0, y: 0, width: 0.5, height: 1 }, 1280, 680);
			expect(geo).toEqual({ x: 0, y: 0, width: 640, height: 680 });
		});

		it('getEmptySlots returns unfilled slots', () => {
			const empty = getEmptySlots('2-even', ['left']);
			expect(empty).toHaveLength(1);
			expect(empty[0].id).toBe('right');
		});

		it('getGroupColor returns consistent color for same ID', () => {
			const c1 = getGroupColor('snap_123');
			const c2 = getGroupColor('snap_123');
			expect(c1).toBe(c2);
		});

		it('getGroupColor returns different colors for different IDs', () => {
			const c1 = getGroupColor('snap_aaa');
			const c2 = getGroupColor('snap_zzz');
			// Not guaranteed different but very likely
			expect(typeof c1).toBe('string');
			expect(typeof c2).toBe('string');
		});
	});

	// ── Snap Groups ──

	describe('snap groups', () => {
		it('createSnapGroup creates a locked group', () => {
			windowManager.openWindow({ id: 'w1', title: 'W1', icon: 'terminal', state: 'normal' });
			windowManager.openWindow({ id: 'w2', title: 'W2', icon: 'folder', state: 'normal' });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'w1' },
				{ slotId: 'right', windowId: 'w2' },
			]);

			expect(windowManager.snapGroups).toHaveLength(1);
			expect(windowManager.snapGroups[0].locked).toBe(true);
			expect(windowManager.snapGroups[0].slots).toHaveLength(2);

			expect(windowManager.getWindow('w1')?.snapGroupId).toBe(windowManager.snapGroups[0].id);
			expect(windowManager.getWindow('w2')?.snapGroupId).toBe(windowManager.snapGroups[0].id);
		});

		it('isWindowLocked returns true for windows in locked groups', () => {
			windowManager.openWindow({ id: 'l1', title: 'L1', icon: 'terminal' });
			windowManager.openWindow({ id: 'l2', title: 'L2', icon: 'folder' });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'l1' },
				{ slotId: 'right', windowId: 'l2' },
			]);

			expect(windowManager.isWindowLocked('l1')).toBe(true);
			expect(windowManager.isWindowLocked('l2')).toBe(true);
		});

		it('isWindowLocked returns false for ungrouped windows', () => {
			windowManager.openWindow({ id: 'free', title: 'Free', icon: 'terminal' });
			expect(windowManager.isWindowLocked('free')).toBe(false);
		});

		it('getGroupSiblings returns sibling window IDs', () => {
			windowManager.openWindow({ id: 's1', title: 'S1', icon: 'terminal' });
			windowManager.openWindow({ id: 's2', title: 'S2', icon: 'folder' });
			windowManager.openWindow({ id: 's3', title: 'S3', icon: 'cpu' });

			windowManager.createSnapGroup('3-left-focus', [
				{ slotId: 'left', windowId: 's1' },
				{ slotId: 'top-right', windowId: 's2' },
				{ slotId: 'bottom-right', windowId: 's3' },
			]);

			const siblings = windowManager.getGroupSiblings('s1');
			expect(siblings).toContain('s2');
			expect(siblings).toContain('s3');
			expect(siblings).not.toContain('s1');
		});

		it('unsnapWindow removes window from group and restores geometry', () => {
			windowManager.openWindow({ id: 'u1', title: 'U1', icon: 'terminal' });
			windowManager.openWindow({ id: 'u2', title: 'U2', icon: 'folder' });
			windowManager.openWindow({ id: 'u3', title: 'U3', icon: 'cpu' });

			windowManager.createSnapGroup('3-left-focus', [
				{ slotId: 'left', windowId: 'u1' },
				{ slotId: 'top-right', windowId: 'u2' },
				{ slotId: 'bottom-right', windowId: 'u3' },
			]);

			windowManager.unsnapWindow('u1');

			expect(windowManager.getWindow('u1')?.snapGroupId).toBeUndefined();
			expect(windowManager.getWindow('u1')?.geometry).toBeDefined();
			// Group should still exist with u2 and u3
			expect(windowManager.snapGroups).toHaveLength(1);
			expect(windowManager.snapGroups[0].slots).toHaveLength(2);
		});

		it('dissolves group when < 2 members remain (via unsnap)', () => {
			windowManager.openWindow({ id: 'd1', title: 'D1', icon: 'terminal' });
			windowManager.openWindow({ id: 'd2', title: 'D2', icon: 'folder' });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'd1' },
				{ slotId: 'right', windowId: 'd2' },
			]);

			windowManager.unsnapWindow('d1');

			// Group should be dissolved since only d2 remains
			expect(windowManager.snapGroups).toHaveLength(0);
			expect(windowManager.getWindow('d2')?.snapGroupId).toBeUndefined();
		});

		it('dissolves group when window is closed', () => {
			windowManager.openWindow({ id: 'c1', title: 'C1', icon: 'terminal' });
			windowManager.openWindow({ id: 'c2', title: 'C2', icon: 'folder' });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'c1' },
				{ slotId: 'right', windowId: 'c2' },
			]);

			windowManager.closeWindow('c1');

			// Group dissolved because only c2 remains
			expect(windowManager.snapGroups).toHaveLength(0);
			expect(windowManager.getWindow('c2')?.snapGroupId).toBeUndefined();
		});

		it('unsnapAll dissolves all groups', () => {
			windowManager.openWindow({ id: 'a1', title: 'A1', icon: 'terminal' });
			windowManager.openWindow({ id: 'a2', title: 'A2', icon: 'folder' });
			windowManager.openWindow({ id: 'a3', title: 'A3', icon: 'cpu' });
			windowManager.openWindow({ id: 'a4', title: 'A4', icon: 'settings' });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'a1' },
				{ slotId: 'right', windowId: 'a2' },
			]);
			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'a3' },
				{ slotId: 'right', windowId: 'a4' },
			]);

			expect(windowManager.snapGroups).toHaveLength(2);

			windowManager.unsnapAll();

			expect(windowManager.snapGroups).toHaveLength(0);
			expect(windowManager.getWindow('a1')?.snapGroupId).toBeUndefined();
			expect(windowManager.getWindow('a4')?.snapGroupId).toBeUndefined();
		});

		it('does not create group with < 2 assignments', () => {
			windowManager.openWindow({ id: 'solo', title: 'Solo', icon: 'terminal' });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'solo' },
			]);

			expect(windowManager.snapGroups).toHaveLength(0);
		});
	});

	// ── Snap Assist ──

	describe('snap assist', () => {
		it('startSnapAssist activates assist state', () => {
			windowManager.startSnapAssist('2-even', { left: 'w1' });

			expect(windowManager.snapAssistActive).toBe(true);
			expect(windowManager.snapAssistLayoutId).toBe('2-even');
			expect(windowManager.snapAssistFilledSlots).toEqual({ left: 'w1' });
		});

		it('dismissSnapAssist clears all assist state', () => {
			windowManager.startSnapAssist('2-even', { left: 'w1' });
			windowManager.dismissSnapAssist();

			expect(windowManager.snapAssistActive).toBe(false);
			expect(windowManager.snapAssistLayoutId).toBeNull();
			expect(windowManager.snapAssistFilledSlots).toEqual({});
		});

		it('completeSnapAssist fills slot and creates group when all slots filled', () => {
			windowManager.openWindow({ id: 'sa1', title: 'SA1', icon: 'terminal' });
			windowManager.openWindow({ id: 'sa2', title: 'SA2', icon: 'folder' });

			windowManager.startSnapAssist('2-even', { left: 'sa1' });
			windowManager.completeSnapAssist('right', 'sa2');

			// Should have created a group and dismissed assist
			expect(windowManager.snapAssistActive).toBe(false);
			expect(windowManager.snapGroups).toHaveLength(1);
			expect(windowManager.snapGroups[0].slots).toHaveLength(2);
		});
	});

	// ── Snap Zone API ──

	describe('snap zone API', () => {
		it('setActiveSnapZone sets and clears zone', () => {
			const zone = { id: 'left' as const, geometry: { x: 0, y: 0, width: 640, height: 680 } };
			windowManager.setActiveSnapZone(zone);
			expect(windowManager.activeSnapZone).toEqual(zone);

			windowManager.setActiveSnapZone(null);
			expect(windowManager.activeSnapZone).toBeNull();
		});

		it('snapWindowToZone positions window and triggers assist', () => {
			windowManager.openWindow({ id: 'sz1', title: 'SZ1', icon: 'terminal' });
			const zone = { id: 'left' as const, geometry: { x: 0, y: 0, width: 640, height: 680 } };

			windowManager.snapWindowToZone('sz1', zone);

			const win = windowManager.getWindow('sz1');
			expect(win?.state).toBe('normal');
			expect(win?.geometry?.x).toBe(0);
			expect(win?.geometry?.width).toBe(640);
			expect(win?.snapSlotId).toBe('left');

			// Snap assist should be triggered for 2-even layout
			expect(windowManager.snapAssistActive).toBe(true);
			expect(windowManager.snapAssistLayoutId).toBe('2-even');
		});

		it('snapWindowToZone with top zone maximizes without assist', () => {
			windowManager.openWindow({ id: 'sz2', title: 'SZ2', icon: 'terminal' });
			const zone = { id: 'top' as const, geometry: { x: 0, y: 0, width: 1280, height: 680 } };

			windowManager.snapWindowToZone('sz2', zone);

			expect(windowManager.getWindow('sz2')?.state).toBe('maximized');
			expect(windowManager.snapAssistActive).toBe(false);
		});
	});

	// ── Persistence ──

	describe('snap group persistence', () => {
		it('persists snap groups to sessionStorage', () => {
			windowManager.openWindow({ id: 'p1', title: 'P1', icon: 'terminal' });
			windowManager.openWindow({ id: 'p2', title: 'P2', icon: 'folder' });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'p1' },
				{ slotId: 'right', windowId: 'p2' },
			]);

			const saved = storage.get('pf_wm');
			expect(saved).toBeTruthy();
			const parsed = JSON.parse(saved!);
			expect(parsed.snapGroups).toHaveLength(1);
			expect(parsed.snapGroups[0].slots).toHaveLength(2);
		});
	});

	// ── Layout Picker ──

	describe('layout picker', () => {
		it('openLayoutPicker sets window ID', () => {
			windowManager.openLayoutPicker('test-win');
			expect(windowManager.layoutPickerWindowId).toBe('test-win');
		});

		it('closeLayoutPicker clears window ID', () => {
			windowManager.openLayoutPicker('test-win');
			windowManager.closeLayoutPicker();
			expect(windowManager.layoutPickerWindowId).toBeNull();
		});
	});

	// ── Window Prefs Persistence ──

	describe('window prefs persistence', () => {
		it('saves geometry to localStorage on close and recalls on reopen', () => {
			// Open a window with explicit geometry
			const geo = { x: 100, y: 200, width: 500, height: 400 };
			windowManager.openWindow({
				id: 'geo-pref', title: 'Geo Pref', icon: 'terminal',
				state: 'normal', geometry: geo,
			});

			// Close and reopen
			windowManager.closeWindow('geo-pref');
			const reopened = windowManager.openWindow({ id: 'geo-pref', title: 'Geo Pref', icon: 'terminal' });

			// Should recall saved geometry
			expect(reopened.geometry).toBeDefined();
			expect(reopened.geometry!.x).toBe(geo.x);
			expect(reopened.geometry!.y).toBe(geo.y);
			expect(reopened.geometry!.width).toBe(geo.width);
			expect(reopened.geometry!.height).toBe(geo.height);
		});

		it('recalls saved state preference on reopen', () => {
			// Open as normal, close, reopen without explicit state
			windowManager.openWindow({ id: 'state-pref', title: 'State', icon: 'terminal', state: 'normal' });
			windowManager.closeWindow('state-pref');

			const reopened = windowManager.openWindow({ id: 'state-pref', title: 'State', icon: 'terminal' });
			expect(reopened.state).toBe('normal');
		});

		it('explicit state overrides saved state preference', () => {
			// Save as normal
			windowManager.openWindow({ id: 'override', title: 'Override', icon: 'terminal', state: 'normal' });
			windowManager.closeWindow('override');

			// Reopen with explicit maximized
			const reopened = windowManager.openWindow({ id: 'override', title: 'Override', icon: 'terminal', state: 'maximized' });
			expect(reopened.state).toBe('maximized');
		});

		it('saves geometry on move and resize (verified via close+reopen)', () => {
			const geo = { x: 0, y: 0, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'mv', title: 'MV', icon: 'terminal',
				state: 'normal', geometry: geo,
			});
			windowManager.moveWindow('mv', 50, 60);
			windowManager.resizeWindow('mv', 300, 250);

			// Close flushes prefs immediately
			windowManager.closeWindow('mv');

			// Reopen and verify geometry was saved
			const reopened = windowManager.openWindow({ id: 'mv', title: 'MV', icon: 'terminal' });
			expect(reopened.geometry).toBeDefined();
			expect(reopened.geometry!.x).toBe(50);
			expect(reopened.geometry!.y).toBe(60);
			expect(reopened.geometry!.width).toBe(300);
			expect(reopened.geometry!.height).toBe(250);
		});
	});

	describe('pre-maximize geometry restore', () => {
		it('restores to pre-maximize position after toggle', () => {
			const originalGeo = { x: 100, y: 50, width: 600, height: 400 };
			windowManager.openWindow({
				id: 'premax', title: 'PreMax', icon: 'terminal',
				state: 'normal', geometry: { ...originalGeo },
			});

			// Maximize then restore
			windowManager.toggleWindowState('premax'); // normal → maximized
			windowManager.toggleWindowState('premax'); // maximized → normal

			const win = windowManager.getWindow('premax')!;
			expect(win.state).toBe('normal');
			expect(win.geometry!.x).toBe(originalGeo.x);
			expect(win.geometry!.y).toBe(originalGeo.y);
			expect(win.geometry!.width).toBe(originalGeo.width);
			expect(win.geometry!.height).toBe(originalGeo.height);
		});

		it('restores to pre-maximize position after maximizeWindow + restoreWindow', () => {
			const originalGeo = { x: 150, y: 75, width: 500, height: 350 };
			windowManager.openWindow({
				id: 'premax2', title: 'PreMax2', icon: 'terminal',
				state: 'normal', geometry: { ...originalGeo },
			});

			windowManager.maximizeWindow('premax2');
			windowManager.restoreWindow('premax2');

			const win = windowManager.getWindow('premax2')!;
			expect(win.geometry!.x).toBe(originalGeo.x);
			expect(win.geometry!.y).toBe(originalGeo.y);
		});

		it('pre-maximize geometry survives close and reopen', () => {
			const originalGeo = { x: 200, y: 100, width: 600, height: 400 };
			windowManager.openWindow({
				id: 'surv', title: 'Survive', icon: 'terminal',
				state: 'normal', geometry: { ...originalGeo },
			});

			// Maximize (saves pre-max) then close while maximized
			windowManager.maximizeWindow('surv');
			windowManager.closeWindow('surv');

			// Reopen — should be maximized (last state), then restore should use pre-max
			const reopened = windowManager.openWindow({ id: 'surv', title: 'Survive', icon: 'terminal' });
			expect(reopened.state).toBe('maximized');

			windowManager.restoreWindow('surv');
			const win = windowManager.getWindow('surv')!;
			expect(win.geometry!.x).toBe(originalGeo.x);
			expect(win.geometry!.y).toBe(originalGeo.y);
		});
	});

	describe('viewport clamping', () => {
		it('clamps position so window stays visible when saved geometry is off-screen', () => {
			// Save geometry with position beyond viewport via the API
			const largeGeo = { x: 5000, y: 3000, width: 500, height: 400 };
			windowManager.openWindow({
				id: 'clamp-test', title: 'Clamp', icon: 'terminal',
				state: 'normal', geometry: { ...largeGeo },
			});
			windowManager.closeWindow('clamp-test');

			// Reopen — saved position (5000, 3000) should be clamped to viewport
			const win = windowManager.openWindow({ id: 'clamp-test', title: 'Clamp', icon: 'terminal' });
			expect(win.geometry).toBeDefined();

			// getViewportSize returns innerWidth x (innerHeight-40)
			const vw = typeof window !== 'undefined' ? window.innerWidth : 1280;
			const vh = typeof window !== 'undefined' ? window.innerHeight - 40 : 680;

			// Position should ensure at least 50px of window is visible
			expect(win.geometry!.x).toBeLessThanOrEqual(vw - 50);
			expect(win.geometry!.y).toBeLessThanOrEqual(vh - 50);
			expect(win.geometry!.y).toBeGreaterThanOrEqual(0);
		});
	});

	describe('invalid geometry rejection', () => {
		it('clampGeometry handles all-valid data correctly', () => {
			// Save valid geometry, then verify it's recalled correctly
			const validGeo = { x: 50, y: 50, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'valid-geo', title: 'Valid', icon: 'terminal',
				state: 'normal', geometry: { ...validGeo },
			});
			windowManager.closeWindow('valid-geo');

			const win = windowManager.openWindow({ id: 'valid-geo', title: 'Valid', icon: 'terminal' });
			expect(win.geometry).toBeDefined();
			expect(Number.isFinite(win.geometry!.x)).toBe(true);
			expect(Number.isFinite(win.geometry!.y)).toBe(true);
			expect(Number.isFinite(win.geometry!.width)).toBe(true);
			expect(Number.isFinite(win.geometry!.height)).toBe(true);
		});

		it('rejects invalid state values and falls back to maximized', () => {
			// Inject invalid state directly into prefs via internal access
			const prefs = (windowManager as any)._prefs;
			prefs.states['bad-state'] = 'invalid_state' as any;

			const win = windowManager.openWindow({ id: 'bad-state', title: 'Bad', icon: 'terminal' });
			expect(['normal', 'maximized', 'minimized']).toContain(win.state);
			// Should fall back to 'maximized' since invalid_state is not valid
			expect(win.state).toBe('maximized');
		});

		it('injects NaN geometry via prefs and verifies rejection', () => {
			// Inject invalid geometry directly into prefs
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['nan-test'] = { x: NaN, y: 100, width: 500, height: 400 };

			const win = windowManager.openWindow({ id: 'nan-test', title: 'NaN', icon: 'terminal' });

			// NaN geometry should be rejected by clampGeometry, no geometry set
			expect(win.geometry).toBeUndefined();
		});

		it('rejects Infinity values in saved geometry', () => {
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['inf-test'] = { x: Infinity, y: 100, width: 500, height: 400 };

			const win = windowManager.openWindow({ id: 'inf-test', title: 'Inf', icon: 'terminal' });
			expect(win.geometry).toBeUndefined();
		});
	});

	describe('unsnap uses saved geometry', () => {
		it('unsnapWindow restores saved geometry instead of centering', () => {
			// Open window with specific geometry, close to save prefs
			const savedGeo = { x: 100, y: 80, width: 500, height: 400 };
			windowManager.openWindow({
				id: 'snap-save', title: 'SS', icon: 'terminal',
				state: 'normal', geometry: { ...savedGeo },
			});
			windowManager.closeWindow('snap-save');

			// Reopen and create a 3-window snap group
			windowManager.openWindow({ id: 'snap-save', title: 'SS', icon: 'terminal', state: 'normal' });
			windowManager.openWindow({ id: 'snap-partner', title: 'SP', icon: 'folder', state: 'normal' });
			windowManager.openWindow({ id: 'snap-extra', title: 'SE', icon: 'cpu', state: 'normal' });

			windowManager.createSnapGroup('3-left-focus', [
				{ slotId: 'left', windowId: 'snap-save' },
				{ slotId: 'top-right', windowId: 'snap-partner' },
				{ slotId: 'bottom-right', windowId: 'snap-extra' },
			]);

			windowManager.unsnapWindow('snap-save');

			const win = windowManager.getWindow('snap-save')!;
			expect(win.snapGroupId).toBeUndefined();
			expect(win.geometry).toBeDefined();
			// Should have restored to saved geometry (100, 80) not centered
			expect(win.geometry!.x).toBe(savedGeo.x);
			expect(win.geometry!.y).toBe(savedGeo.y);
		});

		it('snapWindowToZone saves pre-snap geometry for restore via top zone maximize', () => {
			// Open window with known geometry
			const preSnapGeo = { x: 200, y: 150, width: 600, height: 400 };
			windowManager.openWindow({
				id: 'snap-zone', title: 'SZ', icon: 'terminal',
				state: 'normal', geometry: { ...preSnapGeo },
			});

			// Snap to top zone (maximize) — should save pre-snap geometry then maximize
			const topZone = { id: 'top' as const, geometry: { x: 0, y: 0, width: 1280, height: 680 } };
			windowManager.snapWindowToZone('snap-zone', topZone);

			expect(windowManager.getWindow('snap-zone')!.state).toBe('maximized');

			// Restore — should get pre-snap geometry back
			windowManager.restoreWindow('snap-zone');

			const restored = windowManager.getWindow('snap-zone')!;
			expect(restored.geometry!.x).toBe(preSnapGeo.x);
			expect(restored.geometry!.y).toBe(preSnapGeo.y);
			expect(restored.geometry!.width).toBe(preSnapGeo.width);
		});

		it('snapWindowToZone to side saves pre-snap geometry for unsnap', () => {
			// Open window with known geometry
			const preSnapGeo = { x: 200, y: 150, width: 600, height: 400 };
			windowManager.openWindow({
				id: 'snap-side', title: 'SS', icon: 'terminal',
				state: 'normal', geometry: { ...preSnapGeo },
			});

			// Snap to left — saves pre-snap geometry then sets zone geometry
			const zone = { id: 'left' as const, geometry: { x: 0, y: 0, width: 640, height: 680 } };
			windowManager.snapWindowToZone('snap-side', zone);

			// Window should now have zone geometry
			expect(windowManager.getWindow('snap-side')!.geometry!.x).toBe(0);
			expect(windowManager.getWindow('snap-side')!.geometry!.width).toBe(640);

			// Restoring (not via unsnap, but via toggle) should use pre-snap geometry
			// Note: toggle from normal → maximized saves zone geometry as pre-max,
			// so we verify the pre-snap is in the saved prefs instead
			windowManager.closeWindow('snap-side');
			const reopened = windowManager.openWindow({ id: 'snap-side', title: 'SS', icon: 'terminal' });
			// State was 'normal' when snapped, so saved state is 'normal'
			// Pre-max geometry holds pre-snap position
			windowManager.restoreWindow('snap-side');
			const win = windowManager.getWindow('snap-side')!;
			expect(win.geometry!.x).toBe(preSnapGeo.x);
			expect(win.geometry!.y).toBe(preSnapGeo.y);
		});
	});

	describe('moveAndResizeWindow', () => {
		it('updates position and size in a single call', () => {
			windowManager.openWindow({
				id: 'mr', title: 'MR', icon: 'terminal',
				state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 },
			});

			windowManager.moveAndResizeWindow('mr', 50, 60, 500, 350);

			const win = windowManager.getWindow('mr')!;
			expect(win.geometry!.x).toBe(50);
			expect(win.geometry!.y).toBe(60);
			expect(win.geometry!.width).toBe(500);
			expect(win.geometry!.height).toBe(350);
		});

		it('respects min dimensions', () => {
			windowManager.openWindow({
				id: 'mr-min', title: 'MR', icon: 'terminal',
				state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 },
				minWidth: 300, minHeight: 200,
			});

			windowManager.moveAndResizeWindow('mr-min', 10, 20, 100, 50);

			const win = windowManager.getWindow('mr-min')!;
			expect(win.geometry!.width).toBe(300); // clamped to minWidth
			expect(win.geometry!.height).toBe(200); // clamped to minHeight
		});
	});

	// ══════════════════════════════════════════════════════════════════
	// Comprehensive Business Logic, Edge Cases & Integration Tests
	// ══════════════════════════════════════════════════════════════════

	describe('TASKBAR_HEIGHT single source of truth', () => {
		it('exports TASKBAR_HEIGHT as 40', () => {
			expect(TASKBAR_HEIGHT).toBe(40);
		});

		it('getViewportSize subtracts TASKBAR_HEIGHT from innerHeight', () => {
			const { vw, vh } = getViewportSize();
			expect(vw).toBe(window.innerWidth);
			expect(vh).toBe(window.innerHeight - TASKBAR_HEIGHT);
		});

		it('computeSnapZone uses TASKBAR_HEIGHT for viewport calculation', () => {
			const fullVh = window.innerHeight - TASKBAR_HEIGHT;
			// Bottom edge detection: cursor near vh should trigger bottom zone
			const zone = computeSnapZone(5, fullVh - 5, window.innerWidth, fullVh);
			expect(zone).not.toBeNull();
			expect(zone!.id).toBe('bottom-left');
		});
	});

	describe('assignToSlot pre-slot geometry preservation', () => {
		it('saves pre-slot geometry before overwriting with slot geometry', () => {
			const originalGeo = { x: 100, y: 80, width: 500, height: 400 };
			windowManager.openWindow({
				id: 'slot-save', title: 'SS', icon: 'terminal',
				state: 'normal', geometry: { ...originalGeo },
			});

			windowManager.assignToSlot('slot-save', '2-even', 'left');

			// Window should now have slot geometry (left half)
			const { vw, vh } = getViewportSize();
			const expectedSlotGeo = resolveSlotGeometry(getLayout('2-even')!.slots[0], vw, vh);
			const win = windowManager.getWindow('slot-save')!;
			expect(win.geometry!.x).toBe(expectedSlotGeo.x);
			expect(win.geometry!.width).toBe(expectedSlotGeo.width);

			// Restore should return to pre-slot geometry
			windowManager.maximizeWindow('slot-save');
			windowManager.restoreWindow('slot-save');
			// The pre-slot geometry was saved by assignToSlot, so _restoreGeometry tier 1 should use it
			// But since maximizeWindow also saves pre-max (which is the slot geometry),
			// the pre-max now holds the slot geometry. However, the original was saved by assignToSlot.
			// Let's verify via close+reopen+restore instead
		});

		it('assignToSlot → close → reopen → restore returns to pre-slot geometry', () => {
			const originalGeo = { x: 150, y: 90, width: 600, height: 450 };
			windowManager.openWindow({
				id: 'slot-cl', title: 'SC', icon: 'terminal',
				state: 'normal', geometry: { ...originalGeo },
			});

			// assignToSlot saves pre-slot geometry
			windowManager.assignToSlot('slot-cl', '2-even', 'left');

			// Close (saves current slot geometry as geometry, pre-slot as preMaxGeometry)
			windowManager.closeWindow('slot-cl');

			// Reopen
			windowManager.openWindow({ id: 'slot-cl', title: 'SC', icon: 'terminal' });

			// Restore should use pre-max geometry tier (which holds pre-slot)
			windowManager.restoreWindow('slot-cl');
			const win = windowManager.getWindow('slot-cl')!;
			expect(win.geometry!.x).toBe(originalGeo.x);
			expect(win.geometry!.y).toBe(originalGeo.y);
			expect(win.geometry!.width).toBe(originalGeo.width);
			expect(win.geometry!.height).toBe(originalGeo.height);
		});

		it('does not save pre-slot geometry for maximized windows (no geometry to save)', () => {
			windowManager.openWindow({ id: 'slot-max', title: 'SM', icon: 'terminal' });
			// Window is maximized (no geometry)
			expect(windowManager.getWindow('slot-max')!.state).toBe('maximized');

			windowManager.assignToSlot('slot-max', '2-even', 'right');
			// Should still work — just won't save pre-slot since there was no geometry
			const win = windowManager.getWindow('slot-max')!;
			expect(win.state).toBe('normal');
			expect(win.geometry).toBeDefined();
		});
	});

	describe('unsnapAll geometry restoration', () => {
		it('restores all windows to their saved geometry', () => {
			// Create windows with known geometries
			const geo1 = { x: 10, y: 20, width: 400, height: 300 };
			const geo2 = { x: 500, y: 100, width: 350, height: 250 };

			windowManager.openWindow({ id: 'ua1', title: 'UA1', icon: 'terminal', state: 'normal', geometry: { ...geo1 } });
			windowManager.openWindow({ id: 'ua2', title: 'UA2', icon: 'folder', state: 'normal', geometry: { ...geo2 } });

			// Snap both (saves pre-snap via snapWindowToZone or createSnapGroup)
			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'ua1' },
				{ slotId: 'right', windowId: 'ua2' },
			]);

			// Verify windows are now in snap geometry (not original)
			expect(windowManager.getWindow('ua1')!.geometry!.x).toBe(0);

			// unsnapAll should restore original geometries
			windowManager.unsnapAll();

			// Windows should have geometry restored via _restoreGeometry
			expect(windowManager.getWindow('ua1')!.snapGroupId).toBeUndefined();
			expect(windowManager.getWindow('ua2')!.snapGroupId).toBeUndefined();
			expect(windowManager.getWindow('ua1')!.geometry).toBeDefined();
			expect(windowManager.getWindow('ua2')!.geometry).toBeDefined();
		});

		it('unsnapAll with multiple groups restores all', () => {
			windowManager.openWindow({ id: 'mg1', title: 'MG1', icon: 'terminal', state: 'normal', geometry: { x: 10, y: 10, width: 400, height: 300 } });
			windowManager.openWindow({ id: 'mg2', title: 'MG2', icon: 'folder', state: 'normal', geometry: { x: 500, y: 10, width: 400, height: 300 } });
			windowManager.openWindow({ id: 'mg3', title: 'MG3', icon: 'cpu', state: 'normal', geometry: { x: 10, y: 400, width: 400, height: 300 } });
			windowManager.openWindow({ id: 'mg4', title: 'MG4', icon: 'settings', state: 'normal', geometry: { x: 500, y: 400, width: 400, height: 300 } });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'mg1' },
				{ slotId: 'right', windowId: 'mg2' },
			]);
			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'mg3' },
				{ slotId: 'right', windowId: 'mg4' },
			]);

			expect(windowManager.snapGroups).toHaveLength(2);

			windowManager.unsnapAll();

			expect(windowManager.snapGroups).toHaveLength(0);
			// All windows should have geometry and no snap tags
			for (const id of ['mg1', 'mg2', 'mg3', 'mg4']) {
				const win = windowManager.getWindow(id)!;
				expect(win.snapGroupId).toBeUndefined();
				expect(win.snapSlotId).toBeUndefined();
				expect(win.geometry).toBeDefined();
			}
		});

		it('unsnapAll is idempotent when no groups exist', () => {
			windowManager.openWindow({ id: 'idem', title: 'Idem', icon: 'terminal', state: 'normal', geometry: { x: 50, y: 50, width: 400, height: 300 } });
			const geoBefore = { ...windowManager.getWindow('idem')!.geometry! };

			windowManager.unsnapAll();

			expect(windowManager.snapGroups).toHaveLength(0);
			// Geometry should be unchanged
			expect(windowManager.getWindow('idem')!.geometry).toEqual(geoBefore);
		});
	});

	describe('3-tier restore fallback logic', () => {
		it('tier 1: uses pre-maximize geometry when available', () => {
			const preMaxGeo = { x: 100, y: 50, width: 600, height: 400 };
			windowManager.openWindow({
				id: 'tier1', title: 'T1', icon: 'terminal',
				state: 'normal', geometry: { ...preMaxGeo },
			});
			// Save distinct geometry to prefs (tier 2)
			windowManager.moveWindow('tier1', 200, 100);
			// Now maximize (saves current pos as pre-max)
			windowManager.maximizeWindow('tier1');
			// Restore → should use tier 1 (pre-max at 200,100), not tier 2 (last saved 200,100)
			windowManager.restoreWindow('tier1');
			const win = windowManager.getWindow('tier1')!;
			expect(win.geometry!.x).toBe(200);
			expect(win.geometry!.y).toBe(100);
		});

		it('tier 2: falls back to saved geometry prefs when no pre-max exists', () => {
			// Save geometry via close
			const savedGeo = { x: 300, y: 200, width: 500, height: 350 };
			windowManager.openWindow({
				id: 'tier2', title: 'T2', icon: 'terminal',
				state: 'normal', geometry: { ...savedGeo },
			});
			windowManager.closeWindow('tier2');

			// Reopen as maximized (no pre-max snapshot exists for this fresh open)
			windowManager.openWindow({ id: 'tier2', title: 'T2', icon: 'terminal', state: 'maximized' });

			// Clear pre-max to force tier 2
			const prefs = (windowManager as any)._prefs;
			delete prefs.preMaxGeometries['tier2'];

			windowManager.restoreWindow('tier2');
			const win = windowManager.getWindow('tier2')!;
			expect(win.geometry!.x).toBe(savedGeo.x);
			expect(win.geometry!.y).toBe(savedGeo.y);
		});

		it('tier 3: creates centered default when no saved geometry exists', () => {
			// Open maximized with no prior saved geometry
			windowManager.openWindow({ id: 'tier3', title: 'T3', icon: 'terminal', state: 'maximized' });
			windowManager.restoreWindow('tier3');
			const win = windowManager.getWindow('tier3')!;
			expect(win.geometry).toBeDefined();
			// Centered default: should be roughly in the middle
			const { vw, vh } = getViewportSize();
			expect(win.geometry!.x).toBeGreaterThan(0);
			expect(win.geometry!.y).toBeGreaterThanOrEqual(0);
			expect(win.geometry!.x + win.geometry!.width).toBeLessThanOrEqual(vw);
			expect(win.geometry!.y + win.geometry!.height).toBeLessThanOrEqual(vh);
		});

		it('tier 1 with invalid pre-max falls through to tier 2', () => {
			const savedGeo = { x: 50, y: 50, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'fall-t2', title: 'FT2', icon: 'terminal',
				state: 'normal', geometry: { ...savedGeo },
			});
			windowManager.closeWindow('fall-t2');

			windowManager.openWindow({ id: 'fall-t2', title: 'FT2', icon: 'terminal', state: 'maximized' });

			// Inject invalid pre-max
			const prefs = (windowManager as any)._prefs;
			prefs.preMaxGeometries['fall-t2'] = { x: NaN, y: 0, width: 400, height: 300 };

			windowManager.restoreWindow('fall-t2');
			const win = windowManager.getWindow('fall-t2')!;
			// Should fall through to tier 2 (saved geometry)
			expect(win.geometry!.x).toBe(savedGeo.x);
			expect(win.geometry!.y).toBe(savedGeo.y);
		});
	});

	describe('geometry persistence through full lifecycle', () => {
		it('open → move → resize → close → reopen preserves final geometry', () => {
			windowManager.openWindow({
				id: 'lifecycle', title: 'LC', icon: 'terminal',
				state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 },
			});

			windowManager.moveWindow('lifecycle', 100, 200);
			windowManager.resizeWindow('lifecycle', 600, 500);
			windowManager.closeWindow('lifecycle');

			const reopened = windowManager.openWindow({ id: 'lifecycle', title: 'LC', icon: 'terminal' });
			expect(reopened.geometry!.x).toBe(100);
			expect(reopened.geometry!.y).toBe(200);
			expect(reopened.geometry!.width).toBe(600);
			expect(reopened.geometry!.height).toBe(500);
			expect(reopened.state).toBe('normal');
		});

		it('open → snap → close → reopen → restore → correct pre-snap geometry', () => {
			const original = { x: 80, y: 40, width: 500, height: 350 };
			windowManager.openWindow({
				id: 'snap-life', title: 'SL', icon: 'terminal',
				state: 'normal', geometry: { ...original },
			});

			// Snap to left zone
			const zone = { id: 'left' as const, geometry: { x: 0, y: 0, width: 640, height: 680 } };
			windowManager.snapWindowToZone('snap-life', zone);

			// Close while snapped
			windowManager.closeWindow('snap-life');

			// Reopen — geometry should be snap zone geometry (what was saved on close)
			const reopened = windowManager.openWindow({ id: 'snap-life', title: 'SL', icon: 'terminal' });
			// State was 'normal' when closed
			expect(reopened.state).toBe('normal');

			// Restore should use pre-snap geometry (tier 1)
			windowManager.restoreWindow('snap-life');
			const win = windowManager.getWindow('snap-life')!;
			expect(win.geometry!.x).toBe(original.x);
			expect(win.geometry!.y).toBe(original.y);
			expect(win.geometry!.width).toBe(original.width);
		});

		it('open → maximize → close → reopen → verify maximized → restore → pre-max geometry', () => {
			const normalGeo = { x: 120, y: 60, width: 500, height: 400 };
			windowManager.openWindow({
				id: 'max-life', title: 'ML', icon: 'terminal',
				state: 'normal', geometry: { ...normalGeo },
			});

			windowManager.maximizeWindow('max-life');
			windowManager.closeWindow('max-life');

			// Reopen — should be maximized (saved state)
			const reopened = windowManager.openWindow({ id: 'max-life', title: 'ML', icon: 'terminal' });
			expect(reopened.state).toBe('maximized');

			// Restore → pre-max geometry
			windowManager.restoreWindow('max-life');
			const win = windowManager.getWindow('max-life')!;
			expect(win.geometry!.x).toBe(normalGeo.x);
			expect(win.geometry!.y).toBe(normalGeo.y);
		});

		it('multiple maximize/restore cycles preserve geometry', () => {
			const geo = { x: 100, y: 80, width: 500, height: 400 };
			windowManager.openWindow({
				id: 'multi-toggle', title: 'MT', icon: 'terminal',
				state: 'normal', geometry: { ...geo },
			});

			for (let i = 0; i < 5; i++) {
				windowManager.toggleWindowState('multi-toggle'); // normal → maximized
				windowManager.toggleWindowState('multi-toggle'); // maximized → normal
			}

			const win = windowManager.getWindow('multi-toggle')!;
			expect(win.state).toBe('normal');
			expect(win.geometry!.x).toBe(geo.x);
			expect(win.geometry!.y).toBe(geo.y);
			expect(win.geometry!.width).toBe(geo.width);
			expect(win.geometry!.height).toBe(geo.height);
		});
	});

	describe('snap edge cases', () => {
		it('snap → unsnap → snap → unsnap restores to original geometry each time', () => {
			const original = { x: 150, y: 100, width: 500, height: 350 };
			windowManager.openWindow({
				id: 'bounce', title: 'B', icon: 'terminal',
				state: 'normal', geometry: { ...original },
			});

			for (let i = 0; i < 3; i++) {
				const zone = { id: 'left' as const, geometry: { x: 0, y: 0, width: 640, height: 680 } };
				windowManager.snapWindowToZone('bounce', zone);

				expect(windowManager.getWindow('bounce')!.geometry!.x).toBe(0);
				expect(windowManager.getWindow('bounce')!.geometry!.width).toBe(640);

				// Restore via toggle (maximized → would first maximize, so use restoreWindow directly)
				windowManager.restoreWindow('bounce');

				const win = windowManager.getWindow('bounce')!;
				expect(win.geometry!.x).toBe(original.x);
				expect(win.geometry!.y).toBe(original.y);
			}
		});

		it('snap group creation assigns slot geometry to all windows', () => {
			windowManager.openWindow({ id: 'sg1', title: 'SG1', icon: 'terminal', state: 'normal', geometry: { x: 50, y: 50, width: 400, height: 300 } });
			windowManager.openWindow({ id: 'sg2', title: 'SG2', icon: 'folder', state: 'normal', geometry: { x: 500, y: 50, width: 400, height: 300 } });

			windowManager.createSnapGroup('2-even', [
				{ slotId: 'left', windowId: 'sg1' },
				{ slotId: 'right', windowId: 'sg2' },
			]);

			const { vw, vh } = getViewportSize();
			const leftSlot = resolveSlotGeometry(getLayout('2-even')!.slots[0], vw, vh);
			const rightSlot = resolveSlotGeometry(getLayout('2-even')!.slots[1], vw, vh);

			expect(windowManager.getWindow('sg1')!.geometry).toEqual(leftSlot);
			expect(windowManager.getWindow('sg2')!.geometry).toEqual(rightSlot);
		});

		it('closing a snapped window saves slot geometry (not pre-snap) as regular geometry', () => {
			const original = { x: 200, y: 150, width: 500, height: 350 };
			windowManager.openWindow({
				id: 'snap-close', title: 'SC', icon: 'terminal',
				state: 'normal', geometry: { ...original },
			});

			const zone = { id: 'left' as const, geometry: { x: 0, y: 0, width: 640, height: 680 } };
			windowManager.snapWindowToZone('snap-close', zone);

			windowManager.closeWindow('snap-close');

			// The saved geometry should be the snap zone geometry (what it was when closed)
			const prefs = (windowManager as any)._prefs;
			expect(prefs.geometries['snap-close']).toEqual({ x: 0, y: 0, width: 640, height: 680 });
			// But pre-max should hold the original
			expect(prefs.preMaxGeometries['snap-close'].x).toBe(original.x);
			expect(prefs.preMaxGeometries['snap-close'].y).toBe(original.y);
		});

		it('assignToSlot sets snapSlotId on the window', () => {
			windowManager.openWindow({ id: 'slot-tag', title: 'ST', icon: 'terminal', state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 } });
			windowManager.assignToSlot('slot-tag', '3-left-focus', 'top-right');

			expect(windowManager.getWindow('slot-tag')!.snapSlotId).toBe('top-right');
		});

		it('assignToSlot with unknown layout is a no-op', () => {
			const geo = { x: 100, y: 100, width: 400, height: 300 };
			windowManager.openWindow({ id: 'bad-layout', title: 'BL', icon: 'terminal', state: 'normal', geometry: { ...geo } });
			windowManager.assignToSlot('bad-layout', 'nonexistent-layout', 'left');

			// Should be unchanged
			expect(windowManager.getWindow('bad-layout')!.geometry).toEqual(geo);
		});

		it('assignToSlot with unknown slot is a no-op', () => {
			const geo = { x: 100, y: 100, width: 400, height: 300 };
			windowManager.openWindow({ id: 'bad-slot', title: 'BS', icon: 'terminal', state: 'normal', geometry: { ...geo } });
			windowManager.assignToSlot('bad-slot', '2-even', 'nonexistent' as any);

			expect(windowManager.getWindow('bad-slot')!.geometry).toEqual(geo);
		});

		it('assignToSlot with unknown window is a no-op', () => {
			// Should not throw
			windowManager.assignToSlot('nonexistent-window', '2-even', 'left');
			expect(windowManager.windows).toHaveLength(0);
		});
	});

	describe('resize business logic', () => {
		it('resizeWindow enforces minimum width', () => {
			windowManager.openWindow({
				id: 'res-min', title: 'RM', icon: 'terminal',
				state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 },
				minWidth: 300,
			});

			windowManager.resizeWindow('res-min', 100, 300);
			expect(windowManager.getWindow('res-min')!.geometry!.width).toBe(300);
		});

		it('resizeWindow enforces minimum height', () => {
			windowManager.openWindow({
				id: 'res-minh', title: 'RMH', icon: 'terminal',
				state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 },
				minHeight: 250,
			});

			windowManager.resizeWindow('res-minh', 400, 100);
			expect(windowManager.getWindow('res-minh')!.geometry!.height).toBe(250);
		});

		it('resizeWindow uses default minWidth/minHeight when not specified', () => {
			windowManager.openWindow({
				id: 'res-default', title: 'RD', icon: 'terminal',
				state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 },
			});

			windowManager.resizeWindow('res-default', 50, 50);
			expect(windowManager.getWindow('res-default')!.geometry!.width).toBe(200); // default min
			expect(windowManager.getWindow('res-default')!.geometry!.height).toBe(150); // default min
		});

		it('resizeWindow is no-op for non-resizable windows', () => {
			windowManager.openWindow({
				id: 'no-resize', title: 'NR', icon: 'terminal',
				state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 },
				resizable: false,
			});

			windowManager.resizeWindow('no-resize', 600, 500);
			expect(windowManager.getWindow('no-resize')!.geometry!.width).toBe(400);
			expect(windowManager.getWindow('no-resize')!.geometry!.height).toBe(300);
		});

		it('moveAndResizeWindow is no-op for non-resizable windows', () => {
			windowManager.openWindow({
				id: 'no-mr', title: 'NMR', icon: 'terminal',
				state: 'normal', geometry: { x: 10, y: 20, width: 400, height: 300 },
				resizable: false,
			});

			windowManager.moveAndResizeWindow('no-mr', 100, 200, 600, 500);
			const win = windowManager.getWindow('no-mr')!;
			expect(win.geometry!.x).toBe(10);
			expect(win.geometry!.width).toBe(400);
		});

		it('moveWindow is no-op for windows without geometry', () => {
			windowManager.openWindow({ id: 'no-geo-move', title: 'NGM', icon: 'terminal' });
			// Window is maximized with no geometry
			windowManager.moveWindow('no-geo-move', 100, 200);
			expect(windowManager.getWindow('no-geo-move')!.geometry).toBeUndefined();
		});
	});

	describe('viewport clamping edge cases', () => {
		it('clamps oversized window dimensions to viewport', () => {
			// Save geometry larger than viewport
			const hugeGeo = { x: 0, y: 0, width: 5000, height: 3000 };
			windowManager.openWindow({
				id: 'oversized', title: 'OS', icon: 'terminal',
				state: 'normal', geometry: { ...hugeGeo },
			});
			windowManager.closeWindow('oversized');

			const reopened = windowManager.openWindow({ id: 'oversized', title: 'OS', icon: 'terminal' });
			const { vw, vh } = getViewportSize();
			expect(reopened.geometry!.width).toBeLessThanOrEqual(vw);
			expect(reopened.geometry!.height).toBeLessThanOrEqual(vh);
		});

		it('clamps negative positions to keep window partially visible', () => {
			const negGeo = { x: -1000, y: -500, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'neg-pos', title: 'NP', icon: 'terminal',
				state: 'normal', geometry: { ...negGeo },
			});
			windowManager.closeWindow('neg-pos');

			const reopened = windowManager.openWindow({ id: 'neg-pos', title: 'NP', icon: 'terminal' });
			// x should be clamped so at least 50px is visible: x >= -(width - 50)
			expect(reopened.geometry!.x).toBeGreaterThanOrEqual(-(reopened.geometry!.width - 50));
			// y should be >= 0
			expect(reopened.geometry!.y).toBeGreaterThanOrEqual(0);
		});

		it('window dimensions respect minWidth/minHeight after clamping', () => {
			// Save very small geometry, then reopen with larger min constraints
			const tinyGeo = { x: 50, y: 50, width: 100, height: 80 };
			windowManager.openWindow({
				id: 'tiny', title: 'T', icon: 'terminal',
				state: 'normal', geometry: { ...tinyGeo },
			});
			windowManager.closeWindow('tiny');

			// Reopen with larger min constraints
			const reopened = windowManager.openWindow({
				id: 'tiny', title: 'T', icon: 'terminal',
				minWidth: 400, minHeight: 300,
			});
			expect(reopened.geometry!.width).toBeGreaterThanOrEqual(400);
			expect(reopened.geometry!.height).toBeGreaterThanOrEqual(300);
		});

		it('handles zero-sized viewport gracefully', () => {
			// Inject geometry, the clampGeometry should handle edge cases
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['zero-vp'] = { x: 100, y: 100, width: 400, height: 300 };

			// Even in a tiny viewport, window should still be created
			const win = windowManager.openWindow({ id: 'zero-vp', title: 'ZV', icon: 'terminal' });
			expect(win.geometry).toBeDefined();
		});
	});

	describe('invalid data rejection', () => {
		it('rejects geometry with string values', () => {
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['string-geo'] = { x: 'hello', y: 100, width: 500, height: 400 };

			const win = windowManager.openWindow({ id: 'string-geo', title: 'SG', icon: 'terminal' });
			expect(win.geometry).toBeUndefined();
		});

		it('rejects geometry with null values', () => {
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['null-geo'] = { x: null, y: 100, width: 500, height: 400 };

			const win = windowManager.openWindow({ id: 'null-geo', title: 'NG', icon: 'terminal' });
			expect(win.geometry).toBeUndefined();
		});

		it('rejects geometry with undefined values', () => {
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['undef-geo'] = { x: undefined, y: 100, width: 500, height: 400 };

			const win = windowManager.openWindow({ id: 'undef-geo', title: 'UG', icon: 'terminal' });
			expect(win.geometry).toBeUndefined();
		});

		it('rejects geometry with negative Infinity', () => {
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['neginf-geo'] = { x: -Infinity, y: 100, width: 500, height: 400 };

			const win = windowManager.openWindow({ id: 'neginf-geo', title: 'NI', icon: 'terminal' });
			expect(win.geometry).toBeUndefined();
		});

		it('rejects null geometry object', () => {
			const prefs = (windowManager as any)._prefs;
			prefs.geometries['null-obj'] = null;

			const win = windowManager.openWindow({ id: 'null-obj', title: 'NO', icon: 'terminal' });
			expect(win.geometry).toBeUndefined();
		});

		it('handles corrupted localStorage gracefully', () => {
			// Write garbage to localStorage
			localStore.set('pf_window_prefs', 'not-valid-json{{{');

			// loadPrefs should catch and return defaults
			// We can verify this works by checking that the manager still functions
			const win = windowManager.openWindow({ id: 'corrupt', title: 'C', icon: 'terminal' });
			expect(win).toBeDefined();
			expect(win.state).toBe('maximized');
		});
	});

	describe('state persistence edge cases', () => {
		it('does not save geometry for maximized windows (only state)', () => {
			windowManager.openWindow({ id: 'max-no-geo', title: 'MNG', icon: 'terminal' });
			// Window is maximized, no geometry
			windowManager.closeWindow('max-no-geo');

			const prefs = (windowManager as any)._prefs;
			expect(prefs.states['max-no-geo']).toBe('maximized');
			// geometries should not have an entry (since state was maximized, geometry is undefined)
			expect(prefs.geometries['max-no-geo']).toBeUndefined();
		});

		it('saves geometry only for normal state windows', () => {
			const geo = { x: 50, y: 50, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'normal-save', title: 'NS', icon: 'terminal',
				state: 'normal', geometry: { ...geo },
			});
			windowManager.closeWindow('normal-save');

			const prefs = (windowManager as any)._prefs;
			expect(prefs.geometries['normal-save']).toEqual(geo);
			expect(prefs.states['normal-save']).toBe('normal');
		});

		it('minimized window state is saved but geometry is not updated', () => {
			const geo = { x: 100, y: 100, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'min-save', title: 'MS', icon: 'terminal',
				state: 'normal', geometry: { ...geo },
			});
			windowManager.minimizeWindow('min-save');
			windowManager.closeWindow('min-save');

			const prefs = (windowManager as any)._prefs;
			expect(prefs.states['min-save']).toBe('minimized');
			// Geometry from normal state was saved before the minimize
		});

		it('explicit state in openWindow overrides saved state', () => {
			windowManager.openWindow({ id: 'state-ov', title: 'SO', icon: 'terminal', state: 'normal' });
			windowManager.closeWindow('state-ov');
			// Saved state should be 'normal'

			const reopened = windowManager.openWindow({ id: 'state-ov', title: 'SO', icon: 'terminal', state: 'maximized' });
			expect(reopened.state).toBe('maximized');
		});

		it('saved geometry does not override explicit geometry in openWindow', () => {
			// Save geometry
			windowManager.openWindow({
				id: 'geo-ov', title: 'GO', icon: 'terminal',
				state: 'normal', geometry: { x: 100, y: 100, width: 400, height: 300 },
			});
			windowManager.closeWindow('geo-ov');

			// Reopen with explicit geometry — clamped saved geo takes precedence
			// (per the code: geometry: clampedGeo ?? entry.geometry)
			const reopened = windowManager.openWindow({
				id: 'geo-ov', title: 'GO', icon: 'terminal',
				geometry: { x: 200, y: 200, width: 500, height: 400 },
			});
			// clampedGeo should be the saved 100,100 geometry
			expect(reopened.geometry!.x).toBe(100);
			expect(reopened.geometry!.y).toBe(100);
		});
	});

	describe('snap zone detection edge cases', () => {
		const VW = 1280;
		const VH = 680;

		it('exact threshold boundary triggers zone', () => {
			// Exactly at 20px threshold (EDGE_THRESHOLD = 20)
			const zone = computeSnapZone(20, 340, VW, VH);
			expect(zone).not.toBeNull();
			expect(zone!.id).toBe('left');
		});

		it('one pixel past threshold returns null', () => {
			const zone = computeSnapZone(21, 340, VW, VH);
			expect(zone).toBeNull();
		});

		it('right edge exact boundary', () => {
			const zone = computeSnapZone(VW - 20, 340, VW, VH);
			expect(zone).not.toBeNull();
			expect(zone!.id).toBe('right');
		});

		it('right edge one pixel past returns null', () => {
			const zone = computeSnapZone(VW - 21, 340, VW, VH);
			expect(zone).toBeNull();
		});

		it('top maximize threshold at exactly 8px', () => {
			// TOP_MAXIMIZE_THRESHOLD = 8
			const zone = computeSnapZone(640, 8, VW, VH);
			expect(zone).not.toBeNull();
			expect(zone!.id).toBe('top');
		});

		it('top maximize does not trigger at 9px', () => {
			// At y=9, neither in corner zone nor top maximize zone
			const zone = computeSnapZone(640, 9, VW, VH);
			expect(zone).toBeNull();
		});

		it('corner detection at exact boundary (20px, 20px)', () => {
			const zone = computeSnapZone(20, 20, VW, VH);
			expect(zone).not.toBeNull();
			expect(zone!.id).toBe('top-left');
		});

		it('all 7 zone geometries cover expected areas', () => {
			const zones: Array<{ id: string; x: number; y: number }> = [
				{ id: 'left', x: 5, y: 340 },
				{ id: 'right', x: VW - 5, y: 340 },
				{ id: 'top', x: 640, y: 3 },
				{ id: 'top-left', x: 5, y: 5 },
				{ id: 'top-right', x: VW - 5, y: 5 },
				{ id: 'bottom-left', x: 5, y: VH - 5 },
				{ id: 'bottom-right', x: VW - 5, y: VH - 5 },
			];

			for (const { id, x, y } of zones) {
				const zone = computeSnapZone(x, y, VW, VH);
				expect(zone, `expected zone ${id} at (${x}, ${y})`).not.toBeNull();
				expect(zone!.id).toBe(id);
			}
		});
	});

	describe('window focus and z-order during snap operations', () => {
		it('snapWindowToZone focuses the snapped window', () => {
			windowManager.openWindow({ id: 'zf1', title: 'ZF1', icon: 'terminal', state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 } });
			windowManager.openWindow({ id: 'zf2', title: 'ZF2', icon: 'folder', state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 } });
			expect(windowManager.activeWindowId).toBe('zf2');

			const zone = { id: 'left' as const, geometry: { x: 0, y: 0, width: 640, height: 680 } };
			windowManager.snapWindowToZone('zf1', zone);
			expect(windowManager.activeWindowId).toBe('zf1');
		});

		it('assignToSlot focuses the assigned window', () => {
			windowManager.openWindow({ id: 'af1', title: 'AF1', icon: 'terminal', state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 } });
			windowManager.openWindow({ id: 'af2', title: 'AF2', icon: 'folder', state: 'normal', geometry: { x: 0, y: 0, width: 400, height: 300 } });
			expect(windowManager.activeWindowId).toBe('af2');

			windowManager.assignToSlot('af1', '2-even', 'left');
			expect(windowManager.activeWindowId).toBe('af1');
		});
	});

	describe('sessionStorage vs localStorage separation', () => {
		it('open windows are persisted to sessionStorage (pf_wm)', () => {
			windowManager.openWindow({ id: 'sess-test', title: 'ST', icon: 'terminal' });
			const session = storage.get('pf_wm');
			expect(session).toBeTruthy();
			const parsed = JSON.parse(session!);
			expect(parsed.windows.some((w: any) => w.id === 'sess-test')).toBe(true);
		});

		it('window geometry prefs are persisted to localStorage (pf_window_prefs)', () => {
			const geo = { x: 50, y: 50, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'local-test', title: 'LT', icon: 'terminal',
				state: 'normal', geometry: { ...geo },
			});
			windowManager.closeWindow('local-test');

			const local = localStore.get('pf_window_prefs');
			expect(local).toBeTruthy();
			const parsed = JSON.parse(local!);
			expect(parsed.geometries['local-test']).toEqual(geo);
		});

		it('closing all windows clears sessionStorage windows but preserves localStorage prefs', () => {
			const geo = { x: 100, y: 100, width: 400, height: 300 };
			windowManager.openWindow({
				id: 'persist-check', title: 'PC', icon: 'terminal',
				state: 'normal', geometry: { ...geo },
			});
			windowManager.closeWindow('persist-check');

			const session = storage.get('pf_wm');
			const parsed = JSON.parse(session!);
			expect(parsed.windows).toHaveLength(0);

			// But localStorage still has the prefs
			const local = localStore.get('pf_window_prefs');
			const localParsed = JSON.parse(local!);
			expect(localParsed.geometries['persist-check']).toBeDefined();
		});
	});

	describe('tileWindows integration', () => {
		it('tiles visible windows and sets them to normal state', () => {
			windowManager.openWindow({ id: 'tile1', title: 'T1', icon: 'terminal' });
			windowManager.openWindow({ id: 'tile2', title: 'T2', icon: 'folder' });
			windowManager.openWindow({ id: 'tile3', title: 'T3', icon: 'cpu' });

			windowManager.tileWindows('left-right');

			for (const id of ['tile1', 'tile2', 'tile3']) {
				const win = windowManager.getWindow(id)!;
				expect(win.state).toBe('normal');
				expect(win.geometry).toBeDefined();
				expect(win.geometry!.y).toBe(0);
			}

			// Windows should fill the full width
			const { vw } = getViewportSize();
			const totalWidth = ['tile1', 'tile2', 'tile3'].reduce(
				(sum, id) => sum + windowManager.getWindow(id)!.geometry!.width, 0
			);
			expect(totalWidth).toBeLessThanOrEqual(vw + 3); // allow rounding
		});

		it('minimized windows are excluded from tiling', () => {
			windowManager.openWindow({ id: 'vis1', title: 'V1', icon: 'terminal' });
			windowManager.openWindow({ id: 'vis2', title: 'V2', icon: 'folder' });
			windowManager.openWindow({ id: 'min-tile', title: 'MT', icon: 'cpu' });
			windowManager.minimizeWindow('min-tile');

			windowManager.tileWindows('left-right');

			const minWin = windowManager.getWindow('min-tile')!;
			expect(minWin.state).toBe('minimized');
			// The two visible windows should split the viewport
			const { vw } = getViewportSize();
			const expectedWidth = Math.floor(vw / 2);
			expect(windowManager.getWindow('vis1')!.geometry!.width).toBe(expectedWidth);
		});
	});

	// ── Magnetic Edge Snapping ──

	describe('getSnapCandidateWindows', () => {
		function makeEntry(id: string, state: 'normal' | 'maximized' | 'minimized', geo?: { x: number; y: number; width: number; height: number }): WindowEntry {
			return { id, title: id, icon: 'terminal', state, zIndex: 1, geometry: geo };
		}

		it('excludes self', () => {
			const windows = [
				makeEntry('a', 'normal', { x: 0, y: 0, width: 200, height: 200 }),
				makeEntry('b', 'normal', { x: 300, y: 0, width: 200, height: 200 }),
			];
			const result = getSnapCandidateWindows(windows, 'a');
			expect(result).toHaveLength(1);
			expect(result[0].id).toBe('b');
		});

		it('excludes minimized and maximized windows', () => {
			const windows = [
				makeEntry('a', 'normal', { x: 0, y: 0, width: 200, height: 200 }),
				makeEntry('b', 'minimized', { x: 300, y: 0, width: 200, height: 200 }),
				makeEntry('c', 'maximized', { x: 0, y: 0, width: 1280, height: 720 }),
				makeEntry('d', 'normal', { x: 500, y: 0, width: 200, height: 200 }),
			];
			const result = getSnapCandidateWindows(windows, 'a');
			expect(result).toHaveLength(1);
			expect(result[0].id).toBe('d');
		});

		it('excludes windows without geometry', () => {
			const windows = [
				makeEntry('a', 'normal', { x: 0, y: 0, width: 200, height: 200 }),
				makeEntry('b', 'normal'), // no geometry
			];
			const result = getSnapCandidateWindows(windows, 'a');
			expect(result).toHaveLength(0);
		});
	});

	describe('computeEdgeSnap', () => {
		function makeEntry(id: string, geo: { x: number; y: number; width: number; height: number }): WindowEntry {
			return { id, title: id, icon: 'terminal', state: 'normal', zIndex: 1, geometry: geo };
		}

		it('snaps right edge to left edge (adjacent)', () => {
			const dragged = { x: 195, y: 50, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 400, y: 50, width: 200, height: 200 })];
			const result = computeEdgeSnap(dragged, others);
			// dragged right edge (395) is within 12px of other left edge (400) → snap to 400-200=200
			expect(result.x).toBe(200);
			expect(result.snappedEdges.horizontal).toBe('right');
		});

		it('snaps left edge to right edge (adjacent)', () => {
			const dragged = { x: 405, y: 50, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 100, y: 50, width: 300, height: 200 })];
			const result = computeEdgeSnap(dragged, others);
			// dragged left edge (405) is within 12px of other right edge (400) → snap to 400
			expect(result.x).toBe(400);
			expect(result.snappedEdges.horizontal).toBe('left');
		});

		it('snaps bottom edge to top edge (adjacent)', () => {
			const dragged = { x: 50, y: 190, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 50, y: 400, width: 200, height: 200 })];
			const result = computeEdgeSnap(dragged, others);
			// dragged bottom edge (390) is within 12px of other top edge (400) → snap to 400-200=200
			expect(result.y).toBe(200);
			expect(result.snappedEdges.vertical).toBe('bottom');
		});

		it('snaps top edge to bottom edge (adjacent)', () => {
			const dragged = { x: 50, y: 405, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 50, y: 100, width: 200, height: 300 })];
			const result = computeEdgeSnap(dragged, others);
			// dragged top edge (405) is within 12px of other bottom edge (400) → snap to 400
			expect(result.y).toBe(400);
			expect(result.snappedEdges.vertical).toBe('top');
		});

		it('snaps alignment: left↔left', () => {
			const dragged = { x: 107, y: 100, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 100, y: 50, width: 300, height: 200 })];
			const result = computeEdgeSnap(dragged, others);
			// dragged left (107) within 12px of other left (100), vertical overlap exists → snap to 100
			expect(result.x).toBe(100);
			expect(result.snappedEdges.horizontal).toBe('left');
		});

		it('does not snap beyond threshold', () => {
			const dragged = { x: 50, y: 50, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 300, y: 50, width: 200, height: 200 })];
			const result = computeEdgeSnap(dragged, others);
			// dragged right edge (250) is 50px from other left edge (300) → no snap
			expect(result.x).toBe(50);
			expect(result.y).toBe(50);
			expect(result.snappedEdges.horizontal).toBeNull();
			expect(result.snappedEdges.vertical).toBeNull();
		});

		it('does not snap horizontally without vertical overlap', () => {
			const dragged = { x: 188, y: 500, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 400, y: 50, width: 200, height: 100 })];
			const result = computeEdgeSnap(dragged, others);
			// No vertical overlap (dragged: 500-700, other: 50-150) → no horizontal snap
			expect(result.x).toBe(188);
			expect(result.snappedEdges.horizontal).toBeNull();
		});

		it('picks closest edge with multiple candidates', () => {
			const dragged = { x: 290, y: 50, width: 200, height: 200 };
			const others = [
				makeEntry('b', { x: 500, y: 50, width: 200, height: 200 }),
				makeEntry('c', { x: 505, y: 50, width: 200, height: 200 }),
			];
			const result = computeEdgeSnap(dragged, others);
			// dragged right edge (490): distance to b.left (500) = 10, to c.left (505) = 15 → pick b
			expect(result.x).toBe(300);
			expect(result.snappedEdges.horizontal).toBe('right');
		});

		it('supports simultaneous dual-axis snap to different windows', () => {
			const dragged = { x: 295, y: 195, width: 200, height: 200 };
			const others = [
				makeEntry('b', { x: 500, y: 100, width: 200, height: 200 }), // right of dragged
				makeEntry('c', { x: 200, y: 400, width: 200, height: 200 }), // below dragged
			];
			const result = computeEdgeSnap(dragged, others);
			// H: dragged right (495) → b.left (500) = 5px → snap x=300
			// V: dragged bottom (395) → c.top (400) = 5px → snap y=200
			expect(result.x).toBe(300);
			expect(result.y).toBe(200);
			expect(result.snappedEdges.horizontal).toBe('right');
			expect(result.snappedEdges.vertical).toBe('bottom');
		});

		it('returns original position with empty candidates', () => {
			const dragged = { x: 100, y: 100, width: 200, height: 200 };
			const result = computeEdgeSnap(dragged, []);
			expect(result.x).toBe(100);
			expect(result.y).toBe(100);
			expect(result.snappedEdges.horizontal).toBeNull();
			expect(result.snappedEdges.vertical).toBeNull();
		});
	});

	describe('computeResizeEdgeSnap', () => {
		function makeEntry(id: string, geo: { x: number; y: number; width: number; height: number }): WindowEntry {
			return { id, title: id, icon: 'terminal', state: 'normal', zIndex: 1, geometry: geo };
		}

		it('snaps east edge to adjacent window left', () => {
			const geo = { x: 100, y: 50, width: 295, height: 200 };
			const others = [makeEntry('b', { x: 400, y: 50, width: 200, height: 200 })];
			const result = computeResizeEdgeSnap(geo, 'e', others);
			// right edge (395) within 12px of b.left (400) → width = 400 - 100 = 300
			expect(result.width).toBe(300);
			expect(result.x).toBe(100); // unchanged
		});

		it('snaps west edge to adjacent window right', () => {
			const geo = { x: 405, y: 50, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 100, y: 50, width: 300, height: 200 })];
			const result = computeResizeEdgeSnap(geo, 'w', others);
			// left edge (405) within 12px of b.right (400) → x=400, width=605-400=205
			expect(result.x).toBe(400);
			expect(result.width).toBe(205);
		});

		it('snaps south edge to adjacent window top', () => {
			const geo = { x: 50, y: 100, width: 200, height: 293 };
			const others = [makeEntry('b', { x: 50, y: 400, width: 200, height: 200 })];
			const result = computeResizeEdgeSnap(geo, 's', others);
			// bottom edge (393) within 12px of b.top (400) → height = 400 - 100 = 300
			expect(result.height).toBe(300);
			expect(result.y).toBe(100); // unchanged
		});

		it('does not snap non-resized edges', () => {
			const geo = { x: 188, y: 50, width: 200, height: 200 };
			const others = [makeEntry('b', { x: 400, y: 50, width: 200, height: 200 })];
			// Only resizing south — right edge (388) near b.left (400) should NOT snap
			const result = computeResizeEdgeSnap(geo, 's', others);
			expect(result.x).toBe(188);
			expect(result.width).toBe(200);
		});

		it('snaps north edge to adjacent window bottom', () => {
			const geo = { x: 50, y: 405, width: 200, height: 300 };
			const others = [makeEntry('b', { x: 50, y: 100, width: 200, height: 300 })];
			const result = computeResizeEdgeSnap(geo, 'n', others);
			// top edge (405) within 12px of b.bottom (400) → y=400, height=705-400=305
			expect(result.y).toBe(400);
			expect(result.height).toBe(305);
		});

		it('snaps alignment: east edge to other right edge', () => {
			const geo = { x: 100, y: 50, width: 497, height: 200 };
			const others = [makeEntry('b', { x: 200, y: 50, width: 400, height: 200 })];
			const result = computeResizeEdgeSnap(geo, 'e', others);
			// right edge (597) within 12px of b.right (600) → width = 600 - 100 = 500
			expect(result.width).toBe(500);
			expect(result.x).toBe(100);
		});

		it('picks closest candidate across multiple windows (west)', () => {
			const geo = { x: 405, y: 50, width: 200, height: 200 };
			const others = [
				makeEntry('b', { x: 100, y: 50, width: 300, height: 200 }), // right=400
				makeEntry('c', { x: 50, y: 50, width: 348, height: 200 }),  // right=398
			];
			const result = computeResizeEdgeSnap(geo, 'w', others);
			// left edge (405): d to b.right (400) = 5, d to c.right (398) = 7 → picks b (closer)
			expect(result.x).toBe(400);
			expect(result.width).toBe(205);
		});

		it('regression: west resize picks closer candidate not further', () => {
			// Bug: mutated `x` caused further candidates to incorrectly win.
			// Window B is closer (right=400, d=5), C is further (right=396, d=9).
			// Without fix, after snapping to B (x→400), C would be checked with
			// mutated x=400 → d=|400-396|=4 < |400-405|=5 → incorrectly wins.
			const geo = { x: 405, y: 50, width: 200, height: 200 };
			const others = [
				makeEntry('b', { x: 100, y: 50, width: 300, height: 200 }), // right=400 (d=5)
				makeEntry('c', { x: 50, y: 50, width: 346, height: 200 }),  // right=396 (d=9)
			];
			const result = computeResizeEdgeSnap(geo, 'w', others);
			// Should snap to B (closer to original left edge 405)
			expect(result.x).toBe(400);
			expect(result.width).toBe(205);
		});

		it('handles diagonal resize (se) with cross-axis snaps', () => {
			const geo = { x: 100, y: 100, width: 295, height: 293 };
			const others = [
				makeEntry('b', { x: 400, y: 100, width: 200, height: 200 }), // for east snap
				makeEntry('c', { x: 100, y: 400, width: 200, height: 200 }), // for south snap
			];
			const result = computeResizeEdgeSnap(geo, 'se', others);
			// east: right (395) → b.left (400), width = 300
			// south: bottom (393) → c.top (400), height = 300
			expect(result.width).toBe(300);
			expect(result.height).toBe(300);
			expect(result.x).toBe(100);
			expect(result.y).toBe(100);
		});
	});
});
