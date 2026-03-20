import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

// Mock d3 to avoid DOM rendering issues in jsdom
vi.mock('d3', () => ({
  select: vi.fn(() => ({
    selectAll: vi.fn().mockReturnThis(),
    data: vi.fn().mockReturnThis(),
    join: vi.fn().mockReturnThis(),
    attr: vi.fn().mockReturnThis(),
    text: vi.fn().mockReturnThis(),
    append: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
    call: vi.fn().mockReturnThis(),
    node: vi.fn(() => null),
    remove: vi.fn().mockReturnThis(),
    select: vi.fn().mockReturnThis(),
  })),
  zoom: vi.fn(() => ({
    scaleExtent: vi.fn().mockReturnThis(),
    translateExtent: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
  })),
  arc: vi.fn(() => vi.fn(() => 'M0,0')),
  zoomIdentity: { k: 1, x: 0, y: 0 },
}));

// Mock $app/environment — browser = false keeps the render path safe
vi.mock('$app/environment', () => ({ browser: false }));

vi.mock('$lib/api/patterns', () => ({
  getGraph: vi.fn().mockResolvedValue({ families: [], edges: [], center: { total_families: 0, total_patterns: 0, total_optimizations: 0 } }),
}));

import RadialMindmap from './RadialMindmap.svelte';
import { patternsStore } from '$lib/stores/patterns.svelte';

describe('RadialMindmap', () => {
  beforeEach(() => {
    patternsStore._reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(RadialMindmap);
    expect(container.querySelector('.mindmap-container')).toBeInTheDocument();
  });

  it('shows empty state when graph has no families', () => {
    patternsStore.graph = { families: [], edges: [], center: { total_families: 0, total_patterns: 0, total_optimizations: 0 } };
    patternsStore.graphLoaded = true;
    render(RadialMindmap);
    expect(screen.getByText(/No patterns yet/)).toBeInTheDocument();
  });

  it('shows error state when graphError is set', () => {
    patternsStore.graphError = 'Network error';
    patternsStore.graphLoaded = true;
    render(RadialMindmap);
    expect(screen.getByText(/Error loading graph/)).toBeInTheDocument();
  });
});
