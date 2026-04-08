import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';

import TierGuide from './TierGuide.svelte';

vi.mock('$lib/actions/tooltip', () => ({
  tooltip: () => ({ destroy() {} }),
}));

const defaultSteps = [
  { number: 1, title: 'Configure Provider', description: 'Set up your LLM provider.', detail: 'Detailed instructions here.', accent: 'cyan' as const },
  { number: 2, title: 'Run Pipeline', description: 'Execute the optimization.', detail: 'Step details.', accent: 'green' as const },
  { number: 3, title: 'Review Results', description: 'Inspect the output.', detail: 'Final step.', accent: 'yellow' as const },
];

const defaultComparison = [
  { feature: 'Speed', internal: 'Fast', sampling: 'Medium', passthrough: 'Instant' },
  { feature: 'Quality', internal: 'High', sampling: 'High', passthrough: 'Variable' },
];

function renderGuide(overrides: Record<string, unknown> = {}) {
  const props = {
    title: 'Test Guide',
    ariaLabel: 'Test guide dialog',
    accentColor: 'var(--color-neon-cyan)',
    whyTitle: 'Why This Tier?',
    whyText: 'Because it provides the best results for your use case.',
    steps: defaultSteps,
    comparison: defaultComparison,
    highlightColumn: 'internal' as const,
    open: true,
    activeStep: 0,
    onclose: vi.fn(),
    onsetstep: vi.fn(),
    onnextstep: vi.fn(),
    onprevstep: vi.fn(),
    ...overrides,
  };
  return { ...render(TierGuide, { props }), props };
}

describe('TierGuide', () => {
  afterEach(() => { cleanup(); });

  it('renders nothing visible when open=false', () => {
    renderGuide({ open: false });
    // The dialog container should not be visible
    expect(screen.queryByText('Test Guide')).not.toBeInTheDocument();
  });

  it('renders modal with title when open=true', () => {
    renderGuide({ open: true });
    expect(screen.getByText('Test Guide')).toBeInTheDocument();
  });

  it('shows the why section', () => {
    renderGuide();
    expect(screen.getByText('Why This Tier?')).toBeInTheDocument();
    expect(screen.getByText(/best results for your use case/)).toBeInTheDocument();
  });

  it('renders all step titles', () => {
    renderGuide();
    for (const step of defaultSteps) {
      expect(screen.getByText(step.title)).toBeInTheDocument();
    }
  });

  it('renders comparison table with feature labels', () => {
    renderGuide();
    expect(screen.getByText('Speed')).toBeInTheDocument();
    expect(screen.getByText('Quality')).toBeInTheDocument();
  });

  it('has accessible aria-label', () => {
    renderGuide();
    expect(screen.getByLabelText('Test guide dialog')).toBeInTheDocument();
  });

  it('close button calls onclose', async () => {
    const user = userEvent.setup();
    const { props } = renderGuide();
    const closeBtn = screen.getByLabelText('Close guide');
    await user.click(closeBtn);
    expect(props.onclose).toHaveBeenCalledWith(false);
  });

  it('dont-show-again checkbox passes dismissed=true on close', async () => {
    const user = userEvent.setup();
    const { props } = renderGuide();
    const checkbox = screen.getByRole('checkbox');
    await user.click(checkbox);
    const closeBtn = screen.getByLabelText('Close guide');
    await user.click(closeBtn);
    expect(props.onclose).toHaveBeenCalledWith(true);
  });
});
