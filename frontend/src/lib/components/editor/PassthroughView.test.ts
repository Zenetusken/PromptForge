import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

vi.mock('$lib/api/client', () => ({
  savePassthrough: vi.fn().mockResolvedValue({}),
  getOptimization: vi.fn().mockResolvedValue(null),
}));

import PassthroughView from './PassthroughView.svelte';
import { forgeStore } from '$lib/stores/forge.svelte';

describe('PassthroughView', () => {
  beforeEach(() => {
    forgeStore._reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(PassthroughView);
    expect(container.querySelector('.passthrough-view')).toBeInTheDocument();
  });

  it('shows MANUAL PASSTHROUGH header label', () => {
    render(PassthroughView);
    expect(screen.getByText('MANUAL PASSTHROUGH')).toBeInTheDocument();
  });

  it('shows loading state when assembledPrompt is absent', () => {
    render(PassthroughView);
    expect(screen.getByText('Preparing prompt...')).toBeInTheDocument();
  });

  it('shows assembled prompt when forgeStore.assembledPrompt is set', () => {
    forgeStore.assembledPrompt = 'My assembled prompt content';
    render(PassthroughView);
    expect(screen.getByText('My assembled prompt content')).toBeInTheDocument();
  });
});
