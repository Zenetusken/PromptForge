import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import CardGrid from './CardGrid.svelte';

describe('CardGrid', () => {
  afterEach(() => {
    cleanup();
  });

  const sampleCards = [
    { title: 'Analyze', description: 'Classify and detect weaknesses', color: '#00e5ff' },
    { title: 'Optimize', description: 'Rewrite using strategy', color: '#a855f7' },
    { title: 'Score', description: 'Evaluate with 5 dimensions', color: '#10b981' },
  ];

  it('renders without crashing', () => {
    const { container } = render(CardGrid, { props: { columns: 3, cards: sampleCards } });
    expect(container.querySelector('.card-grid')).toBeInTheDocument();
  });

  it('renders all card titles', () => {
    render(CardGrid, { props: { columns: 3, cards: sampleCards } });
    expect(screen.getByText('Analyze')).toBeInTheDocument();
    expect(screen.getByText('Optimize')).toBeInTheDocument();
    expect(screen.getByText('Score')).toBeInTheDocument();
  });

  it('renders card descriptions', () => {
    render(CardGrid, { props: { columns: 3, cards: sampleCards } });
    expect(screen.getByText('Classify and detect weaknesses')).toBeInTheDocument();
  });

  it('renders with empty cards array', () => {
    const { container } = render(CardGrid, { props: { columns: 3, cards: [] } });
    expect(container.querySelector('.card-grid')).toBeInTheDocument();
  });
});
