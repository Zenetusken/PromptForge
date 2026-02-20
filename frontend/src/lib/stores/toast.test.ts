import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { toastState } from './toast.svelte';

describe('ToastState', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		toastState.toasts = [];
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('starts with empty toasts', () => {
		expect(toastState.toasts).toHaveLength(0);
	});

	it('show() adds a toast', () => {
		toastState.show('Hello');

		expect(toastState.toasts).toHaveLength(1);
		expect(toastState.toasts[0].message).toBe('Hello');
		expect(toastState.toasts[0].type).toBe('info');
		expect(toastState.toasts[0].dismissing).toBe(false);
	});

	it('show() respects type parameter', () => {
		toastState.show('Error!', 'error');

		expect(toastState.toasts[0].type).toBe('error');
	});

	it('show() respects success type', () => {
		toastState.show('Done', 'success');

		expect(toastState.toasts[0].type).toBe('success');
	});

	it('show() assigns unique IDs', () => {
		toastState.show('first');
		toastState.show('second');

		expect(toastState.toasts[0].id).not.toBe(toastState.toasts[1].id);
	});

	it('show() auto-dismisses after duration', () => {
		toastState.show('Auto', 'info', 2000);

		expect(toastState.toasts).toHaveLength(1);

		// After duration, toast starts dismissing
		vi.advanceTimersByTime(2000);
		expect(toastState.toasts[0].dismissing).toBe(true);

		// After 300ms animation delay, toast is removed
		vi.advanceTimersByTime(300);
		expect(toastState.toasts).toHaveLength(0);
	});

	it('dismiss() sets dismissing flag then removes after 300ms', () => {
		toastState.show('Test');
		const id = toastState.toasts[0].id;

		toastState.dismiss(id);

		// Immediately: dismissing = true, toast still present
		expect(toastState.toasts).toHaveLength(1);
		expect(toastState.toasts[0].dismissing).toBe(true);

		// After 300ms: removed
		vi.advanceTimersByTime(300);
		expect(toastState.toasts).toHaveLength(0);
	});

	it('dismiss() is idempotent for same ID', () => {
		toastState.show('Test');
		const id = toastState.toasts[0].id;

		toastState.dismiss(id);
		toastState.dismiss(id); // Second call should be a no-op

		expect(toastState.toasts).toHaveLength(1);
		vi.advanceTimersByTime(300);
		expect(toastState.toasts).toHaveLength(0);
	});

	it('dismiss() ignores unknown IDs', () => {
		toastState.show('Test');

		toastState.dismiss(99999);

		expect(toastState.toasts).toHaveLength(1);
		expect(toastState.toasts[0].dismissing).toBe(false);
	});

	it('multiple toasts coexist', () => {
		toastState.show('first');
		toastState.show('second');
		toastState.show('third');

		expect(toastState.toasts).toHaveLength(3);

		// Dismiss the middle one
		toastState.dismiss(toastState.toasts[1].id);
		vi.advanceTimersByTime(300);

		expect(toastState.toasts).toHaveLength(2);
		expect(toastState.toasts[0].message).toBe('first');
		expect(toastState.toasts[1].message).toBe('third');
	});

	it('uses default duration of 4000ms', () => {
		toastState.show('Default duration');

		expect(toastState.toasts[0].duration).toBe(4000);

		// Not dismissed at 3999ms
		vi.advanceTimersByTime(3999);
		expect(toastState.toasts[0].dismissing).toBe(false);

		// Dismissed at 4000ms
		vi.advanceTimersByTime(1);
		expect(toastState.toasts[0].dismissing).toBe(true);
	});
});
