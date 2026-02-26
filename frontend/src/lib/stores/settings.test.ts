import { describe, it, expect, beforeEach } from 'vitest';

// Mock localStorage
const storageMap = new Map<string, string>();
const mockLocalStorage = {
	getItem: (key: string) => storageMap.get(key) ?? null,
	setItem: (key: string, value: string) => storageMap.set(key, value),
	removeItem: (key: string) => storageMap.delete(key),
	clear: () => storageMap.clear(),
	get length() { return storageMap.size; },
	key: (i: number) => [...storageMap.keys()][i] ?? null,
};
Object.defineProperty(globalThis, 'localStorage', { value: mockLocalStorage, writable: true });

// Mock sessionStorage (needed by transitive imports)
const sessionMap = new Map<string, string>();
Object.defineProperty(globalThis, 'sessionStorage', {
	value: {
		getItem: (key: string) => sessionMap.get(key) ?? null,
		setItem: (key: string, value: string) => sessionMap.set(key, value),
		removeItem: (key: string) => sessionMap.delete(key),
		clear: () => sessionMap.clear(),
		get length() { return sessionMap.size; },
		key: (i: number) => [...sessionMap.keys()][i] ?? null,
	},
	writable: true,
});

import { settingsState } from './settings.svelte';

describe('SettingsState', () => {
	beforeEach(() => {
		storageMap.clear();
		settingsState.reset();
	});

	describe('default values', () => {
		it('has cyan as default accent color', () => {
			expect(settingsState.accentColor).toBe('neon-cyan');
		});

		it('has 2 as default max concurrent forges', () => {
			expect(settingsState.maxConcurrentForges).toBe(2);
		});

		it('has animations enabled by default', () => {
			expect(settingsState.enableAnimations).toBe(true);
		});

		it('has no default strategy', () => {
			expect(settingsState.defaultStrategy).toBe('');
		});

		it('has no default provider', () => {
			expect(settingsState.defaultProvider).toBeNull();
		});
	});

	describe('update', () => {
		it('updates a single field', () => {
			settingsState.update({ accentColor: 'neon-purple' });
			expect(settingsState.accentColor).toBe('neon-purple');
		});

		it('updates multiple fields', () => {
			settingsState.update({
				maxConcurrentForges: 4,
				enableAnimations: false,
			});
			expect(settingsState.maxConcurrentForges).toBe(4);
			expect(settingsState.enableAnimations).toBe(false);
		});

		it('preserves unmodified fields', () => {
			settingsState.update({ accentColor: 'neon-green' });
			expect(settingsState.maxConcurrentForges).toBe(2); // default preserved
		});

		it('persists to localStorage', () => {
			settingsState.update({ accentColor: 'neon-red' });
			const stored = storageMap.get('pf_settings');
			expect(stored).toBeTruthy();
			const parsed = JSON.parse(stored!);
			expect(parsed.accentColor).toBe('neon-red');
		});
	});

	describe('reset', () => {
		it('restores all defaults', () => {
			settingsState.update({
				accentColor: 'neon-pink',
				maxConcurrentForges: 5,
				enableAnimations: false,
			});

			settingsState.reset();

			expect(settingsState.accentColor).toBe('neon-cyan');
			expect(settingsState.maxConcurrentForges).toBe(2);
			expect(settingsState.enableAnimations).toBe(true);
		});
	});
});
