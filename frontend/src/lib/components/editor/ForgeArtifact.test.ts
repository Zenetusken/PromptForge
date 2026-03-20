import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import { mockOptimizationResult } from '$lib/test-utils';

vi.mock('$lib/api/client', () => ({
  submitFeedback: vi.fn().mockResolvedValue({}),
  getOptimization: vi.fn().mockResolvedValue(null),
}));

import ForgeArtifact from './ForgeArtifact.svelte';
import { forgeStore } from '$lib/stores/forge.svelte';
import { refinementStore } from '$lib/stores/refinement.svelte';

describe('ForgeArtifact', () => {
  beforeEach(() => {
    forgeStore._reset();
    refinementStore._reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(ForgeArtifact);
    expect(container.querySelector('.forge-artifact')).toBeInTheDocument();
  });

  it('shows empty state message when no result', () => {
    render(ForgeArtifact);
    expect(screen.getByText(/No result yet/)).toBeInTheDocument();
  });

  it('shows optimized prompt text when result is set', () => {
    forgeStore.result = mockOptimizationResult() as any;
    render(ForgeArtifact);
    expect(screen.getByText('OPTIMIZED PROMPT')).toBeInTheDocument();
  });
});
