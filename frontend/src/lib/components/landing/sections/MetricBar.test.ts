import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import MetricBar from './MetricBar.svelte';

describe('MetricBar', () => {
  afterEach(() => {
    cleanup();
  });

  const sampleDimensions = [
    { name: 'Clarity', value: 8.5, color: '#00e5ff' },
    { name: 'Specificity', value: 7.0, color: '#a855f7' },
    { name: 'Structure', value: 9.0, color: '#10b981' },
  ];

  it('renders without crashing', () => {
    const { container } = render(MetricBar, { props: { dimensions: sampleDimensions } });
    expect(container.querySelector('.metric-bar')).toBeInTheDocument();
  });

  it('renders dimension names', () => {
    render(MetricBar, { props: { dimensions: sampleDimensions } });
    expect(screen.getByText('Clarity')).toBeInTheDocument();
    expect(screen.getByText('Specificity')).toBeInTheDocument();
    expect(screen.getByText('Structure')).toBeInTheDocument();
  });

  it('renders dimension values', () => {
    render(MetricBar, { props: { dimensions: sampleDimensions } });
    expect(screen.getByText('8.5')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('renders optional label when provided', () => {
    render(MetricBar, { props: { dimensions: sampleDimensions, label: 'Score Distribution' } });
    expect(screen.getByText('Score Distribution')).toBeInTheDocument();
  });
});
