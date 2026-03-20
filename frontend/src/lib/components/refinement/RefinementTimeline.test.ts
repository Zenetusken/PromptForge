import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import { mockRefinementTurn } from '$lib/test-utils';

vi.mock('$lib/api/client', () => ({
  refineSSE: vi.fn(),
  getRefinementVersions: vi.fn().mockResolvedValue([]),
}));

// jsdom doesn't implement scrollTo on elements — patch it globally so the
// RefinementTimeline auto-scroll effect doesn't produce unhandled rejections.
if (typeof HTMLElement !== 'undefined' && !HTMLElement.prototype.scrollTo) {
  HTMLElement.prototype.scrollTo = vi.fn() as any;
}

import RefinementTimeline from './RefinementTimeline.svelte';
import { refinementStore } from '$lib/stores/refinement.svelte';

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
});
