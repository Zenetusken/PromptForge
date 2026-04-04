// frontend/src/lib/api/seed.ts
import { apiFetch } from './client';

export interface SeedRequest {
  project_description: string;
  workspace_path?: string | null;
  repo_full_name?: string | null;
  prompt_count?: number;
  agents?: string[] | null;
  prompts?: string[] | null;
}

export interface SeedOutput {
  status: 'completed' | 'partial' | 'failed';
  batch_id: string;
  tier: string;
  prompts_generated: number;
  prompts_optimized: number;
  prompts_failed: number;
  estimated_cost_usd: number | null;
  // NOTE: actual_cost_usd is intentionally absent — matches Python SeedOutput.
  // The backend provides estimation only.
  domains_touched: string[];
  clusters_created: number;
  summary: string;
  duration_ms: number;
}

export interface SeedAgent {
  name: string;
  description: string;
  task_types: string[];
  prompts_per_run: number;
  enabled: boolean;
}

export async function seedTaxonomy(req: SeedRequest): Promise<SeedOutput> {
  return apiFetch<SeedOutput>('/seed', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function listSeedAgents(): Promise<SeedAgent[]> {
  return apiFetch<SeedAgent[]>('/seed/agents');
}
