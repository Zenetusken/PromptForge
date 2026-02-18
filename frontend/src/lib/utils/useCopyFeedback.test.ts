import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('$lib/utils/clipboard', () => ({
	copyToClipboard: vi.fn(),
}));

import { useCopyFeedback } from './useCopyFeedback.svelte';
import { copyToClipboard } from '$lib/utils/clipboard';

describe('useCopyFeedback', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('starts with copied = false', () => {
		vi.mocked(copyToClipboard).mockReturnValue(true);
		const feedback = useCopyFeedback();
		expect(feedback.copied).toBe(false);
	});

	it('copy() returns true and sets copied on success', () => {
		vi.mocked(copyToClipboard).mockReturnValue(true);
		const feedback = useCopyFeedback();

		const result = feedback.copy('hello');

		expect(result).toBe(true);
		expect(feedback.copied).toBe(true);
		expect(copyToClipboard).toHaveBeenCalledWith('hello');
	});

	it('copy() returns false and keeps copied false on failure', () => {
		vi.mocked(copyToClipboard).mockReturnValue(false);
		const feedback = useCopyFeedback();

		const result = feedback.copy('hello');

		expect(result).toBe(false);
		expect(feedback.copied).toBe(false);
	});

	it('resets copied to false after default timeout (2000ms)', () => {
		vi.mocked(copyToClipboard).mockReturnValue(true);
		const feedback = useCopyFeedback();

		feedback.copy('text');
		expect(feedback.copied).toBe(true);

		vi.advanceTimersByTime(1999);
		expect(feedback.copied).toBe(true);

		vi.advanceTimersByTime(1);
		expect(feedback.copied).toBe(false);
	});

	it('respects custom resetMs parameter', () => {
		vi.mocked(copyToClipboard).mockReturnValue(true);
		const feedback = useCopyFeedback(500);

		feedback.copy('text');
		expect(feedback.copied).toBe(true);

		vi.advanceTimersByTime(499);
		expect(feedback.copied).toBe(true);

		vi.advanceTimersByTime(1);
		expect(feedback.copied).toBe(false);
	});

	it('restarts timer on repeated copy calls', () => {
		vi.mocked(copyToClipboard).mockReturnValue(true);
		const feedback = useCopyFeedback(1000);

		feedback.copy('first');
		vi.advanceTimersByTime(800);
		expect(feedback.copied).toBe(true);

		// Copy again — should restart the timer
		feedback.copy('second');
		vi.advanceTimersByTime(800);
		// Would have expired from the first copy, but timer was restarted
		expect(feedback.copied).toBe(true);

		vi.advanceTimersByTime(200);
		expect(feedback.copied).toBe(false);
	});

	it('passes text through to copyToClipboard', () => {
		vi.mocked(copyToClipboard).mockReturnValue(true);
		const feedback = useCopyFeedback();

		feedback.copy('specific text to copy');
		expect(copyToClipboard).toHaveBeenCalledWith('specific text to copy');
	});
});
