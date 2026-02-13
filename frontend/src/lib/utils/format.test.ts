import { describe, it, expect } from 'vitest';
import { formatRelativeTime, truncateText, formatPercent, formatDate } from './format';

describe('formatRelativeTime', () => {
	it('returns "just now" for recent timestamps', () => {
		const now = new Date().toISOString();
		expect(formatRelativeTime(now)).toBe('just now');
	});

	it('returns minutes ago for timestamps within an hour', () => {
		const date = new Date(Date.now() - 5 * 60 * 1000).toISOString();
		expect(formatRelativeTime(date)).toBe('5m ago');
	});

	it('returns hours ago for timestamps within a day', () => {
		const date = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
		expect(formatRelativeTime(date)).toBe('3h ago');
	});

	it('returns days ago for timestamps within a week', () => {
		const date = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
		expect(formatRelativeTime(date)).toBe('2d ago');
	});

	it('returns formatted date for older timestamps', () => {
		const date = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
		const result = formatRelativeTime(date);
		// Should be a formatted date like "Jan 14" (not relative)
		expect(result).not.toContain('ago');
	});
});

describe('truncateText', () => {
	it('returns full text when shorter than max length', () => {
		expect(truncateText('hello', 10)).toBe('hello');
	});

	it('truncates and adds ellipsis for long text', () => {
		expect(truncateText('hello world this is long', 10)).toBe('hello worl...');
	});

	it('returns exact text when equal to max length', () => {
		expect(truncateText('12345', 5)).toBe('12345');
	});
});

describe('formatPercent', () => {
	it('formats a number as a percentage', () => {
		expect(formatPercent(75)).toBe('75%');
	});

	it('rounds decimal values', () => {
		expect(formatPercent(75.6)).toBe('76%');
	});

	it('handles zero', () => {
		expect(formatPercent(0)).toBe('0%');
	});
});

describe('formatDate', () => {
	it('returns a readable date string', () => {
		const result = formatDate('2024-06-15T10:30:00Z');
		expect(result).toContain('June');
		expect(result).toContain('15');
		expect(result).toContain('2024');
	});
});
