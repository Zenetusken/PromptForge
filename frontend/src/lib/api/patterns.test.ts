import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { matchPattern, getPatternGraph, listFamilies, getFamilyDetail, renameFamily, searchPatterns, getPatternStats } from './patterns';
import { mockFetch, mockPatternFamily, mockMetaPattern } from '../test-utils';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('matchPattern - URL and method', () => {
  it('sends POST to /patterns/match with prompt_text in body', async () => {
    const mock = mockFetch([{
      match: '/patterns/match',
      response: { match: null },
    }]);
    await matchPattern('hello world');
    const [url, opts] = mock.mock.calls[0];
    expect(url).toContain('/patterns/match');
    expect((opts as RequestInit).method).toBe('POST');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.prompt_text).toBe('hello world');
  });

  it('returns null match when no family matches', async () => {
    mockFetch([{ match: '/patterns/match', response: { match: null } }]);
    const result = await matchPattern('something unrelated');
    expect(result.match).toBeNull();
  });
});

describe('getPatternGraph - with familyId', () => {
  it('appends family_id query param when provided', async () => {
    const mock = mockFetch([{
      match: '/patterns/graph',
      response: { center: { total_families: 1, total_patterns: 0, total_optimizations: 0 }, families: [], edges: [] },
    }]);
    await getPatternGraph('fam-1');
    const [url] = mock.mock.calls[0];
    expect(url).toContain('family_id=fam-1');
  });

  it('does not append query param when familyId omitted', async () => {
    const mock = mockFetch([{
      match: '/patterns/graph',
      response: { center: { total_families: 0, total_patterns: 0, total_optimizations: 0 }, families: [], edges: [] },
    }]);
    await getPatternGraph();
    const [url] = mock.mock.calls[0];
    expect(url).not.toContain('family_id');
  });

  it('returns families and edges arrays', async () => {
    const family = { ...mockPatternFamily(), meta_patterns: [mockMetaPattern()] };
    mockFetch([{
      match: '/patterns/graph',
      response: {
        center: { total_families: 1, total_patterns: 1, total_optimizations: 5 },
        families: [family],
        edges: [{ from: 'fam-1', to: 'fam-2', weight: 0.6 }],
      },
    }]);
    const graph = await getPatternGraph();
    expect(graph.families).toHaveLength(1);
    expect(graph.edges).toHaveLength(1);
    expect(graph.edges[0].weight).toBe(0.6);
  });
});

describe('listFamilies - params', () => {
  it('appends offset, limit, and domain params', async () => {
    const mock = mockFetch([{
      match: '/patterns/families',
      response: { total: 0, count: 0, offset: 10, has_more: false, next_offset: null, items: [] },
    }]);
    await listFamilies({ offset: 10, limit: 5, domain: 'backend' });
    const [url] = mock.mock.calls[0];
    expect(url).toContain('offset=10');
    expect(url).toContain('limit=5');
    expect(url).toContain('domain=backend');
  });

  it('does not append params when none provided', async () => {
    const mock = mockFetch([{
      match: '/patterns/families',
      response: { total: 0, count: 0, offset: 0, has_more: false, next_offset: null, items: [] },
    }]);
    await listFamilies();
    const [url] = mock.mock.calls[0];
    expect(url).not.toContain('?');
  });
});

describe('getFamilyDetail - URL construction', () => {
  it('calls GET /patterns/families/:id', async () => {
    const detail = { ...mockPatternFamily({ id: 'fam-42' }), updated_at: null, meta_patterns: [], optimizations: [] };
    const mock = mockFetch([{ match: '/patterns/families/fam-42', response: detail }]);
    const result = await getFamilyDetail('fam-42');
    expect(result.id).toBe('fam-42');
    const [url] = mock.mock.calls[0];
    expect(url).toContain('/patterns/families/fam-42');
  });
});

describe('renameFamily - URL and body', () => {
  it('sends PATCH to /patterns/families/:id with intent_label', async () => {
    const mock = mockFetch([{ match: '/patterns/families/fam-1', response: { id: 'fam-1', intent_label: 'Renamed' } }]);
    await renameFamily('fam-1', 'Renamed');
    const [url, opts] = mock.mock.calls[0];
    expect(url).toContain('/patterns/families/fam-1');
    expect((opts as RequestInit).method).toBe('PATCH');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.intent_label).toBe('Renamed');
  });
});

describe('searchPatterns - URL construction', () => {
  it('encodes query and appends top_k', async () => {
    const mock = mockFetch([{ match: '/patterns/search', response: [] }]);
    await searchPatterns('hello world', 10);
    const [url] = mock.mock.calls[0];
    expect(url).toContain('q=hello%20world');
    expect(url).toContain('top_k=10');
  });

  it('uses default top_k=5 when not specified', async () => {
    const mock = mockFetch([{ match: '/patterns/search', response: [] }]);
    await searchPatterns('test');
    const [url] = mock.mock.calls[0];
    expect(url).toContain('top_k=5');
  });

  it('returns array of SearchResult items', async () => {
    mockFetch([{
      match: '/patterns/search',
      response: [
        { type: 'family', id: 'fam-1', label: 'API patterns', score: 0.9, domain: 'backend' },
        { type: 'pattern', id: 'mp-1', label: 'Error handling', score: 0.8, family_id: 'fam-1' },
      ],
    }]);
    const results = await searchPatterns('api');
    expect(results).toHaveLength(2);
    expect(results[0].type).toBe('family');
    expect(results[1].type).toBe('pattern');
  });
});

describe('getPatternStats - URL', () => {
  it('calls GET /patterns/stats', async () => {
    const mock = mockFetch([{
      match: '/patterns/stats',
      response: { total_families: 3, total_patterns: 7, total_optimizations: 15, domain_distribution: { backend: 2, frontend: 1 } },
    }]);
    const stats = await getPatternStats();
    expect(stats.domain_distribution).toEqual({ backend: 2, frontend: 1 });
    const [url] = mock.mock.calls[0];
    expect(url).toContain('/patterns/stats');
  });
});
