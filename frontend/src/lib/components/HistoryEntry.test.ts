import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

// Mock bits-ui Tooltip primitives to avoid Provider context requirement.
// Each primitive becomes a simple passthrough that renders its children.
vi.mock('bits-ui', async () => {
	const { default: Passthrough } = await import('./ui/__test__/Passthrough.svelte');
	return {
		Tooltip: {
			Root: Passthrough,
			Trigger: Passthrough,
			Portal: Passthrough,
			Content: Passthrough,
			Arrow: Passthrough,
		},
	};
});

// Mock all store/navigation dependencies
vi.mock('$app/navigation', () => ({
	goto: vi.fn(),
}));

vi.mock('$lib/stores/optimization.svelte', () => ({
	optimizationState: {
		retryOptimization: vi.fn(),
	},
}));

vi.mock('$lib/stores/prompt.svelte', () => ({
	promptState: {
		set: vi.fn(),
	},
}));

vi.mock('$lib/stores/history.svelte', () => ({
	historyState: {
		removeEntry: vi.fn(),
	},
}));

import HistoryEntry from './HistoryEntry.svelte';
import { goto } from '$app/navigation';
import { optimizationState } from '$lib/stores/optimization.svelte';
import { promptState } from '$lib/stores/prompt.svelte';
import { historyState } from '$lib/stores/history.svelte';

const mockItem = (overrides = {}) => ({
	id: 'opt-1',
	created_at: '2024-01-15T10:30:00Z',
	raw_prompt: 'Write a function to sort an array',
	title: 'Array Sorter',
	task_type: 'coding',
	complexity: 'medium',
	project: 'My Project',
	project_id: 'proj-1',
	project_status: null,
	tags: ['sorting', 'algorithm'],
	overall_score: 0.85,
	framework_applied: 'chain-of-thought',
	model_used: 'claude-opus-4-6',
	status: 'completed',
	error_message: null,
	prompt_id: 'prm-1',
	strategy: 'chain-of-thought',
	secondary_frameworks: null,
	version: null,
	...overrides,
});

