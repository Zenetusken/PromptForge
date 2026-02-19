import { describe, it, expect } from 'vitest';
import { promptState } from './prompt.svelte';

describe('PromptState', () => {
	it('starts with empty text', () => {
		expect(promptState.text).toBe('');
	});

	it('set() updates text', () => {
		promptState.set('hello world');
		expect(promptState.text).toBe('hello world');
	});

	it('set() can update to a different value', () => {
		promptState.set('first');
		promptState.set('second');
		expect(promptState.text).toBe('second');
	});

	it('clear() resets text to empty string', () => {
		promptState.set('something');
		promptState.clear();
		expect(promptState.text).toBe('');
	});

	it('set() handles empty string', () => {
		promptState.set('non-empty');
		promptState.set('');
		expect(promptState.text).toBe('');
	});

	it('set() handles multiline text', () => {
		const multiline = 'line 1\nline 2\nline 3';
		promptState.set(multiline);
		expect(promptState.text).toBe(multiline);
	});

	it('set() stores promptId when provided', () => {
		promptState.set('text', 'project', 'prompt-123');
		expect(promptState.promptId).toBe('prompt-123');
		expect(promptState.projectName).toBe('project');
	});

	it('set() defaults promptId to empty string', () => {
		promptState.set('text', 'project');
		expect(promptState.promptId).toBe('');
	});

	it('clear() resets promptId', () => {
		promptState.set('text', 'proj', 'pid');
		promptState.clear();
		expect(promptState.promptId).toBe('');
		expect(promptState.projectName).toBe('');
	});

	it('set() stores metadata fields when provided', () => {
		promptState.set('text', 'proj', 'pid', {
			title: 'My Title',
			tags: ['tag1', 'tag2'],
			version: 'v3',
			sourceAction: 'optimize',
		});
		expect(promptState.title).toBe('My Title');
		expect(promptState.tags).toEqual(['tag1', 'tag2']);
		expect(promptState.version).toBe('v3');
		expect(promptState.sourceAction).toBe('optimize');
	});

	it('set() defaults metadata fields when not provided', () => {
		promptState.set('text', 'proj', 'pid');
		expect(promptState.title).toBe('');
		expect(promptState.tags).toEqual([]);
		expect(promptState.version).toBe('');
		expect(promptState.sourceAction).toBeNull();
	});

	it('set() accepts reiterate sourceAction', () => {
		promptState.set('text', 'proj', 'pid', { sourceAction: 'reiterate' });
		expect(promptState.sourceAction).toBe('reiterate');
	});

	it('clear() resets all metadata fields', () => {
		promptState.set('text', 'proj', 'pid', {
			title: 'Title',
			tags: ['tag'],
			version: 'v1',
			sourceAction: 'reiterate',
		});
		promptState.clear();
		expect(promptState.title).toBe('');
		expect(promptState.tags).toEqual([]);
		expect(promptState.version).toBe('');
		expect(promptState.sourceAction).toBeNull();
	});
});
