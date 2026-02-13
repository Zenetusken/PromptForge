import { describe, it, expect } from 'vitest';
import { computeDiff, computeLineDiff } from './diff';

describe('computeDiff', () => {
	it('returns equal segments for identical strings', () => {
		const result = computeDiff('hello world', 'hello world');
		expect(result).toHaveLength(1);
		expect(result[0]).toEqual({ type: 'equal', value: 'hello world' });
	});

	it('detects added words', () => {
		const result = computeDiff('hello', 'hello world');
		const added = result.filter((s) => s.type === 'added');
		expect(added.length).toBeGreaterThan(0);
		expect(added.some((s) => s.value.includes('world'))).toBe(true);
	});

	it('detects removed words', () => {
		const result = computeDiff('hello world', 'hello');
		const removed = result.filter((s) => s.type === 'removed');
		expect(removed.length).toBeGreaterThan(0);
		expect(removed.some((s) => s.value.includes('world'))).toBe(true);
	});

	it('handles empty strings', () => {
		const result = computeDiff('', 'new text');
		expect(result.some((s) => s.type === 'added')).toBe(true);
	});
});

describe('computeLineDiff', () => {
	it('returns matching lines for identical text', () => {
		const result = computeLineDiff('line one\nline two', 'line one\nline two');
		expect(result.left.every((l) => l.type === 'equal')).toBe(true);
		expect(result.right.every((l) => l.type === 'equal')).toBe(true);
	});

	it('marks added lines on the right side', () => {
		const result = computeLineDiff('line one\n', 'line one\nline two\n');
		const addedRight = result.right.filter((l) => l.type === 'added');
		expect(addedRight.length).toBeGreaterThan(0);
		expect(addedRight[0].text).toBe('line two');
	});

	it('marks removed lines on the left side', () => {
		const result = computeLineDiff('line one\nline two\n', 'line one\n');
		const removedLeft = result.left.filter((l) => l.type === 'removed');
		expect(removedLeft.length).toBeGreaterThan(0);
		expect(removedLeft[0].text).toBe('line two');
	});

	it('assigns sequential line numbers', () => {
		const result = computeLineDiff('a\nb\nc', 'a\nx\nc');
		// Left should have lines numbered 1, 2, 3
		expect(result.left.map((l) => l.lineNumber)).toEqual(
			expect.arrayContaining([1, 2, 3])
		);
	});
});
