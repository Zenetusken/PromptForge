import { describe, it, expect } from 'vitest';
import { formatRelativeTime, truncateText, normalizeScore, formatScore, getScoreColorClass } from './format';

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

describe('normalizeScore', () => {
	it('returns null for null input', () => {
		expect(normalizeScore(null)).toBeNull();
	});

	it('returns null for undefined input', () => {
		expect(normalizeScore(undefined)).toBeNull();
	});

	it('converts 0-1 scale to 0-100', () => {
		expect(normalizeScore(0.85)).toBe(85);
	});

	it('rounds 0-1 scale values', () => {
		expect(normalizeScore(0.856)).toBe(86);
	});

	it('passes through 0-100 values', () => {
		expect(normalizeScore(75)).toBe(75);
	});

	it('handles exact 1 as 100', () => {
		expect(normalizeScore(1)).toBe(100);
	});

	it('handles 0 as 0', () => {
		expect(normalizeScore(0)).toBe(0);
	});
});

describe('formatScore', () => {
	it('returns dash for null', () => {
		expect(formatScore(null)).toBe('—');
	});

	it('returns dash for undefined', () => {
		expect(formatScore(undefined)).toBe('—');
	});

	it('formats 0-1 score as string', () => {
		expect(formatScore(0.85)).toBe('85');
	});

	it('formats 0-100 score as string', () => {
		expect(formatScore(75)).toBe('75');
	});
});

describe('getScoreColorClass', () => {
	it('returns neon-green for high scores', () => {
		expect(getScoreColorClass(0.85)).toBe('neon-green');
		expect(getScoreColorClass(70)).toBe('neon-green');
	});

	it('returns neon-yellow for medium scores', () => {
		expect(getScoreColorClass(0.5)).toBe('neon-yellow');
		expect(getScoreColorClass(40)).toBe('neon-yellow');
	});

	it('returns neon-red for low scores', () => {
		expect(getScoreColorClass(0.2)).toBe('neon-red');
		expect(getScoreColorClass(30)).toBe('neon-red');
	});

	it('returns neon-red for null', () => {
		expect(getScoreColorClass(null)).toBe('neon-red');
	});
});
