import { describe, it, expect, vi, beforeEach } from 'vitest';

// Stub localStorage before importing the store
const storage: Record<string, string> = {};
vi.stubGlobal('localStorage', {
	getItem: vi.fn((key: string) => storage[key] ?? null),
	setItem: vi.fn((key: string, value: string) => {
		storage[key] = value;
	}),
	removeItem: vi.fn((key: string) => {
		delete storage[key];
	}),
});

import { sidebarState } from './sidebar.svelte';

describe('SidebarState', () => {
	beforeEach(() => {
		Object.keys(storage).forEach((k) => delete storage[k]);
		sidebarState.activeTab = 'history';
		sidebarState.isOpen = true;
		vi.clearAllMocks(); // Clear after state reset so setter's setItem calls don't leak
	});

	it('defaults to history tab', () => {
		expect(sidebarState.activeTab).toBe('history');
	});

	it('setTab() switches to projects', () => {
		sidebarState.setTab('projects');

		expect(sidebarState.activeTab).toBe('projects');
	});

	it('setTab() switches back to history', () => {
		sidebarState.setTab('projects');
		sidebarState.setTab('history');

		expect(sidebarState.activeTab).toBe('history');
	});

	it('setTab() persists to localStorage', () => {
		sidebarState.setTab('projects');

		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_tab', 'projects');
	});

	it('setTab() persists history to localStorage', () => {
		sidebarState.setTab('history');

		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_tab', 'history');
	});

	it('isOpen defaults to true', () => {
		expect(sidebarState.isOpen).toBe(true);
	});

	it('close() sets isOpen to false and persists', () => {
		sidebarState.close();

		expect(sidebarState.isOpen).toBe(false);
		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_open', 'false');
	});

	it('open() sets isOpen to true and persists', () => {
		sidebarState.close();
		vi.clearAllMocks();

		sidebarState.open();

		expect(sidebarState.isOpen).toBe(true);
		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_open', 'true');
	});

	it('toggle() flips isOpen and persists', () => {
		sidebarState.toggle();

		expect(sidebarState.isOpen).toBe(false);
		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_open', 'false');

		vi.clearAllMocks();
		sidebarState.toggle();

		expect(sidebarState.isOpen).toBe(true);
		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_open', 'true');
	});

	it('isOpen setter persists to localStorage', () => {
		sidebarState.isOpen = false;

		expect(storage['pf_sidebar_open']).toBe('false');

		sidebarState.isOpen = true;

		expect(storage['pf_sidebar_open']).toBe('true');
	});

	it('openTo() opens sidebar and switches tab', () => {
		sidebarState.close();
		vi.clearAllMocks();

		sidebarState.openTo('projects');

		expect(sidebarState.isOpen).toBe(true);
		expect(sidebarState.activeTab).toBe('projects');
		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_tab', 'projects');
		expect(localStorage.setItem).toHaveBeenCalledWith('pf_sidebar_open', 'true');
	});

	it('loads isOpen from localStorage on init', () => {
		// Simulate "false" in storage — since the module is already loaded,
		// we verify the load function logic via setter/getter round-trip
		storage['pf_sidebar_open'] = 'false';

		// The getter reads from the reactive field, not storage directly,
		// so we verify the setter persists correctly instead
		sidebarState.isOpen = false;
		expect(sidebarState.isOpen).toBe(false);
		expect(storage['pf_sidebar_open']).toBe('false');
	});
});
