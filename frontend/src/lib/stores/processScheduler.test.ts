import { describe, it, expect, beforeEach, vi } from 'vitest';

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

import { systemBus } from '$lib/services/systemBus.svelte';
import { processScheduler, type ForgeProcess } from './processScheduler.svelte';

describe('ProcessScheduler', () => {
	beforeEach(() => {
		processScheduler.reset();
		systemBus.reset();
		storageMap.clear();
		uuidCounter = 0;
	});

	describe('spawn', () => {
		it('creates a running process with monotonic PID', () => {
			const proc = processScheduler.spawn({ title: 'Forge A' });
			expect(proc.pid).toBe(1);
			expect(proc.status).toBe('running');
			expect(proc.title).toBe('Forge A');
			expect(proc.parentPid).toBeNull();
			expect(proc.priority).toBe('interactive');
			expect(processScheduler.processes).toHaveLength(1);
		});

		it('assigns incrementing PIDs', () => {
			const a = processScheduler.spawn({ title: 'A' });
			const b = processScheduler.spawn({ title: 'B' });
			expect(b.pid).toBe(a.pid + 1);
		});

		it('sets activeProcessId to the new process', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			expect(processScheduler.activeProcessId).toBe(proc.id);
		});

		it('queues when at maxConcurrent', () => {
			processScheduler.maxConcurrent = 1;
			const a = processScheduler.spawn({ title: 'A' });
			const b = processScheduler.spawn({ title: 'B' });
			expect(a.status).toBe('running');
			expect(b.status).toBe('queued');
		});

		it('respects priority parameter', () => {
			const proc = processScheduler.spawn({ title: 'Batch', priority: 'batch' });
			expect(proc.priority).toBe('batch');
		});

		it('sets parentPid for retry chains', () => {
			const parent = processScheduler.spawn({ title: 'Parent' });
			const child = processScheduler.spawn({ title: 'Retry', parentPid: parent.pid });
			expect(child.parentPid).toBe(parent.pid);
		});

		it('emits forge:started on the bus', () => {
			const handler = vi.fn();
			systemBus.on('forge:started', handler);
			processScheduler.spawn({ title: 'Test' });
			expect(handler).toHaveBeenCalledOnce();
			expect(handler.mock.calls[0][0].payload.title).toBe('Test');
		});

		it('evicts oldest completed at max capacity', () => {
			processScheduler.maxConcurrent = 20; // avoid queuing
			for (let i = 0; i < 10; i++) {
				processScheduler.spawn({ title: `F${i}` });
			}
			// Complete the oldest
			const oldest = processScheduler.processes[processScheduler.processes.length - 1];
			processScheduler.complete(oldest.id, { score: 5 });

			processScheduler.spawn({ title: 'F10' });
			expect(processScheduler.processes).toHaveLength(10);
			expect(processScheduler.processes.some(p => p.id === oldest.id)).toBe(false);
		});
	});

	describe('complete', () => {
		it('marks process as completed with data', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, {
				score: 8.5,
				strategy: 'chain-of-thought',
				optimizationId: 'opt-1',
			});

			const updated = processScheduler.findById(proc.id);
			expect(updated?.status).toBe('completed');
			expect(updated?.score).toBe(8.5);
			expect(updated?.strategy).toBe('chain-of-thought');
			expect(updated?.optimizationId).toBe('opt-1');
			expect(updated?.completedAt).toBeGreaterThan(0);
		});

		it('emits forge:completed on the bus', () => {
			const handler = vi.fn();
			systemBus.on('forge:completed', handler);
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, { score: 7 });

			expect(handler).toHaveBeenCalledOnce();
			expect(handler.mock.calls[0][0].payload.score).toBe(7);
		});

		it('promotes next queued process', () => {
			processScheduler.maxConcurrent = 1;
			const a = processScheduler.spawn({ title: 'A' });
			const b = processScheduler.spawn({ title: 'B' });
			expect(b.status).toBe('queued');

			processScheduler.complete(a.id, { score: 8 });
			const updatedB = processScheduler.findById(b.id);
			expect(updatedB?.status).toBe('running');
		});

		it('no-ops for unknown ID', () => {
			processScheduler.spawn({ title: 'A' });
			processScheduler.complete('nonexistent', { score: 5 });
			expect(processScheduler.processes[0].status).toBe('running');
		});
	});

	describe('fail', () => {
		it('marks process as error', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.fail(proc.id, 'Rate limit');

			expect(processScheduler.findById(proc.id)?.status).toBe('error');
			expect(processScheduler.findById(proc.id)?.error).toBe('Rate limit');
		});

		it('emits forge:failed on the bus', () => {
			const handler = vi.fn();
			systemBus.on('forge:failed', handler);
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.fail(proc.id, 'Error msg');

			expect(handler).toHaveBeenCalledOnce();
			expect(handler.mock.calls[0][0].payload.error).toBe('Error msg');
		});

		it('promotes next queued process', () => {
			processScheduler.maxConcurrent = 1;
			const a = processScheduler.spawn({ title: 'A' });
			const b = processScheduler.spawn({ title: 'B' });

			processScheduler.fail(a.id, 'Failed');
			expect(processScheduler.findById(b.id)?.status).toBe('running');
		});
	});

	describe('cancel', () => {
		it('cancels a running process by PID', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.cancel(proc.pid);

			expect(processScheduler.findByPid(proc.pid)?.status).toBe('cancelled');
		});

		it('cancels a queued process by PID', () => {
			processScheduler.maxConcurrent = 1;
			processScheduler.spawn({ title: 'A' });
			const b = processScheduler.spawn({ title: 'B' });

			processScheduler.cancel(b.pid);
			expect(processScheduler.findByPid(b.pid)?.status).toBe('cancelled');
		});

		it('emits forge:cancelled on the bus', () => {
			const handler = vi.fn();
			systemBus.on('forge:cancelled', handler);
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.cancel(proc.pid);

			expect(handler).toHaveBeenCalledOnce();
		});

		it('no-ops for completed/error processes', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, { score: 8 });
			processScheduler.cancel(proc.pid);
			expect(processScheduler.findByPid(proc.pid)?.status).toBe('completed');
		});
	});

	describe('dismiss', () => {
		it('removes a completed process', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, { score: 8 });
			processScheduler.dismiss(proc.pid);
			expect(processScheduler.processes).toHaveLength(0);
		});

		it('does not remove a running process', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.dismiss(proc.pid);
			expect(processScheduler.processes).toHaveLength(1);
		});

		it('updates activeProcessId when dismissing active', () => {
			const a = processScheduler.spawn({ title: 'A' });
			const b = processScheduler.spawn({ title: 'B' });
			processScheduler.complete(a.id, {});
			processScheduler.complete(b.id, {});
			processScheduler.activeProcessId = b.id;
			processScheduler.dismiss(b.pid);
			expect(processScheduler.activeProcessId).toBe(a.id);
		});
	});

	describe('promote', () => {
		it('bumps a queued process to interactive priority', () => {
			processScheduler.maxConcurrent = 1;
			processScheduler.spawn({ title: 'A' });
			const b = processScheduler.spawn({ title: 'B', priority: 'batch' });

			expect(b.priority).toBe('batch');
			processScheduler.promote(b.pid);
			expect(processScheduler.findByPid(b.pid)?.priority).toBe('interactive');
		});

		it('no-ops for non-queued processes', () => {
			const proc = processScheduler.spawn({ title: 'A' });
			processScheduler.promote(proc.pid);
			expect(proc.priority).toBe('interactive'); // unchanged
		});
	});

	describe('updateProgress', () => {
		it('updates stage and progress', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.updateProgress(proc.id, 'analyze', 0.5);

			const updated = processScheduler.findById(proc.id);
			expect(updated?.currentStage).toBe('analyze');
			expect(updated?.progress).toBe(0.5);
		});

		it('clamps progress to 0-1', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.updateProgress(proc.id, 'validate', 1.5);
			expect(processScheduler.findById(proc.id)?.progress).toBe(1);

			processScheduler.updateProgress(proc.id, 'validate', -0.5);
			expect(processScheduler.findById(proc.id)?.progress).toBe(0);
		});

		it('no-ops for non-running processes', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, {});
			processScheduler.updateProgress(proc.id, 'analyze', 0.5);
			expect(processScheduler.findById(proc.id)?.currentStage).toBeNull();
		});
	});

	describe('derived state', () => {
		it('queue returns only queued processes', () => {
			processScheduler.maxConcurrent = 1;
			processScheduler.spawn({ title: 'A' });
			processScheduler.spawn({ title: 'B' });
			processScheduler.spawn({ title: 'C' });

			expect(processScheduler.queue).toHaveLength(2);
			expect(processScheduler.running).toHaveLength(1);
		});

		it('canSpawn is true when under maxConcurrent', () => {
			processScheduler.maxConcurrent = 2;
			expect(processScheduler.canSpawn).toBe(true);
			processScheduler.spawn({ title: 'A' });
			expect(processScheduler.canSpawn).toBe(true);
			processScheduler.spawn({ title: 'B' });
			expect(processScheduler.canSpawn).toBe(false);
		});

		it('activeProcess returns the active process', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			expect(processScheduler.activeProcess?.id).toBe(proc.id);
		});

		it('activeProcess returns null when no active', () => {
			expect(processScheduler.activeProcess).toBeNull();
		});
	});

	describe('priority-based promotion', () => {
		it('promotes interactive before batch when slot opens', () => {
			processScheduler.maxConcurrent = 1;
			const running = processScheduler.spawn({ title: 'Running' });
			processScheduler.spawn({ title: 'Batch', priority: 'batch' });
			const interactive = processScheduler.spawn({ title: 'Interactive', priority: 'interactive' });

			processScheduler.complete(running.id, {});

			// Interactive should be promoted first
			expect(processScheduler.findById(interactive.id)?.status).toBe('running');
		});
	});

	describe('persistence', () => {
		it('persists processes to sessionStorage', () => {
			processScheduler.spawn({ title: 'Test' });
			const stored = storageMap.get('pf_scheduler_processes');
			expect(stored).toBeTruthy();
			const parsed = JSON.parse(stored!);
			expect(parsed).toHaveLength(1);
			expect(parsed[0].title).toBe('Test');
		});

		it('persists activeProcessId', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			expect(storageMap.get('pf_scheduler_active')).toBe(proc.id);
		});

		it('strips result and metadata from persisted data', () => {
			const proc = processScheduler.spawn({ title: 'Test' });
			processScheduler.complete(proc.id, { result: { id: 'r1' } as any });
			const stored = JSON.parse(storageMap.get('pf_scheduler_processes')!);
			expect(stored[0]).not.toHaveProperty('result');
			expect(stored[0]).not.toHaveProperty('metadata');
		});
	});
});
