import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import ContentPage from './ContentPage.svelte';
import type { Section } from '$lib/content/types';

describe('ContentPage', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing with an empty sections array', () => {
    const { container } = render(ContentPage, { props: { sections: [] } });
    expect(container).toBeInTheDocument();
  });

  it('renders a hero section', () => {
    const sections: Section[] = [
      { type: 'hero', heading: 'Test Heading', subheading: 'Test subheading text' },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('Test Heading')).toBeInTheDocument();
  });

  it('renders a prose section', () => {
    const sections: Section[] = [
      { type: 'prose', blocks: [{ heading: 'About', content: '<p>Some content</p>' }] },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('About')).toBeInTheDocument();
  });

  it('renders a code-block section', () => {
    const sections: Section[] = [
      { type: 'code-block', language: 'bash', code: 'npm install' },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('npm install')).toBeInTheDocument();
  });

  it('renders a card-grid section', () => {
    const sections: Section[] = [
      {
        type: 'card-grid',
        columns: 2,
        cards: [
          { title: 'Card One', description: 'First card body', color: '#00e5ff' },
          { title: 'Card Two', description: 'Second card body', color: '#a855f7' },
        ],
      },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('Card One')).toBeInTheDocument();
  });

  it('renders a timeline section', () => {
    const sections: Section[] = [
      {
        type: 'timeline',
        versions: [
          { version: 'v1.0.0', date: '2026-01-01', categories: [{ label: 'ADDED' as const, color: '#22c55e', items: ['Initial release'] }] },
        ],
      },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
  });

  it('renders a step-flow section', () => {
    const sections: Section[] = [
      {
        type: 'step-flow',
        steps: [
          { title: 'First Step', description: 'First step description' },
          { title: 'Second Step', description: 'Second step description' },
        ],
      },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('First Step')).toBeInTheDocument();
  });

  it('renders a metric-bar section', () => {
    const sections: Section[] = [
      {
        type: 'metric-bar',
        label: 'Performance',
        dimensions: [
          { name: 'Clarity', value: 8.5, color: '#00e5ff' },
          { name: 'Structure', value: 7.0, color: '#a855f7' },
        ],
      },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('Performance')).toBeInTheDocument();
  });

  it('renders multiple mixed sections', () => {
    const sections: Section[] = [
      { type: 'hero', heading: 'Hero Section', subheading: 'Subtitle text' },
      { type: 'code-block', language: 'js', code: 'const x = 1;' },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('Hero Section')).toBeInTheDocument();
    expect(screen.getByText('const x = 1;')).toBeInTheDocument();
  });
});
