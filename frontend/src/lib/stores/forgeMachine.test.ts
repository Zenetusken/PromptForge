import { describe, it, expect, beforeEach } from 'vitest';

// Mock sessionStorage
const storageMap = new Map<string, string>();
const mockSessionStorage = {
	getItem: (key: string) => storageMap.get(key) ?? null,
	setItem: (key: string, value: string) => storageMap.set(key, value),
	removeItem: (key: string) => storageMap.delete(key),
	clear: () => storageMap.clear(),
	get length() { return storageMap.size; },
	key: (i: number) => [...storageMap.keys()][i] ?? null,
};
Object.defineProperty(globalThis, 'sessionStorage', { value: mockSessionStorage, writable: true });

import { forgeMachine } from './forgeMachine.svelte';

describe('ForgeMachineState', () => {
	beforeEach(() => {
		forgeMachine.reset();
		forgeMachine.setWidth(240);
		storageMap.clear();
	});

	describe('initial state', () => {
		it('starts in compose mode', () => {
			expect(forgeMachine.mode).toBe('compose');
		});

		it('starts with compact width tier', () => {
			expect(forgeMachine.widthTier).toBe('compact');
		});

		it('isCompact is true at 240px', () => {
			expect(forgeMachine.isCompact).toBe(true);
		});

		it('comparison slots are null', () => {
			expect(forgeMachine.comparison.slotA).toBeNull();
			expect(forgeMachine.comparison.slotB).toBeNull();
		});
	});

	describe('state transitions', () => {
		it('forge() transitions compose → forging', () => {
			forgeMachine.forge();
			expect(forgeMachine.mode).toBe('forging');
		});

		it('forge() is guarded — no-op from forging', () => {
			forgeMachine.forge();
			forgeMachine.forge();
			expect(forgeMachine.mode).toBe('forging');
		});

		it('forge() is guarded — no-op from review', () => {
			forgeMachine.forge();
			forgeMachine.complete();
			forgeMachine.forge();
			expect(forgeMachine.mode).toBe('review');
		});

		it('complete() transitions forging → review', () => {
			forgeMachine.forge();
			forgeMachine.complete();
			expect(forgeMachine.mode).toBe('review');
		});

		it('complete() is guarded — no-op from compose', () => {
			forgeMachine.complete();
			expect(forgeMachine.mode).toBe('compose');
		});

		it('compare() transitions to compare mode', () => {
			forgeMachine.compare('id-a', 'id-b');
			expect(forgeMachine.mode).toBe('compare');
			expect(forgeMachine.comparison.slotA).toBe('id-a');
			expect(forgeMachine.comparison.slotB).toBe('id-b');
		});

		it('back() transitions to compose from any mode', () => {
			forgeMachine.forge();
			forgeMachine.back();
			expect(forgeMachine.mode).toBe('compose');

			forgeMachine.forge();
			forgeMachine.complete();
			forgeMachine.back();
			expect(forgeMachine.mode).toBe('compose');

			forgeMachine.compare('a', 'b');
			forgeMachine.back();
			expect(forgeMachine.mode).toBe('compose');
		});

		it('back() clears comparison slots', () => {
			forgeMachine.compare('a', 'b');
			forgeMachine.back();
			expect(forgeMachine.comparison.slotA).toBeNull();
			expect(forgeMachine.comparison.slotB).toBeNull();
		});

		it('back() is no-op from compose', () => {
			forgeMachine.back();
			expect(forgeMachine.mode).toBe('compose');
		});

		it('reset() returns to compose and clears slots', () => {
			forgeMachine.compare('a', 'b');
			forgeMachine.reset();
			expect(forgeMachine.mode).toBe('compose');
			expect(forgeMachine.comparison.slotA).toBeNull();
		});
	});

	describe('panel width', () => {
		it('setWidth clamps to min (240)', () => {
			forgeMachine.setWidth(100);
			expect(forgeMachine.panelWidth).toBe(240);
		});

		it('setWidth clamps to max (560)', () => {
			forgeMachine.setWidth(1000);
			expect(forgeMachine.panelWidth).toBe(560);
		});

		it('setWidth accepts values in range', () => {
			forgeMachine.setWidth(400);
			expect(forgeMachine.panelWidth).toBe(400);
		});

		it('widthTier is compact below 340', () => {
			forgeMachine.setWidth(300);
			expect(forgeMachine.widthTier).toBe('compact');
		});

		it('widthTier is standard at 340-479', () => {
			forgeMachine.setWidth(380);
			expect(forgeMachine.widthTier).toBe('standard');
		});

		it('widthTier is wide at 480+', () => {
			forgeMachine.setWidth(500);
			expect(forgeMachine.widthTier).toBe('wide');
		});

		it('forge() auto-widens to standard when compact', () => {
			forgeMachine.setWidth(240);
			forgeMachine.forge();
			expect(forgeMachine.panelWidth).toBe(380);
			expect(forgeMachine.widthTier).toBe('standard');
		});

		it('forge() does not shrink if already wider', () => {
			forgeMachine.setWidth(400);
			forgeMachine.forge();
			expect(forgeMachine.panelWidth).toBe(400);
		});

		it('compare() auto-widens to wide', () => {
			forgeMachine.setWidth(380);
			forgeMachine.compare('a', 'b');
			expect(forgeMachine.panelWidth).toBe(560);
			expect(forgeMachine.widthTier).toBe('wide');
		});

		it('compare() does not shrink if already wide', () => {
			forgeMachine.setWidth(500);
			forgeMachine.compare('a', 'b');
			expect(forgeMachine.panelWidth).toBe(500);
		});

		it('persists width to sessionStorage', () => {
			forgeMachine.setWidth(400);
			expect(storageMap.get('pf_forge_panel_width')).toBe('400');
		});
	});
});
