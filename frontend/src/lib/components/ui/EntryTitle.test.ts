import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import EntryTitle from './EntryTitle.svelte';

beforeEach(() => {
	document.body.innerHTML = '';
});

describe('EntryTitle', () => {
	it('renders title text when title is provided', () => {
		render(EntryTitle, { props: { title: 'My Prompt Title' } });
		const el = screen.getByTestId('entry-title');
		expect(el.textContent).toBe('My Prompt Title');
	});

	it('renders placeholder for null title', () => {
		render(EntryTitle, { props: { title: null } });
		const el = screen.getByTestId('entry-title-placeholder');
		expect(el.textContent).toBe('Untitled');
	});

	it('renders placeholder for undefined title', () => {
		render(EntryTitle, { props: { title: undefined } });
		const el = screen.getByTestId('entry-title-placeholder');
		expect(el.textContent).toBe('Untitled');
	});

	it('renders placeholder for empty string title', () => {
		render(EntryTitle, { props: { title: '' } });
		const el = screen.getByTestId('entry-title-placeholder');
		expect(el.textContent).toBe('Untitled');
	});

	it('truncates title when maxLength is set', () => {
		render(EntryTitle, { props: { title: 'A very long title that should be truncated', maxLength: 15 } });
		const el = screen.getByTestId('entry-title');
		expect(el.textContent).toBe('A very long tit...');
	});

	it('does not truncate title when maxLength is not set', () => {
		const longTitle = 'A very long title that should not be truncated';
		render(EntryTitle, { props: { title: longTitle } });
		const el = screen.getByTestId('entry-title');
		expect(el.textContent).toBe(longTitle);
	});

	it('uses custom placeholder text', () => {
		render(EntryTitle, { props: { title: null, placeholder: 'No name' } });
		const el = screen.getByTestId('entry-title-placeholder');
		expect(el.textContent).toBe('No name');
	});

	it('applies class prop to title span', () => {
		render(EntryTitle, { props: { title: 'Test', class: 'truncate text-sm' } });
		const el = screen.getByTestId('entry-title');
		expect(el.className).toContain('truncate');
		expect(el.className).toContain('text-sm');
	});

	it('applies class prop plus italic/dim to placeholder span', () => {
		render(EntryTitle, { props: { title: null, class: 'truncate' } });
		const el = screen.getByTestId('entry-title-placeholder');
		expect(el.className).toContain('truncate');
		expect(el.className).toContain('italic');
		expect(el.className).toContain('text-text-dim');
	});

	it('does not add italic or text-text-dim when title exists', () => {
		render(EntryTitle, { props: { title: 'Present' } });
		const el = screen.getByTestId('entry-title');
		expect(el.className).not.toContain('italic');
		expect(el.className).not.toContain('text-text-dim');
	});
});