describe('HistoryEntry', () => {
	beforeEach(() => {
		document.body.innerHTML = '';
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it('renders entry with title', () => {
		render(HistoryEntry, { props: { item: mockItem() } });

		expect(screen.getByTestId('history-entry')).toBeTruthy();
	});

	it('displays task type', () => {
		render(HistoryEntry, { props: { item: mockItem() } });

		expect(screen.getByTestId('history-entry-task-type').textContent?.trim()).toBe('coding');
	});

	it('displays strategy', () => {
		render(HistoryEntry, { props: { item: mockItem() } });

		expect(screen.getByTestId('history-entry-strategy').textContent?.trim()).toBe(
			'chain-of-thought',
		);
	});

	it('displays score badge', () => {
		render(HistoryEntry, { props: { item: mockItem() } });

		const score = screen.getByTestId('history-entry-score');
		expect(score).toBeTruthy();
		// normalizeScore(0.85) = Math.round(0.85 * 100) = 85
		expect(score.textContent?.trim()).toBe('85');
	});

	it('displays project name as link when project_id exists', () => {
		render(HistoryEntry, { props: { item: mockItem() } });

		const projectEl = screen.getByTestId('history-entry-project');
		expect(projectEl.textContent?.trim()).toBe('My Project');
		expect(projectEl.tagName.toLowerCase()).toBe('a');
		expect(projectEl.getAttribute('href')).toBe('/projects/proj-1');
	});

	it('displays project name as span when no project_id', () => {
		render(HistoryEntry, {
			props: { item: mockItem({ project: 'Legacy', project_id: null }) },
		});

		const projectEl = screen.getByTestId('history-entry-project');
		expect(projectEl.tagName.toLowerCase()).toBe('span');
	});

	it('displays tags', () => {
		render(HistoryEntry, { props: { item: mockItem() } });

		const chips = document.querySelectorAll('.tag-chip');
		expect(chips.length).toBe(2);
		expect(chips[0].textContent).toBe('#sorting');
		expect(chips[1].textContent).toBe('#algorithm');
	});

	it('shows +N for overflow tags', () => {
		render(HistoryEntry, {
			props: { item: mockItem({ tags: ['a', 'b', 'c', 'd'] }) },
		});

		const chips = document.querySelectorAll('.tag-chip');
		expect(chips.length).toBe(2);
		expect(document.body.textContent).toContain('+2');
	});

	it('shows raw_prompt preview when no project or tags', () => {
		render(HistoryEntry, {
			props: { item: mockItem({ project: null, project_id: null, tags: [] }) },
		});

		expect(document.body.textContent).toContain('Write a function to sort an array');
	});

	it('hides score for error status', () => {
		render(HistoryEntry, {
			props: { item: mockItem({ status: 'error', overall_score: null }) },
		});

		expect(screen.queryByTestId('history-entry-score')).toBeNull();
	});

	it('shows archived badge for archived project', () => {
		render(HistoryEntry, {
			props: { item: mockItem({ project_status: 'archived' }) },
		});

		expect(document.body.textContent).toContain('archived');
	});

	describe('delete flow', () => {
		it('shows delete confirmation on delete click', async () => {
			render(HistoryEntry, { props: { item: mockItem() } });

			const deleteBtn = screen.getByTestId('delete-entry-btn');
			await fireEvent.click(deleteBtn);

			expect(screen.getByTestId('confirm-delete-btn')).toBeTruthy();
			expect(screen.getByTestId('cancel-delete-btn')).toBeTruthy();
			expect(document.body.textContent).toContain('Delete this entry?');
		});

		it('confirms delete calls removeEntry', async () => {
			vi.mocked(historyState.removeEntry).mockResolvedValue(true);
			render(HistoryEntry, { props: { item: mockItem() } });

			await fireEvent.click(screen.getByTestId('delete-entry-btn'));
			await fireEvent.click(screen.getByTestId('confirm-delete-btn'));

			expect(historyState.removeEntry).toHaveBeenCalledWith('opt-1');
		});

		it('cancel hides confirmation', async () => {
			render(HistoryEntry, { props: { item: mockItem() } });

			await fireEvent.click(screen.getByTestId('delete-entry-btn'));
			expect(screen.getByTestId('confirm-delete-btn')).toBeTruthy();

			await fireEvent.click(screen.getByTestId('cancel-delete-btn'));
			expect(screen.queryByTestId('confirm-delete-btn')).toBeNull();
		});
	});

	describe('re-forge action', () => {
		it('calls retryOptimization and navigates home', async () => {
			render(HistoryEntry, { props: { item: mockItem() } });

			await fireEvent.click(screen.getByTestId('reforge-btn'));

			expect(optimizationState.retryOptimization).toHaveBeenCalledWith(
				'opt-1',
				'Write a function to sort an array',
			);
			expect(goto).toHaveBeenCalledWith('/');
		});
	});

	describe('iterate (edit) action', () => {
		it('sets prompt state and navigates home', async () => {
			render(HistoryEntry, { props: { item: mockItem() } });

			await fireEvent.click(screen.getByTestId('iterate-btn'));

			expect(promptState.set).toHaveBeenCalledWith(
				'Write a function to sort an array',
				'My Project',
				'prm-1',
				expect.objectContaining({
					title: 'Array Sorter',
					tags: ['sorting', 'algorithm'],
					sourceAction: 'optimize',
				}),
			);
			expect(goto).toHaveBeenCalledWith('/');
		});

		it('clears project/promptId for archived projects', async () => {
			render(HistoryEntry, {
				props: { item: mockItem({ project_status: 'archived' }) },
			});

			await fireEvent.click(screen.getByTestId('iterate-btn'));

			expect(promptState.set).toHaveBeenCalledWith(
				'Write a function to sort an array',
				'',
				'',
				expect.objectContaining({ sourceAction: 'optimize' }),
			);
		});
	});
});
