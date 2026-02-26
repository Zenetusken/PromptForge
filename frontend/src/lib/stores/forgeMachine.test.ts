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

// Mock crypto.randomUUID
let uuidCounter = 0;
if (!globalThis.crypto?.randomUUID) {
	Object.defineProperty(globalThis, 'crypto', {
		value: { randomUUID: () => `test-uuid-${++uuidCounter}` },
		writable: true,
	});
}

import { forgeMachine } from './forgeMachine.svelte';
import { processScheduler } from './processScheduler.svelte';

describe('ForgeMachineState', () => {
	beforeEach(() => {
		forgeMachine.reset();
		forgeMachine.setWidth(240);
		processScheduler.reset();
		storageMap.clear();
		uuidCounter = 0;
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

	describe('process lifecycle (via processScheduler)', () => {
		it('spawn creates a running process', () => {
			const proc = processScheduler.spawn({ title: 'Test Forge' });
			expect(proc.id).toBeTruthy();
			expect(processScheduler.processes).toHaveLength(1);
			expect(processScheduler.processes[0].status).toBe('running');
			expect(processScheduler.processes[0].title).toBe('Test Forge');
		});

		it('spawn sets activeProcessId', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			expect(processScheduler.activeProcessId).toBe(proc.id);
		});

		it('spawn prepends new processes', () => {
			processScheduler.spawn({ title: 'First' });
			processScheduler.spawn({ title: 'Second' });
			expect(processScheduler.processes[0].title).toBe('Second');
			expect(processScheduler.processes[1].title).toBe('First');
		});

		it('complete marks process with score and strategy', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, {
				score: 0.85,
				strategy: 'chain-of-thought',
				optimizationId: 'opt-1',
			});
			const found = processScheduler.findById(proc.id);
			expect(found?.status).toBe('completed');
			expect(found?.score).toBe(0.85);
			expect(found?.strategy).toBe('chain-of-thought');
			expect(found?.optimizationId).toBe('opt-1');
		});

		it('complete no-ops for unknown id', () => {
			processScheduler.spawn({ title: 'Test' });
			processScheduler.complete('nonexistent', { score: 5 });
			expect(processScheduler.processes).toHaveLength(1);
			expect(processScheduler.processes[0].status).toBe('running');
		});

		it('fail marks process as error', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.fail(proc.id);
			expect(processScheduler.findById(proc.id)?.status).toBe('error');
		});

		it('dismiss removes process from list', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, {});
			processScheduler.dismiss(proc.pid);
			expect(processScheduler.processes).toHaveLength(0);
		});

		it('runningCount is reflected on forgeMachine', () => {
			processScheduler.spawn({ title: 'A' });
			processScheduler.spawn({ title: 'B' });
			const procC = processScheduler.spawn({ title: 'C' });
			processScheduler.complete(procC.id, { score: 7 });

			expect(forgeMachine.runningCount).toBe(2);
		});
	});

	describe('minimize and restore', () => {
		it('minimize sets isMinimized when not in compose', () => {
			forgeMachine.forge();
			forgeMachine.minimize();
			expect(forgeMachine.isMinimized).toBe(true);
		});

		it('minimize is no-op in compose mode', () => {
			forgeMachine.minimize();
			expect(forgeMachine.isMinimized).toBe(false);
		});

		it('restore clears isMinimized', () => {
			forgeMachine.forge();
			forgeMachine.minimize();
			forgeMachine.restore();
			expect(forgeMachine.isMinimized).toBe(false);
		});

	});

	describe('enterReview and enterForging', () => {
		it('enterReview sets mode to review from any state', () => {
			expect(forgeMachine.mode).toBe('compose');
			forgeMachine.enterReview();
			expect(forgeMachine.mode).toBe('review');
		});

		it('enterReview clears isMinimized', () => {
			forgeMachine.forge();
			forgeMachine.minimize();
			expect(forgeMachine.isMinimized).toBe(true);
			forgeMachine.enterReview();
			expect(forgeMachine.isMinimized).toBe(false);
			expect(forgeMachine.mode).toBe('review');
		});

		it('enterReview persists to sessionStorage', () => {
			forgeMachine.enterReview();
			const stored = storageMap.get('pf_forge_machine');
			expect(stored).toBeTruthy();
			const parsed = JSON.parse(stored!);
			expect(parsed.mode).toBe('review');
			expect(parsed.isMinimized).toBe(false);
		});

		it('enterForging sets mode to forging from any state', () => {
			forgeMachine.enterForging();
			expect(forgeMachine.mode).toBe('forging');
		});

		it('enterForging auto-widens when compact', () => {
			forgeMachine.setWidth(240);
			forgeMachine.enterForging();
			expect(forgeMachine.panelWidth).toBe(380);
			expect(forgeMachine.widthTier).toBe('standard');
		});

		it('enterForging does not shrink when already wider', () => {
			forgeMachine.setWidth(400);
			forgeMachine.enterForging();
			expect(forgeMachine.panelWidth).toBe(400);
		});

		it('enterForging persists to sessionStorage', () => {
			forgeMachine.enterForging();
			const stored = storageMap.get('pf_forge_machine');
			expect(stored).toBeTruthy();
			const parsed = JSON.parse(stored!);
			expect(parsed.mode).toBe('forging');
		});
	});
});
