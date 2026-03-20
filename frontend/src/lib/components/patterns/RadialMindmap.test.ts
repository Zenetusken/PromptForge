import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';

// Build a more complete D3 mock that lets code paths execute further.
// We track event handlers so we can call them in tests.
const _eventHandlers: Record<string, Function> = {};

function makeSel(): any {
  const sel: any = {
    selectAll: vi.fn().mockReturnThis(),
    data: vi.fn().mockReturnThis(),
    join: vi.fn().mockReturnThis(),
    attr: vi.fn().mockReturnThis(),
    text: vi.fn().mockReturnThis(),
    remove: vi.fn().mockReturnThis(),
    select: vi.fn(() => makeSel()),
    on: vi.fn((event: string, handler: Function) => {
      _eventHandlers[event] = handler;
      return sel;
    }),
    call: vi.fn().mockReturnThis(),
    node: vi.fn(() => null),
    append: vi.fn(() => makeSel()),
  };
  return sel;
}

vi.mock('d3', () => ({
  select: vi.fn(() => makeSel()),
  zoom: vi.fn(() => ({
    scaleExtent: vi.fn().mockReturnThis(),
    translateExtent: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
  })),
  arc: vi.fn(() => vi.fn(() => 'M0,0')),
  zoomIdentity: { k: 1, x: 0, y: 0 },
}));

// Mock $app/environment — browser = false keeps the render path safe in jsdom
// (ResizeObserver and D3 internals not available in jsdom)
vi.mock('$app/environment', () => ({ browser: false }));

vi.mock('$lib/api/patterns', () => ({
  getGraph: vi.fn().mockResolvedValue({
    families: [],
    edges: [],
    center: { total_families: 0, total_patterns: 0, total_optimizations: 0 },
  }),
}));

import RadialMindmap from './RadialMindmap.svelte';
import { patternsStore } from '$lib/stores/patterns.svelte';
import type { GraphFamily } from '$lib/api/patterns';

function makeFamily(overrides: Partial<GraphFamily> = {}): GraphFamily {
  return {
    id: 'fam-1',
    intent_label: 'Test family label',
    domain: 'backend',
    task_type: 'coding',
    usage_count: 5,
    member_count: 3,
    avg_score: 8.0,
    created_at: null,
    meta_patterns: [],
    ...overrides,
  };
}

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

  it('calls loadGraph when not loaded', () => {
    const loadGraph = vi.spyOn(patternsStore, 'loadGraph').mockImplementation(async () => {});
    patternsStore.graphLoaded = false;
    render(RadialMindmap);
    expect(loadGraph).toHaveBeenCalled();
  });

  it('renders svg element when graph has families (browser=false shows svg shell)', () => {
    patternsStore.graph = {
      families: [makeFamily()],
      edges: [],
      center: { total_families: 1, total_patterns: 2, total_optimizations: 3 },
    };
    patternsStore.graphLoaded = true;
    const { container } = render(RadialMindmap);
    // With browser=false the D3 render doesn't fire, but the SVG element is still in the template
    expect(container.querySelector('.mindmap-container')).toBeInTheDocument();
    // The SVG element should exist in the template since families.length > 0 and no error
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('renders with graph families and edges (structure test)', () => {
    patternsStore.graph = {
      families: [
        makeFamily({ id: 'fam-1', domain: 'backend' }),
        makeFamily({ id: 'fam-2', domain: 'frontend', intent_label: 'UI patterns' }),
      ],
      edges: [{ from: 'fam-1', to: 'fam-2', weight: 0.8 }],
      center: { total_families: 2, total_patterns: 5, total_optimizations: 10 },
    };
    patternsStore.graphLoaded = true;
    const { container } = render(RadialMindmap);
    expect(container.querySelector('.mindmap-container')).toBeInTheDocument();
  });

  it('shows svg when families exist (not the empty state)', () => {
    patternsStore.graph = {
      families: [makeFamily({ intent_label: 'This is a very long label that should be truncated' })],
      edges: [],
      center: { total_families: 1, total_patterns: 1, total_optimizations: 1 },
    };
    patternsStore.graphLoaded = true;
    render(RadialMindmap);
    // Not the empty state
    expect(screen.queryByText(/No patterns yet/)).not.toBeInTheDocument();
  });

  it('renders without error when families span multiple domains', () => {
    patternsStore.graph = {
      families: [
        makeFamily({ id: 'f1', domain: 'backend' }),
        makeFamily({ id: 'f2', domain: 'frontend' }),
        makeFamily({ id: 'f3', domain: 'database' }),
        makeFamily({ id: 'f4', domain: 'security' }),
      ],
      edges: [],
      center: { total_families: 4, total_patterns: 8, total_optimizations: 20 },
    };
    patternsStore.graphLoaded = true;
    const { container } = render(RadialMindmap);
    expect(container.querySelector('.mindmap-container')).toBeInTheDocument();
  });

  it('renders without error when families have meta_patterns', () => {
    patternsStore.graph = {
      families: [makeFamily({
        meta_patterns: [
          { id: 'mp-1', pattern_text: 'Use step-by-step instructions', source_count: 3 },
          { id: 'mp-2', pattern_text: 'Add examples for clarity', source_count: 2 },
        ],
      })],
      edges: [],
      center: { total_families: 1, total_patterns: 2, total_optimizations: 3 },
    };
    patternsStore.graphLoaded = true;
    const { container } = render(RadialMindmap);
    expect(container.querySelector('.mindmap-container')).toBeInTheDocument();
  });

  it('does not call loadGraph when already loaded', () => {
    const loadGraph = vi.spyOn(patternsStore, 'loadGraph').mockImplementation(async () => {});
    patternsStore.graphLoaded = true;
    patternsStore.graph = { families: [], edges: [], center: { total_families: 0, total_patterns: 0, total_optimizations: 0 } };
    render(RadialMindmap);
    expect(loadGraph).not.toHaveBeenCalled();
  });
});
