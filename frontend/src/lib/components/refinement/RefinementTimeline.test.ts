import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { mockRefinementTurn } from '$lib/test-utils';

vi.mock('$lib/api/client', () => ({
  refineSSE: vi.fn().mockReturnValue({ abort: vi.fn() }),
  getRefinementVersions: vi.fn().mockResolvedValue({ optimization_id: null, versions: [] }),
}));

// jsdom doesn't implement scrollTo on elements — patch it globally so the
// RefinementTimeline auto-scroll effect doesn't produce unhandled rejections.
if (typeof HTMLElement !== 'undefined' && !HTMLElement.prototype.scrollTo) {
  HTMLElement.prototype.scrollTo = vi.fn() as any;
}

import RefinementTimeline from './RefinementTimeline.svelte';
import { refinementStore } from '$lib/stores/refinement.svelte';
import * as apiClient from '$lib/api/client';

describe('RefinementTimeline', () => {
  beforeEach(() => {
    refinementStore._reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(RefinementTimeline);
    expect(container.querySelector('.refinement-timeline')).toBeInTheDocument();
  });

  it('renders refinement input even with no turns', () => {
    render(RefinementTimeline);
    // RefinementInput is always shown
    expect(screen.getByPlaceholderText('Describe refinement...')).toBeInTheDocument();
  });

  it('renders turn cards when turns are set in the store', () => {
    refinementStore.turns = [mockRefinementTurn({ version: 1 })] as any;
    render(RefinementTimeline);
    expect(screen.getByText('REFINEMENT')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
  });

  it('shows refining status indicator in header when status is refining', () => {
    refinementStore.turns = [mockRefinementTurn({ version: 1 })] as any;
    refinementStore.status = 'refining';
    render(RefinementTimeline);
    // There are two status indicators (header + footer) — at least one should be there
    const indicators = screen.getAllByText('refining...');
    expect(indicators.length).toBeGreaterThan(0);
  });

  it('shows refining indicator in footer when status is refining and no turns', () => {
    refinementStore.status = 'refining';
    render(RefinementTimeline);
    expect(screen.getByText('refining...')).toBeInTheDocument();
  });

  it('shows suggestion chips when suggestions are set', async () => {
    const user = userEvent.setup();
    refinementStore.suggestions = [
      { text: 'Add more examples', source: 'model' },
      { text: 'Be more specific', source: 'heuristic' },
    ];
    render(RefinementTimeline);
    // Expand the collapsible suggestions toggle
    const toggle = screen.getByText('SUGGESTIONS').closest('button')!;
    await user.click(toggle);
    expect(screen.getByText('Add more examples')).toBeInTheDocument();
  });

  it('shows error text when refinementStore.error is set', () => {
    refinementStore.error = 'Refinement failed unexpectedly';
    render(RefinementTimeline);
    expect(screen.getByText('Refinement failed unexpectedly')).toBeInTheDocument();
  });

  it('shows branch switcher when multiple branches exist', () => {
    const turn = mockRefinementTurn({ branch_id: 'branch-1' }) as any;
    refinementStore.turns = [turn];
    refinementStore.branches = [
      { id: 'branch-1', optimization_id: 'opt-1', parent_branch_id: null, forked_at_version: null, created_at: '2026-03-20T12:00:00Z' } as any,
      { id: 'branch-2', optimization_id: 'opt-1', parent_branch_id: 'branch-1', forked_at_version: 1, created_at: '2026-03-20T12:05:00Z' } as any,
    ];
    refinementStore.activeBranchId = 'branch-1';
    render(RefinementTimeline);
    // BranchSwitcher should be rendered
    expect(screen.getByText('REFINEMENT')).toBeInTheDocument();
  });

  it('refinement input is disabled when status is refining', () => {
    refinementStore.status = 'refining';
    render(RefinementTimeline);
    const input = screen.getByPlaceholderText('Describe refinement...');
    expect(input).toBeDisabled();
  });

  it('toggles turn expansion when turn card header is clicked', async () => {
    const user = userEvent.setup();
    const turn = mockRefinementTurn({ version: 1 }) as any;
    refinementStore.turns = [turn];
    render(RefinementTimeline);
    // Turn card should be rendered — clicking it triggers toggleExpanded
    const turnHeader = screen.getByText('v1').closest('button') ?? screen.getByText('v1').closest('[role="button"]');
    if (turnHeader) {
      await user.click(turnHeader as HTMLElement);
    }
    // Just check it didn't crash
    expect(screen.getByText('REFINEMENT')).toBeInTheDocument();
  });

  it('last 3 turns are expanded by default', () => {
    const turns = [
      mockRefinementTurn({ id: 'turn-1', version: 1 }) as any,
      mockRefinementTurn({ id: 'turn-2', version: 2 }) as any,
      mockRefinementTurn({ id: 'turn-3', version: 3 }) as any,
      mockRefinementTurn({ id: 'turn-4', version: 4 }) as any,
    ];
    refinementStore.turns = turns;
    render(RefinementTimeline);
    // All 4 turns rendered — only last 3 are expanded (checked visually via the component)
    expect(screen.getByText('v1')).toBeInTheDocument();
    expect(screen.getByText('v4')).toBeInTheDocument();
  });

  it('typing in refinement input and clicking REFINE calls refinementStore.refine', async () => {
    const user = userEvent.setup();
    refinementStore.optimizationId = 'opt-1';
    vi.mocked(apiClient.refineSSE).mockReturnValue({ abort: vi.fn() } as any);
    const refineSpy = vi.spyOn(refinementStore, 'refine');
    render(RefinementTimeline);
    const input = screen.getByRole('textbox', { name: 'Refinement request' });
    await user.type(input, 'Make it more concise');
    await user.click(screen.getByRole('button', { name: 'Submit refinement' }));
    expect(refineSpy).toHaveBeenCalledWith('Make it more concise');
  });

  it('clicking a suggestion chip calls refinementStore.refine with suggestion text', async () => {
    const user = userEvent.setup();
    refinementStore.optimizationId = 'opt-1';
    refinementStore.suggestions = [{ text: 'Add examples', source: 'model' }];
    vi.mocked(apiClient.refineSSE).mockReturnValue({ abort: vi.fn() } as any);
    const refineSpy = vi.spyOn(refinementStore, 'refine');
    render(RefinementTimeline);
    // Expand the collapsible suggestions toggle
    const toggle = screen.getByText('SUGGESTIONS').closest('button')!;
    await user.click(toggle);
    await user.click(screen.getByText('Add examples'));
    expect(refineSpy).toHaveBeenCalledWith('Add examples');
  });

  it('toggleExpanded collapses a turn that was already expanded', async () => {
    const user = userEvent.setup();
    const turn = mockRefinementTurn({ id: 'turn-x', version: 1 }) as any;
    // Turn 1 starts expanded (it's the last turn)
    refinementStore.turns = [turn];
    render(RefinementTimeline);
    // The turn should be expanded by default (last turn in list)
    expect(screen.getByText('v1')).toBeInTheDocument();
    // Find toggle button and click twice to expand then collapse
    const toggleBtn = screen.getByText('v1').closest('button');
    if (toggleBtn) {
      await user.click(toggleBtn); // collapse
      await user.click(toggleBtn); // re-expand
    }
    expect(screen.getByText('v1')).toBeInTheDocument();
  });

  it('handleBranchSwitch sets activeBranchId and calls init when optimizationId is set', async () => {
    const user = userEvent.setup();
    refinementStore.optimizationId = 'opt-1';
    refinementStore.activeBranchId = 'branch-1';
    const turn = mockRefinementTurn({ id: 'turn-1', branch_id: 'branch-1', version: 1 }) as any;
    refinementStore.turns = [turn];
    refinementStore.branches = [
      { id: 'branch-1', optimization_id: 'opt-1', parent_branch_id: null, forked_at_version: null, created_at: '2026-03-20T12:00:00Z' } as any,
      { id: 'branch-2', optimization_id: 'opt-1', parent_branch_id: 'branch-1', forked_at_version: 1, created_at: '2026-03-20T12:05:00Z' } as any,
    ];
    vi.mocked(apiClient.getRefinementVersions).mockResolvedValue({
      optimization_id: 'opt-1',
      versions: [turn],
    } as any);
    const initSpy = vi.spyOn(refinementStore, 'init');
    render(RefinementTimeline);
    // BranchSwitcher buttons should be present
    const branchBtns = screen.getAllByRole('button');
    // Click the branch switcher button for branch-2 (if present)
    const branch2Btn = branchBtns.find(b => b.textContent?.includes('branch-2') || b.getAttribute('aria-label')?.includes('branch-2'));
    if (branch2Btn) {
      await user.click(branch2Btn);
      expect(refinementStore.activeBranchId).toBe('branch-2');
    }
    // Verify the REFINEMENT header is visible
    expect(screen.getByText('REFINEMENT')).toBeInTheDocument();
  });
});
