import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import Timeline from './Timeline.svelte';

describe('Timeline', () => {
  afterEach(() => {
    cleanup();
  });

  const sampleVersions = [
    {
      version: 'v0.2.0',
      date: '2026-03-01',
      categories: [
        {
          label: 'ADDED' as const,
          color: '#10b981',
          items: ['Knowledge graph view', 'Pattern extraction'],
        },
      ],
    },
    {
      version: 'v0.1.0',
      date: '2026-02-01',
      categories: [
        {
          label: 'ADDED' as const,
          color: '#10b981',
          items: ['Initial release'],
        },
      ],
    },
  ];

  it('renders without crashing', () => {
    const { container } = render(Timeline, { props: { versions: sampleVersions } });
    expect(container.querySelector('.timeline')).toBeInTheDocument();
  });

  it('renders version numbers', () => {
    render(Timeline, { props: { versions: sampleVersions } });
    expect(screen.getByText('v0.2.0')).toBeInTheDocument();
    expect(screen.getByText('v0.1.0')).toBeInTheDocument();
  });

  it('renders category items', () => {
    render(Timeline, { props: { versions: sampleVersions } });
    expect(screen.getByText('Knowledge graph view')).toBeInTheDocument();
    expect(screen.getByText('Initial release')).toBeInTheDocument();
  });
});
