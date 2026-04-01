/**
 * Taxonomy health synthesizer — produces natural-language status from raw metrics.
 *
 * Reads Q_system, coherence, separation, node counts, trend, and warm path age
 * to generate a concise, actionable health assessment. One primary status line
 * plus optional diagnostic detail.
 */

import type { ClusterStats } from '$lib/api/clusters';

export interface HealthAssessment {
  /** Primary status line — the headline (e.g., "Healthy, stable taxonomy") */
  headline: string;
  /** Diagnostic detail — explains WHY and suggests action (1–2 sentences) */
  detail: string;
  /** Severity: 'good' | 'warning' | 'critical' | 'info' */
  severity: 'good' | 'warning' | 'critical' | 'info';
  /** CSS color for the headline */
  color: string;
}

// -- Thresholds --

const Q_GOOD = 0.7;
const Q_WARNING = 0.45;

const COHERENCE_GOOD = 0.7;
const COHERENCE_LOW = 0.5;

const SEPARATION_GOOD = 0.5;
const SEPARATION_LOW = 0.3;

const TREND_IMPROVING = 0.1;
const TREND_DECLINING = -0.1;

/**
 * Synthesize a health assessment from cluster stats.
 * Returns null if insufficient data (no stats or no snapshots).
 */
export function assessTaxonomyHealth(stats: ClusterStats | null): HealthAssessment | null {
  if (!stats || stats.q_system == null) return null;

  const q = stats.q_system;
  const coh = stats.q_coherence ?? 0;
  const sep = stats.q_separation ?? 0;
  const trend = stats.q_trend;
  const active = stats.nodes?.active ?? 0;
  const candidate = stats.nodes?.candidate ?? 0;
  const template = stats.nodes?.template ?? 0;
  const total = active + candidate + template;
  const hasTrend = (stats.q_point_count ?? 0) >= 3;

  // -- Determine trajectory --
  const improving = hasTrend && trend > TREND_IMPROVING;
  const declining = hasTrend && trend < TREND_DECLINING;

  // -- Identify issues --
  const issues: string[] = [];

  if (coh < COHERENCE_LOW) {
    issues.push('low coherence — clusters contain dissimilar patterns, split candidates likely');
  } else if (coh < COHERENCE_GOOD) {
    issues.push('moderate coherence — some clusters are loosely grouped');
  }

  if (sep < SEPARATION_LOW) {
    issues.push('low separation — clusters overlap significantly, recluster recommended');
  } else if (sep < SEPARATION_GOOD) {
    issues.push('moderate separation — some cluster boundaries are fuzzy');
  }

  if (total === 0) {
    return {
      headline: 'No clusters yet',
      detail: 'Run optimizations to start building the taxonomy. Clusters form automatically as patterns emerge.',
      severity: 'info',
      color: 'var(--color-text-dim)',
    };
  }

  if (total > 0 && total <= 3) {
    return {
      headline: 'Early taxonomy',
      detail: `${total} cluster${total > 1 ? 's' : ''} forming. Run more optimizations to establish pattern diversity and enable quality metrics.`,
      severity: 'info',
      color: 'var(--color-neon-blue)',
    };
  }

  // -- Build headline --
  let headline: string;
  let severity: HealthAssessment['severity'];
  let color: string;

  if (q >= Q_GOOD) {
    if (improving) {
      headline = 'Healthy and improving';
      severity = 'good';
      color = 'var(--color-neon-green)';
    } else if (declining) {
      headline = 'Healthy but trending down';
      severity = 'warning';
      color = 'var(--color-neon-yellow)';
    } else {
      headline = 'Healthy taxonomy';
      severity = 'good';
      color = 'var(--color-neon-green)';
    }
  } else if (q >= Q_WARNING) {
    if (improving) {
      headline = 'Recovering';
      severity = 'warning';
      color = 'var(--color-neon-yellow)';
    } else if (declining) {
      headline = 'Quality declining';
      severity = 'warning';
      color = 'var(--color-neon-orange)';
    } else {
      headline = 'Moderate quality';
      severity = 'warning';
      color = 'var(--color-neon-yellow)';
    }
  } else {
    if (improving) {
      headline = 'Low quality, recovering';
      severity = 'critical';
      color = 'var(--color-neon-orange)';
    } else {
      headline = 'Needs attention';
      severity = 'critical';
      color = 'var(--color-neon-red)';
    }
  }

  // -- Build detail --
  const parts: string[] = [];

  // Cluster composition
  const composition: string[] = [];
  if (active > 0) composition.push(`${active} active`);
  if (candidate > 0) composition.push(`${candidate} pending`);
  if (template > 0) composition.push(`${template} template`);

  if (coh >= COHERENCE_GOOD && sep >= SEPARATION_GOOD) {
    parts.push(`${composition.join(', ')} — tight grouping, well-separated boundaries`);
  } else if (issues.length > 0) {
    parts.push(`${composition.join(', ')}. ${issues[0]}`);
    if (issues.length > 1) parts.push(issues[1]);
  } else {
    parts.push(composition.join(', '));
  }

  // Actionable guidance
  if (sep < SEPARATION_LOW && active >= 5) {
    parts.push('Trigger a recluster to re-optimize cluster boundaries');
  } else if (candidate > active && candidate >= 3) {
    parts.push('Many candidates pending — warm path will promote qualifying clusters');
  } else if (template === 0 && active >= 5 && q >= Q_GOOD) {
    parts.push('No templates yet — high-quality clusters can be promoted for reuse');
  }

  return {
    headline,
    detail: parts.join('. ') + (parts.length > 0 ? '.' : ''),
    severity,
    color,
  };
}
