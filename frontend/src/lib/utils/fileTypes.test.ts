import { describe, it, expect } from 'vitest';
import { toFilename, TYPE_SORT_ORDER, FILE_EXTENSIONS, DEFAULT_EXTENSION } from './fileTypes';

describe('toFilename', () => {
	it('uses title when provided', () => {
		expect(toFilename('some content', 'My Prompt')).toBe('My Prompt.md');
	});

	it('does not double the extension if title already has .md', () => {
		expect(toFilename('content', 'My Prompt.md')).toBe('My Prompt.md');
	});

	it('handles .MD case-insensitively', () => {
		expect(toFilename('content', 'My Prompt.MD')).toBe('My Prompt.MD');
	});

	it('derives filename from content when no title', () => {
		expect(toFilename('Short prompt text')).toBe('Short prompt text.md');
	});

	it('derives filename from content when title is null', () => {
		expect(toFilename('Short prompt text', null)).toBe('Short prompt text.md');
	});

	it('derives filename from content when title is empty', () => {
		expect(toFilename('Short prompt text', '')).toBe('Short prompt text.md');
	});

	it('derives filename from content when title is whitespace', () => {
		expect(toFilename('Short prompt text', '   ')).toBe('Short prompt text.md');
	});

	it('returns Untitled.md for empty content', () => {
		expect(toFilename('')).toBe('Untitled.md');
	});

	it('returns Untitled.md for whitespace-only content', () => {
		expect(toFilename('   ')).toBe('Untitled.md');
	});

	it('returns Untitled.md for empty content and empty title', () => {
		expect(toFilename('', '')).toBe('Untitled.md');
	});

	it('returns full content + .md for content <= 40 chars', () => {
		const content = 'Exactly forty characters long text here!';
		expect(content.length).toBe(40);
		expect(toFilename(content)).toBe('Exactly forty characters long text here!.md');
	});

	it('truncates long content at word boundary', () => {
		const content = 'Review this Python function for correctness and performance issues';
		const result = toFilename(content);
		expect(result).toMatch(/\.md$/);
		expect(result).toContain('...');
		// Should be reasonably short
		expect(result.length).toBeLessThan(50);
	});

	it('truncates long title with .md already present', () => {
		const title = 'This is a very long title that exceeds forty four characters limit by a lot.md';
		const result = toFilename('content', title);
		expect(result).toMatch(/\.md$/);
		expect(result).toContain('...');
	});

	it('handles single long word without spaces', () => {
		const content = 'abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJ';
		const result = toFilename(content);
		expect(result).toMatch(/\.md$/);
		expect(result).toContain('...');
	});
});

describe('TYPE_SORT_ORDER', () => {
	it('orders system < folder < file', () => {
		expect(TYPE_SORT_ORDER['system']).toBeLessThan(TYPE_SORT_ORDER['folder']);
		expect(TYPE_SORT_ORDER['folder']).toBeLessThan(TYPE_SORT_ORDER['file']);
	});
});

describe('FILE_EXTENSIONS', () => {
	it('defines .md extension', () => {
		expect(FILE_EXTENSIONS['.md']).toBeDefined();
		expect(FILE_EXTENSIONS['.md'].icon).toBe('file-text');
	});
});

describe('DEFAULT_EXTENSION', () => {
	it('is .md', () => {
		expect(DEFAULT_EXTENSION).toBe('.md');
	});
});
