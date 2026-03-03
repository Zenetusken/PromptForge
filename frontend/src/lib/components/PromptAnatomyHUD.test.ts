import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import PromptAnatomyHUD from './PromptAnatomyHUD.svelte';

// Mock promptParser for SECTION_COLORS
vi.mock('$lib/utils/promptParser', () => ({
	SECTION_COLORS: {
		role: 'neon-purple',
		context: 'neon-cyan',
		steps: 'neon-green',
		constraints: 'neon-red',
		examples: 'neon-yellow',
		output: 'neon-blue',
		task: 'neon-orange',
		other: 'text-dim',
	},
}));

const SECTIONS = [
	{ label: 'Role', lineNumber: 1, type: 'role' },
	{ label: 'Context', lineNumber: 3, type: 'context' },
	{ label: 'Steps', lineNumber: 8, type: 'steps' },
];

const VARIABLES = [
	{ name: 'user', occurrences: 3 },
	{ name: 'topic', occurrences: 1 },
];

describe('PromptAnatomyHUD', () => {
	it('renders empty state when no data', () => {
		render(PromptAnatomyHUD, { props: { sections: [], variables: [] } });
		expect(screen.getByText('No structure detected')).toBeTruthy();
	});

	it('renders sections with labels', () => {
		render(PromptAnatomyHUD, { props: { sections: SECTIONS, variables: [] } });
		expect(screen.getByText('Role')).toBeTruthy();
		expect(screen.getByText('Context')).toBeTruthy();
		expect(screen.getByText('Steps')).toBeTruthy();
	});

	it('renders variable chips with occurrence count', () => {
		render(PromptAnatomyHUD, { props: { sections: [], variables: VARIABLES } });
		expect(screen.getByText('{{user}}')).toBeTruthy();
		expect(screen.getByText('×3')).toBeTruthy();
		expect(screen.getByText('{{topic}}')).toBeTruthy();
	});

	it('does not render ×N for single occurrence', () => {
		render(PromptAnatomyHUD, {
			props: { sections: [], variables: [{ name: 'single', occurrences: 1 }] },
		});
		expect(screen.getByText('{{single}}')).toBeTruthy();
		expect(screen.queryByText('×1')).toBeNull();
	});

	it('renders summary bar with counts', () => {
		render(PromptAnatomyHUD, { props: { sections: SECTIONS, variables: VARIABLES } });
		expect(screen.getByText('3 sections · 2 vars')).toBeTruthy();
	});

	it('calls onjumpline in compose mode', async () => {
		const jumpFn = vi.fn();
		render(PromptAnatomyHUD, {
			props: { sections: SECTIONS, variables: [], mode: 'compose', onjumpline: jumpFn },
		});

		const roleButton = screen.getByRole('button', { name: /Role.*line 1/i });
		await fireEvent.click(roleButton);
		expect(jumpFn).toHaveBeenCalledWith(1);
	});

	it('does not render buttons in review mode', () => {
		render(PromptAnatomyHUD, {
			props: { sections: SECTIONS, variables: [], mode: 'review' },
		});
		const buttons = screen.queryAllByRole('button');
		expect(buttons.length).toBe(0);
	});

	it('renders data-testid on non-empty', () => {
		render(PromptAnatomyHUD, { props: { sections: SECTIONS, variables: [] } });
		expect(screen.getByTestId('prompt-anatomy-hud')).toBeTruthy();
	});
});
