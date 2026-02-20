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
		vi.clearAllMocks();
		Object.keys(storage).forEach((k) => delete storage[k]);
		sidebarState.activeTab = 'history';
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
});
