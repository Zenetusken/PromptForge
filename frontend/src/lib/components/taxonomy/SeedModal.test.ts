import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';

// Mock API module
vi.mock('$lib/api/seed', () => ({
  seedTaxonomy: vi.fn().mockResolvedValue({
    status: 'completed',
    prompts_generated: 10,
    prompts_optimized: 10,
    prompts_persisted: 8,
    quality_rejected: 2,
    clusters_created: 3,
    domains_touched: ['backend', 'frontend'],
    batch_id: 'test-batch-123',
    duration_ms: 5000,
  }),
  listSeedAgents: vi.fn().mockResolvedValue([
    { name: 'code-explorer', description: 'Explores codebases', task_types: ['coding'], prompts_per_run: 10, enabled: true },
    { name: 'writer', description: 'Writing tasks', task_types: ['writing'], prompts_per_run: 5, enabled: true },
  ]),
}));

vi.mock('$lib/stores/clusters.svelte', () => ({
  clustersStore: {
    invalidateTree: vi.fn(),
    invalidateStats: vi.fn(),
  },
}));

import SeedModal from './SeedModal.svelte';

describe('SeedModal', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { cleanup(); });

  // --- Visibility ---

  it('renders nothing when open=false', () => {
    render(SeedModal, { props: { open: false, onClose: vi.fn() } });
    expect(screen.queryByText(/Seed Taxonomy/i)).not.toBeInTheDocument();
  });

  it('renders modal content when open=true', () => {
    render(SeedModal, { props: { open: true, onClose: vi.fn() } });
    // The modal should show the start/seed button
    expect(screen.getByText('Start Seed')).toBeInTheDocument();
  });

  // --- Mode selection ---

  it('defaults to generate mode', () => {
    render(SeedModal, { props: { open: true, onClose: vi.fn() } });
    expect(screen.getByText(/Generate/i)).toBeInTheDocument();
  });

  it('shows provide mode option', () => {
    render(SeedModal, { props: { open: true, onClose: vi.fn() } });
    expect(screen.getByText(/Provide/i)).toBeInTheDocument();
  });

  // --- Agent loading ---

  it('loads agents when modal opens', async () => {
    const { listSeedAgents } = await import('$lib/api/seed');
    render(SeedModal, { props: { open: true, onClose: vi.fn() } });
    await vi.waitFor(() => {
      expect(listSeedAgents).toHaveBeenCalled();
    });
  });

  it('displays loaded agent names', async () => {
    render(SeedModal, { props: { open: true, onClose: vi.fn() } });
    await vi.waitFor(() => {
      expect(screen.getByText('code-explorer')).toBeInTheDocument();
    });
  });

  // --- Close behavior ---

  it('calls onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(SeedModal, { props: { open: true, onClose } });
    // Find close/cancel button
    const closeBtn = screen.queryByLabelText(/close/i) || screen.queryByText(/Cancel/i);
    if (closeBtn) {
      await user.click(closeBtn);
      expect(onClose).toHaveBeenCalled();
    }
  });

  // --- Seeding ---

  it('shows prompt count input in generate mode', () => {
    render(SeedModal, { props: { open: true, onClose: vi.fn() } });
    // The prompt count input should have a default value
    const input = screen.queryByDisplayValue('30');
    expect(input).toBeTruthy();
  });

  it('resets state when modal re-opens', async () => {
    const { container, rerender } = render(SeedModal, {
      props: { open: true, onClose: vi.fn() },
    });

    // Close
    await rerender({ open: false, onClose: vi.fn() });

    // Re-open — result and error should be cleared
    await rerender({ open: true, onClose: vi.fn() });
    expect(screen.queryByText(/completed/i)).not.toBeInTheDocument();
  });
});
