import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';

import TierBadge from './TierBadge.svelte';

// Mock the tooltip action (requires DOM directive support)
vi.mock('$lib/actions/tooltip', () => ({
  tooltip: () => ({ destroy() {} }),
}));

describe('TierBadge', () => {
  afterEach(() => { cleanup(); });

  // --- Label resolution ---

  it('shows CLI for internal tier with cli provider', () => {
    render(TierBadge, { props: { tier: 'internal', provider: 'claude_cli' } });
    expect(screen.getByText('CLI')).toBeInTheDocument();
  });

  it('shows API for internal tier with api provider', () => {
    render(TierBadge, { props: { tier: 'internal', provider: 'anthropic_api' } });
    expect(screen.getByText('API')).toBeInTheDocument();
  });

  it('shows INTERNAL for internal tier without provider', () => {
    render(TierBadge, { props: { tier: 'internal' } });
    expect(screen.getByText('INTERNAL')).toBeInTheDocument();
  });

  it('shows SAMPLING for sampling tier', () => {
    render(TierBadge, { props: { tier: 'sampling' } });
    expect(screen.getByText('SAMPLING')).toBeInTheDocument();
  });

  it('shows PASSTHROUGH for passthrough tier', () => {
    render(TierBadge, { props: { tier: 'passthrough' } });
    expect(screen.getByText('PASSTHROUGH')).toBeInTheDocument();
  });

  // --- CSS class application ---

  it('applies tier-internal class', () => {
    const { container } = render(TierBadge, { props: { tier: 'internal' } });
    expect(container.querySelector('.tier-internal')).toBeTruthy();
  });

  it('applies tier-sampling class', () => {
    const { container } = render(TierBadge, { props: { tier: 'sampling' } });
    expect(container.querySelector('.tier-sampling')).toBeTruthy();
  });

  it('applies tier-passthrough class', () => {
    const { container } = render(TierBadge, { props: { tier: 'passthrough' } });
    expect(container.querySelector('.tier-passthrough')).toBeTruthy();
  });

  // --- Degradation indicator ---

  it('shows degraded label with strikethrough when degradedFrom is set', () => {
    const { container } = render(TierBadge, {
      props: { tier: 'internal', degradedFrom: 'sampling' },
    });
    const degraded = container.querySelector('.tier-degraded');
    expect(degraded).toBeTruthy();
    expect(degraded?.textContent).toBe('SAMPLING');
  });

  it('does not show degraded label when degradedFrom is null', () => {
    const { container } = render(TierBadge, {
      props: { tier: 'internal' },
    });
    expect(container.querySelector('.tier-degraded')).toBeNull();
  });

  // --- Accessibility ---

  it('has accessible aria-label without degradation', () => {
    render(TierBadge, { props: { tier: 'sampling' } });
    expect(screen.getByLabelText('Execution tier: SAMPLING')).toBeInTheDocument();
  });

  it('has accessible aria-label with degradation', () => {
    render(TierBadge, { props: { tier: 'passthrough', degradedFrom: 'sampling' } });
    expect(
      screen.getByLabelText('Execution tier: PASSTHROUGH (degraded from sampling)'),
    ).toBeInTheDocument();
  });
});
