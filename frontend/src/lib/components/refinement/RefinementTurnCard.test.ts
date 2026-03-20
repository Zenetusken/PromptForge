import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import RefinementTurnCard from './RefinementTurnCard.svelte';
import { mockRefinementTurn } from '$lib/test-utils';

describe('RefinementTurnCard', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const turn = mockRefinementTurn();
    const { container } = render(RefinementTurnCard, {
      props: {
        turn: turn as any,
        isExpanded: false,
        isSelected: false,
        onToggle: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(container.querySelector('.turn-card')).toBeInTheDocument();
  });

  it('renders the version badge', () => {
    const turn = mockRefinementTurn({ version: 1 });
    render(RefinementTurnCard, {
      props: {
        turn: turn as any,
        isExpanded: false,
        isSelected: false,
        onToggle: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(screen.getByText('v1')).toBeInTheDocument();
  });

  it('renders the refinement request text', () => {
    const turn = mockRefinementTurn({ refinement_request: 'Make it more concise' });
    render(RefinementTurnCard, {
      props: {
        turn: turn as any,
        isExpanded: false,
        isSelected: false,
        onToggle: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(screen.getByText('Make it more concise')).toBeInTheDocument();
  });
});
