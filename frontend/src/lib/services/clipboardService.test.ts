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

// Mock navigator.clipboard
const mockClipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
Object.defineProperty(globalThis, 'navigator', {
	value: { clipboard: mockClipboard },
	writable: true,
});

import { systemBus } from './systemBus.svelte';
import { clipboardService } from './clipboardService.svelte';

describe('ClipboardService', () => {
	beforeEach(() => {
		clipboardService.reset();
		systemBus.reset();
		storageMap.clear();
		mockClipboard.writeText.mockResolvedValue(undefined);
	});

	describe('copy', () => {
		it('copies text to system clipboard', async () => {
			const result = await clipboardService.copy('Hello', 'Test', 'manual');
			expect(result).toBe(true);
			expect(mockClipboard.writeText).toHaveBeenCalledWith('Hello');
		});

		it('adds entry to history', async () => {
			await clipboardService.copy('Hello', 'Test Copy', 'forge-result');
			expect(clipboardService.history).toHaveLength(1);
			const entry = clipboardService.history[0];
			expect(entry.text).toBe('Hello');
			expect(entry.label).toBe('Test Copy');
			expect(entry.source).toBe('forge-result');
			expect(entry.id).toMatch(/^clip_\d+$/);
		});

		it('prepends to history (most recent first)', async () => {
			await clipboardService.copy('First', 'A');
			await clipboardService.copy('Second', 'B');
			expect(clipboardService.history[0].text).toBe('Second');
			expect(clipboardService.history[1].text).toBe('First');
		});

		it('caps history at 10', async () => {
			for (let i = 0; i < 12; i++) {
				await clipboardService.copy(`Item ${i}`);
			}
			expect(clipboardService.history).toHaveLength(10);
			expect(clipboardService.history[0].text).toBe('Item 11');
		});

		it('emits clipboard:copied event on bus', async () => {
			const handler = vi.fn();
			systemBus.on('clipboard:copied', handler);

			await clipboardService.copy('Test', 'My Label', 'forge-result');

			expect(handler).toHaveBeenCalledOnce();
			const event = handler.mock.calls[0][0];
			expect(event.payload.label).toBe('My Label');
			expect(event.payload.source).toBe('forge-result');
			expect(event.payload.textLength).toBe(4);
		});

		it('uses default label and source', async () => {
			await clipboardService.copy('Hello');
			expect(clipboardService.history[0].label).toBe('Copied text');
			expect(clipboardService.history[0].source).toBe('manual');
		});
	});

	describe('getLatest', () => {
		it('returns the most recent entry', async () => {
			await clipboardService.copy('First');
			await clipboardService.copy('Second');
			expect(clipboardService.getLatest()?.text).toBe('Second');
		});

		it('returns null when history is empty', () => {
			expect(clipboardService.getLatest()).toBeNull();
		});
	});

	describe('clear', () => {
		it('empties history', async () => {
			await clipboardService.copy('A');
			await clipboardService.copy('B');
			clipboardService.clear();
			expect(clipboardService.history).toHaveLength(0);
		});
	});

	describe('persistence', () => {
		it('persists to sessionStorage on copy', async () => {
			await clipboardService.copy('Stored', 'Label');
			const stored = storageMap.get('pf_clipboard_history');
			expect(stored).toBeTruthy();
			const parsed = JSON.parse(stored!);
			expect(parsed).toHaveLength(1);
			expect(parsed[0].text).toBe('Stored');
		});
	});
});
