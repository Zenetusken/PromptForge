import { describe, it, expect, afterEach, vi } from 'vitest';
import { getTaxonomyTree, getTaxonomyStats, getTaxonomyNode, triggerRecluster } from './taxonomy';
import { mockFetch } from '../test-utils';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('getTaxonomyTree', () => {
  it('calls GET /taxonomy/tree and unwraps nodes', async () => {
    const nodes = [
      { id: 'n1', label: 'Root', parent_id: null, state: 'confirmed' },
      { id: 'n2', label: 'Child', parent_id: 'n1', state: 'candidate' },
    ];
    mockFetch([{ match: '/taxonomy/tree', response: { nodes } }]);
    const result = await getTaxonomyTree();
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('n1');
    expect(result[1].parent_id).toBe('n1');
  });

  it('passes min_persistence query param when provided', async () => {
    const mock = mockFetch([{ match: '/taxonomy/tree', response: { nodes: [] } }]);
    await getTaxonomyTree(0.5);
    const [url] = mock.mock.calls[0];
    expect(url).toContain('min_persistence=0.5');
  });

  it('omits query param when min_persistence is undefined', async () => {
    const mock = mockFetch([{ match: '/taxonomy/tree', response: { nodes: [] } }]);
    await getTaxonomyTree();
    const [url] = mock.mock.calls[0];
    expect(url).not.toContain('min_persistence');
  });
});

describe('getTaxonomyStats', () => {
  it('calls GET /taxonomy/stats and returns stats', async () => {
    const stats = {
      q_system: 0.85,
      q_coherence: 0.9,
      q_separation: 0.8,
      q_coverage: 0.75,
      q_dbcv: 0.7,
      nodes: { confirmed: 5, candidate: 2, retired: 1, max_depth: 3, leaf_count: 4 },
      last_warm_path: '2026-03-20T12:00:00Z',
      last_cold_path: null,
      q_history: [],
    };
    mockFetch([{ match: '/taxonomy/stats', response: stats }]);
    const result = await getTaxonomyStats();
    expect(result.q_system).toBe(0.85);
    expect(result.nodes.confirmed).toBe(5);
  });
});

describe('getTaxonomyNode', () => {
  it('calls GET /taxonomy/node/:id', async () => {
    const node = {
      id: 'n1', label: 'Test', parent_id: null, state: 'confirmed',
      persistence: 0.9, coherence: 0.8, separation: 0.85, stability: 0.7,
      member_count: 10, usage_count: 5, color_hex: '#a855f7',
      umap_x: 1.0, umap_y: 2.0, umap_z: 3.0,
      children: [], families: [],
    };
    const mock = mockFetch([{ match: '/taxonomy/node/n1', response: node }]);
    const result = await getTaxonomyNode('n1');
    expect(result.id).toBe('n1');
    expect(result.label).toBe('Test');
    const [url] = mock.mock.calls[0];
    expect(url).toContain('/taxonomy/node/n1');
  });
});

describe('triggerRecluster', () => {
  it('sends POST to /taxonomy/recluster', async () => {
    const mock = mockFetch([{
      match: '/taxonomy/recluster',
      response: { status: 'completed', message: 'Recluster done', q_system: 0.88 },
    }]);
    const result = await triggerRecluster();
    expect(result.status).toBe('completed');
    const [, opts] = mock.mock.calls[0];
    expect((opts as RequestInit).method).toBe('POST');
  });

  it('passes min_persistence in body when provided', async () => {
    const mock = mockFetch([{
      match: '/taxonomy/recluster',
      response: { status: 'completed', message: 'ok' },
    }]);
    await triggerRecluster(0.3);
    const [, opts] = mock.mock.calls[0];
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.min_persistence).toBe(0.3);
  });
});
