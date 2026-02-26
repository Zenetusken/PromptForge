import { describe, it, expect, beforeEach } from 'vitest';

// Mock sessionStorage
const storage = new Map<string, string>();
const mockStorage = {
	getItem: (key: string) => storage.get(key) ?? null,
	setItem: (key: string, value: string) => storage.set(key, value),
	removeItem: (key: string) => storage.delete(key),
};
Object.defineProperty(globalThis, 'sessionStorage', { value: mockStorage, writable: true });

import { windowManager, PERSISTENT_WINDOW_IDS } from './windowManager.svelte';

describe('WindowManagerState', () => {
	beforeEach(() => {
		storage.clear();
		// Close all windows to reset
		for (const w of [...windowManager.windows]) {
			windowManager.closeWindow(w.id);
		}
		windowManager.startMenuOpen = false;
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

		it('has exactly 11 entries', () => {
			expect(PERSISTENT_WINDOW_IDS.size).toBe(11);
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
});
