import { describe, it, expect } from 'vitest';
import { formatRelativeTime, formatExactTime, truncateText, normalizeScore, formatScore, getScoreColorClass, getScoreTierLabel, getScoreBadgeClass, formatModelShort, maskApiKey, formatComplexityDots, formatMetadataSummary } from './format';

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

describe('formatExactTime', () => {
	it('returns a human-readable date with weekday, month, day, year, and time', () => {
		// Use a fixed UTC date and check that key components are present
		const result = formatExactTime('2025-03-15T14:30:00Z');
		// Should contain the month and day at minimum
		expect(result).toContain('Mar');
		expect(result).toContain('15');
		expect(result).toContain('2025');
	});

	it('includes the weekday abbreviation', () => {
		// 2025-03-15 is a Saturday
		const result = formatExactTime('2025-03-15T14:30:00Z');
		expect(result).toContain('Sat');
	});

	it('handles ISO date strings', () => {
		const result = formatExactTime('2024-12-25T09:00:00.000Z');
		expect(result).toContain('Dec');
		expect(result).toContain('25');
		expect(result).toContain('2024');
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

describe('getScoreTierLabel', () => {
	it('returns "Good" for high scores', () => {
		expect(getScoreTierLabel(0.85)).toBe('Good');
		expect(getScoreTierLabel(70)).toBe('Good');
	});

	it('returns "Fair" for medium scores', () => {
		expect(getScoreTierLabel(0.5)).toBe('Fair');
		expect(getScoreTierLabel(40)).toBe('Fair');
	});

	it('returns "Low" for low scores', () => {
		expect(getScoreTierLabel(0.2)).toBe('Low');
		expect(getScoreTierLabel(30)).toBe('Low');
	});

	it('returns empty string for null', () => {
		expect(getScoreTierLabel(null)).toBe('');
	});

	it('returns empty string for undefined', () => {
		expect(getScoreTierLabel(undefined)).toBe('');
	});

	it('returns "Good" for exact boundary at 70', () => {
		expect(getScoreTierLabel(0.70)).toBe('Good');
	});

	it('returns "Fair" for exact boundary at 40', () => {
		expect(getScoreTierLabel(0.40)).toBe('Fair');
	});

	it('returns "Low" for zero', () => {
		expect(getScoreTierLabel(0)).toBe('Low');
	});
});

describe('getScoreBadgeClass', () => {
	it('returns green classes for high scores', () => {
		expect(getScoreBadgeClass(0.85)).toBe('bg-neon-green/10 text-neon-green');
	});

	it('returns yellow classes for medium scores', () => {
		expect(getScoreBadgeClass(0.5)).toBe('bg-neon-yellow/10 text-neon-yellow');
	});

	it('returns red classes for low scores', () => {
		expect(getScoreBadgeClass(0.2)).toBe('bg-neon-red/10 text-neon-red');
	});

	it('returns dim classes for null', () => {
		expect(getScoreBadgeClass(null)).toBe('bg-text-dim/10 text-text-dim');
	});

	it('returns dim classes for undefined', () => {
		expect(getScoreBadgeClass(undefined)).toBe('bg-text-dim/10 text-text-dim');
	});
});

describe('maskApiKey', () => {
	it('masks a long key showing first 4 and last 4 chars', () => {
		expect(maskApiKey('sk-ant-api03-abcdefghijklmnop')).toBe('sk-a...mnop');
	});

	it('fully masks short keys (8 chars or fewer)', () => {
		expect(maskApiKey('12345678')).toBe('********');
		expect(maskApiKey('short')).toBe('********');
	});

	it('masks a 9-character key', () => {
		expect(maskApiKey('123456789')).toBe('1234...6789');
	});

	it('handles empty string', () => {
		expect(maskApiKey('')).toBe('********');
	});
});

describe('formatModelShort', () => {
	it('strips claude- prefix', () => {
		expect(formatModelShort('claude-opus-4-6')).toBe('opus-4-6');
	});

	it('strips claude- prefix for sonnet', () => {
		expect(formatModelShort('claude-sonnet-4-5-20250929')).toBe('sonnet-4-5-20250929');
	});

	it('passes through non-Claude models unchanged', () => {
		expect(formatModelShort('gpt-4o')).toBe('gpt-4o');
		expect(formatModelShort('gemini-2.5-pro')).toBe('gemini-2.5-pro');
	});

	it('handles empty string', () => {
		expect(formatModelShort('')).toBe('');
	});
});

describe('formatComplexityDots', () => {
	it('returns 1 filled for simple', () => {
		expect(formatComplexityDots('simple')).toEqual({ filled: 1, total: 3 });
	});

	it('returns 2 filled for moderate', () => {
		expect(formatComplexityDots('moderate')).toEqual({ filled: 2, total: 3 });
	});

	it('returns 3 filled for complex', () => {
		expect(formatComplexityDots('complex')).toEqual({ filled: 3, total: 3 });
	});

	it('is case-insensitive', () => {
		expect(formatComplexityDots('Simple')).toEqual({ filled: 1, total: 3 });
		expect(formatComplexityDots('COMPLEX')).toEqual({ filled: 3, total: 3 });
	});

	it('defaults to 1 for unknown values', () => {
		expect(formatComplexityDots('unknown')).toEqual({ filled: 1, total: 3 });
	});
});

describe('formatMetadataSummary', () => {
	it('returns empty array when no fields provided', () => {
		expect(formatMetadataSummary({})).toEqual([]);
	});

	it('includes identity segment for taskType', () => {
		const result = formatMetadataSummary({ taskType: 'code-review' });
		expect(result).toHaveLength(1);
		expect(result[0]).toEqual({ type: 'identity', value: 'code-review' });
	});

	it('includes process segment for framework', () => {
		const result = formatMetadataSummary({ framework: 'chain-of-thought' });
		expect(result).toHaveLength(1);
		expect(result[0]).toEqual({ type: 'process', value: 'chain-of-thought' });
	});

	it('strips claude- prefix from model', () => {
		const result = formatMetadataSummary({ model: 'claude-opus-4-6' });
		expect(result).toHaveLength(1);
		expect(result[0]).toEqual({ type: 'technical', value: 'opus-4-6' });
	});

	it('builds full segment array in correct order', () => {
		const result = formatMetadataSummary({
			taskType: 'creative-writing',
			framework: 'few-shot',
			model: 'gpt-4o',
		});
		expect(result).toHaveLength(3);
		expect(result[0].type).toBe('identity');
		expect(result[1].type).toBe('process');
		expect(result[2].type).toBe('technical');
	});

	it('skips undefined fields', () => {
		const result = formatMetadataSummary({ taskType: 'analysis', model: 'claude-sonnet-4-6' });
		expect(result).toHaveLength(2);
		expect(result[0].value).toBe('analysis');
		expect(result[1].value).toBe('sonnet-4-6');
	});

	it('skips empty string fields', () => {
		const result = formatMetadataSummary({ taskType: '', framework: 'role-based' });
		expect(result).toHaveLength(1);
		expect(result[0].value).toBe('role-based');
	});

	it('skips null fields', () => {
		const result = formatMetadataSummary({ taskType: null, framework: null, model: 'claude-opus-4-6' });
		expect(result).toHaveLength(1);
		expect(result[0]).toEqual({ type: 'technical', value: 'opus-4-6' });
	});
});
