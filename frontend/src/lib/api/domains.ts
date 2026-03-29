/**
 * Domain API client — fetch active domain nodes from the backend.
 *
 * Domains are taxonomy nodes promoted to domain status, each with
 * an OKLab-computed color. The frontend uses these to replace the
 * former hardcoded DOMAIN_COLORS map.
 */
import { apiFetch } from './client';

// -- Types --

export interface DomainInfo {
  id: string;
  label: string;
  color_hex: string;
  member_count: number;
  avg_score: number | null;
  source: string; // seed | discovered | manual
}

// -- API functions --

export const getDomains = () => apiFetch<DomainInfo[]>('/domains');
