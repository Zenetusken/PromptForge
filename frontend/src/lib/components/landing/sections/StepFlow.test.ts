import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import StepFlow from './StepFlow.svelte';

describe('StepFlow', () => {
  afterEach(() => {
    cleanup();
  });

  const sampleSteps = [
    { title: 'Analyze', description: 'Classify task type and detect weaknesses' },
    { title: 'Optimize', description: 'Rewrite using selected strategy' },
    { title: 'Score', description: 'Evaluate with 5-dimension metrics' },
  ];

  it('renders without crashing', () => {
    const { container } = render(StepFlow, { props: { steps: sampleSteps } });
    expect(container.querySelector('.step-flow')).toBeInTheDocument();
  });

  it('renders step titles', () => {
    render(StepFlow, { props: { steps: sampleSteps } });
    expect(screen.getByText('Analyze')).toBeInTheDocument();
    expect(screen.getByText('Optimize')).toBeInTheDocument();
    expect(screen.getByText('Score')).toBeInTheDocument();
  });

  it('renders step descriptions', () => {
    render(StepFlow, { props: { steps: sampleSteps } });
    expect(screen.getByText('Classify task type and detect weaknesses')).toBeInTheDocument();
  });

  it('renders step numbers', () => {
    render(StepFlow, { props: { steps: sampleSteps } });
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });
});
