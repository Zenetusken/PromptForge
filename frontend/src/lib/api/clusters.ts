/**
 * Cluster API client — unified tree, detail, stats, match, templates, recluster.
 *
 * Replaces the separate patterns.ts and taxonomy.ts API clients.
 * All endpoints hit /api/clusters/*.
 */
import { apiFetch } from './client';

// -- Types --

export interface ClusterNode {
  id: string;
  parent_id: string | null;
  label: string;
  state: string;
  domain: string;
  task_type: string;
  persistence: number | null;
  coherence: number | null;
  separation: number | null;
  stability: number | null;
  member_count: number;
  usage_count: number;
  avg_score: number | null;
  color_hex: string | null;
  umap_x: number | null;
  umap_y: number | null;
  umap_z: number | null;
  preferred_strategy: string | null;
  created_at: string | null;
  // Only populated by getClusterDetail
  children?: ClusterNode[];
  breadcrumb?: string[];
}

export interface MetaPatternItem {
  id: string;
  pattern_text: string;
  source_count: number;
}

export interface LinkedOptimization {
  id: string;
  trace_id: string;
  raw_prompt: string;
  intent_label: string | null;
  overall_score: number | null;
  strategy_used: string | null;
  created_at: string | null;
}

export interface ClusterDetail {
  id: string;
  parent_id: string | null;
  label: string;
  state: string;
  domain: string;
  task_type: string;
  member_count: number;
  usage_count: number;
  avg_score: number | null;
  coherence: number | null;
  separation: number | null;
  preferred_strategy: string | null;
  promoted_at: string | null;
  meta_patterns: MetaPatternItem[];
  optimizations: LinkedOptimization[];
  children: ClusterNode[] | null;
  breadcrumb: string[] | null;
}

export interface ClusterStats {
  q_system: number | null;
  q_coherence: number | null;
  q_separation: number | null;
  q_coverage: number | null;
  q_dbcv: number | null;
  total_clusters: number;
  nodes: {
    active: number;
    candidate: number;
    mature: number;
    template: number;
    archived: number;
    max_depth: number;
    leaf_count: number;
  } | null;
  last_warm_path: string | null;
  last_cold_path: string | null;
  warm_path_age: number | null;
  q_history: Array<{
    timestamp: string | null;
    q_system: number | null;
    operations: number;
  }> | null;
  q_sparkline: number[] | null;
}

export interface ClusterMatchResponse {
  match: {
    cluster: {
      id: string;
      label: string;
      domain: string;
      member_count: number;
    };
    meta_patterns: MetaPatternItem[];
    similarity: number;
  } | null;
}

export interface ReclusterResult {
  status: 'completed' | 'skipped';
  reason?: string;
  snapshot_id?: string;
  q_system?: number | null;
  nodes_created?: number;
  nodes_updated?: number;
  umap_fitted?: boolean;
}

// -- API functions --

export async function getClusterTree(minPersistence?: number): Promise<ClusterNode[]> {
  const qs = minPersistence != null ? `?min_persistence=${minPersistence}` : '';
  const resp = await apiFetch<{ nodes: ClusterNode[] }>(`/clusters/tree${qs}`);
  return resp.nodes;
}

export const getClusterStats = () =>
  apiFetch<ClusterStats>('/clusters/stats');

export const getClusterDetail = (clusterId: string) =>
  apiFetch<ClusterDetail>(`/clusters/${encodeURIComponent(clusterId)}`);

export async function getClusterTemplates(params?: { offset?: number; limit?: number }): Promise<{
  total: number;
  count: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
  items: ClusterNode[];
}> {
  const search = new URLSearchParams();
  if (params?.offset != null) search.set('offset', String(params.offset));
  if (params?.limit != null) search.set('limit', String(params.limit));
  const qs = search.toString();
  return apiFetch(`/clusters/templates${qs ? '?' + qs : ''}`);
}

export const matchPattern = (prompt_text: string) =>
  apiFetch<ClusterMatchResponse>('/clusters/match', {
    method: 'POST',
    body: JSON.stringify({ prompt_text }),
  });

export const updateCluster = (clusterId: string, updates: { intent_label?: string; domain?: string; state?: string }) =>
  apiFetch<{ id: string; intent_label: string; domain: string; state: string }>(`/clusters/${encodeURIComponent(clusterId)}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });

export const triggerRecluster = () =>
  apiFetch<ReclusterResult>('/clusters/recluster', {
    method: 'POST',
    body: JSON.stringify({}),
  });

// -- Legacy re-exports for backward compatibility during migration --

/**
 * List clusters (alias for getClusterTree).
 * ClusterNavigator uses a paginated list — for now falls back to tree.
 */
export const listFamilies = async (params?: { offset?: number; limit?: number; domain?: string }): Promise<{
  total: number;
  count: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
  items: ClusterNode[];
}> => {
  // Use templates endpoint which supports pagination, or fall back to tree
  const search = new URLSearchParams();
  if (params?.offset != null) search.set('offset', String(params.offset));
  if (params?.limit != null) search.set('limit', String(params.limit));
  const qs = search.toString();
  // The tree endpoint returns all nodes — wrap in pagination envelope for compat
  const nodes = await getClusterTree();
  const filtered = params?.domain
    ? nodes.filter(n => n.domain === params.domain)
    : nodes;
  const offset = params?.offset ?? 0;
  const limit = params?.limit ?? 50;
  const sliced = filtered.slice(offset, offset + limit);
  return {
    total: filtered.length,
    count: sliced.length,
    offset,
    has_more: offset + sliced.length < filtered.length,
    next_offset: offset + sliced.length < filtered.length ? offset + sliced.length : null,
    items: sliced,
  };
};

/** @deprecated Use updateCluster instead */
export const updateFamily = (familyId: string, updates: { intent_label?: string; domain?: string }) =>
  updateCluster(familyId, updates);
