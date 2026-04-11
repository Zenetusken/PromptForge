import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import SuggestionChips from './SuggestionChips.svelte';

/** Expand the collapsible SUGGESTIONS toggle so chip buttons become visible. */
async function expandSuggestions(user: ReturnType<typeof userEvent.setup>) {
  const toggle = screen.getByText('SUGGESTIONS').closest('button')!;
  await user.click(toggle);
}

describe('SuggestionChips', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders nothing when suggestions array is empty', () => {
    render(SuggestionChips, { props: { suggestions: [], onSelect: vi.fn() } });
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders a chip for each suggestion (up to 3)', async () => {
    const user = userEvent.setup();
    const suggestions = [
      { text: 'Add examples', source: 'model' },
      { text: 'Be concise', source: 'model' },
      { text: 'Add context', source: 'model' },
    ];
    render(SuggestionChips, { props: { suggestions, onSelect: vi.fn() } });
    await expandSuggestions(user);
    // 1 toggle button + 3 chip buttons
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(4);
  });

  it('shows only the first 3 chips when more are provided', async () => {
    const user = userEvent.setup();
    const suggestions = [
      { text: 'Chip 1', source: 'model' },
      { text: 'Chip 2', source: 'model' },
      { text: 'Chip 3', source: 'model' },
      { text: 'Chip 4', source: 'model' },
    ];
    render(SuggestionChips, { props: { suggestions, onSelect: vi.fn() } });
    await expandSuggestions(user);
    // 1 toggle + 3 visible chips (Chip 4 excluded)
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(4);
    expect(screen.queryByText('Chip 4')).not.toBeInTheDocument();
  });

  it('renders chip text from the "text" field', async () => {
    const user = userEvent.setup();
    const suggestions = [{ text: 'Make it shorter', source: 'model' }];
    render(SuggestionChips, { props: { suggestions, onSelect: vi.fn() } });
    await expandSuggestions(user);
    expect(screen.getByText('Make it shorter')).toBeInTheDocument();
  });

  it('falls back to "action" field if "text" is missing', async () => {
    const user = userEvent.setup();
    const suggestions = [{ action: 'Restructure for clarity', type: 'style' }];
    render(SuggestionChips, { props: { suggestions, onSelect: vi.fn() } });
    await expandSuggestions(user);
    expect(screen.getByText('Restructure for clarity')).toBeInTheDocument();
  });

  it('calls onSelect with chip text on click', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const suggestions = [
      { text: 'Add examples', source: 'model' },
      { text: 'Be concise', source: 'model' },
    ];
    render(SuggestionChips, { props: { suggestions, onSelect } });
    await expandSuggestions(user);
    await user.click(screen.getByText('Add examples'));
    expect(onSelect).toHaveBeenCalledWith('Add examples');
  });

  it('calls onSelect with correct text for the clicked chip', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const suggestions = [
      { text: 'Suggestion A', source: 'model' },
      { text: 'Suggestion B', source: 'model' },
    ];
    render(SuggestionChips, { props: { suggestions, onSelect } });
    await expandSuggestions(user);
    await user.click(screen.getByText('Suggestion B'));
    expect(onSelect).toHaveBeenCalledWith('Suggestion B');
    expect(onSelect).not.toHaveBeenCalledWith('Suggestion A');
  });

  it('renders the chips container with accessible label', async () => {
    const user = userEvent.setup();
    const suggestions = [{ text: 'Try this', source: 'model' }];
    render(SuggestionChips, { props: { suggestions, onSelect: vi.fn() } });
    await expandSuggestions(user);
    expect(screen.getByLabelText('Refinement suggestions')).toBeInTheDocument();
  });

  it('renders a single chip for a single suggestion', async () => {
    const user = userEvent.setup();
    const suggestions = [{ text: 'Just one chip', source: 'model' }];
    render(SuggestionChips, { props: { suggestions, onSelect: vi.fn() } });
    await expandSuggestions(user);
    // 1 toggle + 1 chip
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(2);
    expect(screen.getByText('Just one chip')).toBeInTheDocument();
  });
});
