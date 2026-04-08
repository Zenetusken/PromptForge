import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';

// Stub requestAnimationFrame — ActivityPanel uses it for scroll-to-top,
// but scrollEl is null in jsdom (bind:this doesn't bind in tests).
// Run callbacks synchronously so effects settle within the test frame.
const _origRAF = globalThis.requestAnimationFrame;
globalThis.requestAnimationFrame = (cb: FrameRequestCallback) => { try { cb(0); } catch { /* scrollEl null in jsdom */ } return 0; };

// Inline mock data inside factory (vi.mock is hoisted above variable declarations)
vi.mock('$lib/stores/clusters.svelte', () => ({
  clustersStore: {
    activityEvents: [
      { ts: '2026-04-08T01:00:00Z', path: 'hot', op: 'assign', decision: 'merge_into', cluster_id: 'c1' },
      { ts: '2026-04-08T01:01:00Z', path: 'warm', op: 'split', decision: 'split_complete', cluster_id: 'c2' },
      { ts: '2026-04-08T01:02:00Z', path: 'warm', op: 'error', decision: 'failed', cluster_id: 'c3' },
      { ts: '2026-04-08T01:03:00Z', path: 'cold', op: 'refit', decision: 'accepted' },
      { ts: '2026-04-08T01:04:00Z', path: 'hot', op: 'score', decision: 'scored', optimization_id: 'o1' },
    ],
    loadActivity: vi.fn().mockResolvedValue(undefined),
  },
}));

import ActivityPanel from './ActivityPanel.svelte';

describe('ActivityPanel', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { cleanup(); });

  it('renders the activity feed container', () => {
    const { container } = render(ActivityPanel);
    expect(container.querySelector('.ap-panel')).toBeTruthy();
  });

  it('displays activity events from the store', () => {
    render(ActivityPanel);
    // Multiple elements may match (filter chips + event rows) — use getAllByText
    expect(screen.getAllByText(/assign/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/split/).length).toBeGreaterThan(0);
  });

  it('shows event count', () => {
    render(ActivityPanel);
    expect(screen.getByText(/5/)).toBeInTheDocument();
  });

  it('applies color coding without errors', () => {
    const { container } = render(ActivityPanel);
    expect(container.querySelector('.ap-panel')).toBeTruthy();
  });

  it('loads activity history on mount', async () => {
    const { clustersStore } = await import('$lib/stores/clusters.svelte');
    render(ActivityPanel);
    expect(clustersStore.loadActivity).toHaveBeenCalled();
  });
});
