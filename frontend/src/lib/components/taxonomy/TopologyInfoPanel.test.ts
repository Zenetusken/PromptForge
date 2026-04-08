import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';

vi.mock('$lib/actions/tooltip', () => ({
  tooltip: () => ({ destroy() {} }),
}));

vi.mock('$lib/utils/metric-tooltips', () => ({
  TAXONOMY_TOOLTIPS: {},
  TOPOLOGY_PANEL_TOOLTIPS: {},
}));

vi.mock('$lib/utils/taxonomy-health', () => ({
  assessTaxonomyHealth: () => ({
    level: 'good',
    headline: 'Healthy',
    detail: 'Taxonomy is healthy',
    color: 'var(--color-neon-green)',
  }),
  generatePanelInsight: () => 'System looks good.',
}));

vi.mock('$lib/components/shared/ScoreSparkline.svelte', () => ({
  default: () => {},
}));

// Inline mock data inside the factory to avoid hoisting issues
vi.mock('$lib/stores/clusters.svelte', () => ({
  clustersStore: {
    taxonomyStats: {
      q_health: 0.66,
      q_system: 0.78,
      q_sparkline: [0.60, 0.62, 0.65, 0.66],
      q_coherence: 0.85,
      q_separation: 0.55,
      q_health_coherence_w: 0.64,
      q_health_separation_w: 0.45,
      q_dbcv: 0.0,
      q_coverage: 1.0,
      nodes: { active: 67, candidate: 0, archived: 0 },
    },
    clusterDetail: null,
    selectedClusterId: null,
  },
}));

import TopologyInfoPanel from './TopologyInfoPanel.svelte';

describe('TopologyInfoPanel', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { cleanup(); });

  it('renders in system mode when no cluster is selected', () => {
    const { container } = render(TopologyInfoPanel);
    expect(container.querySelector('.ip-panel')).toBeTruthy();
  });

  it('displays Q health value', () => {
    render(TopologyInfoPanel);
    // Component formats to 3 decimal places
    expect(screen.getByText('0.660')).toBeInTheDocument();
  });

  it('displays coherence metric', () => {
    render(TopologyInfoPanel);
    expect(screen.getByText('0.64')).toBeInTheDocument();
  });

  it('displays separation metric', () => {
    render(TopologyInfoPanel);
    expect(screen.getByText('0.45')).toBeInTheDocument();
  });

  it('displays health assessment label', () => {
    render(TopologyInfoPanel);
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });

  it('hides insight text when hideInsight is true', () => {
    render(TopologyInfoPanel, { props: { hideInsight: true } });
    expect(screen.queryByText('System looks good.')).not.toBeInTheDocument();
  });

  it('shows insight text when hideInsight is false', () => {
    render(TopologyInfoPanel, { props: { hideInsight: false } });
    expect(screen.getByText('System looks good.')).toBeInTheDocument();
  });
});
